"""Personal Access Token management API endpoints."""

import hashlib
import secrets
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from ghost.api.deps import CurrentUser
from ghost.db import PersonalAccessToken, get_db

router = APIRouter()

# Token prefix for easy identification
TOKEN_PREFIX = "gmcp_"


# =============================================================================
# Pydantic Models
# =============================================================================


class TokenCreateRequest(BaseModel):
    """Request model for creating a new PAT."""

    name: str
    expires_at: str | None = None  # ISO 8601 datetime string, or null for no expiry


class TokenResponse(BaseModel):
    """Response model for a PAT (never includes the hash)."""

    id: int
    name: str
    token_prefix: str
    expires_at: str | None
    last_used_at: str | None
    created_at: str | None
    is_revoked: bool


class TokenCreateResponse(BaseModel):
    """Response model for PAT creation -- includes the raw token (shown once)."""

    id: int
    name: str
    token_prefix: str
    token: str  # The raw token, shown only at creation time
    expires_at: str | None
    created_at: str | None


class TokenListResponse(BaseModel):
    """Response model for listing PATs."""

    tokens: list[TokenResponse]
    total: int


# =============================================================================
# Helpers
# =============================================================================


def _generate_token() -> str:
    """Generate a new personal access token with the gmcp_ prefix."""
    raw = secrets.token_urlsafe(32)
    return f"{TOKEN_PREFIX}{raw}"


def _hash_token(token: str) -> str:
    """Compute SHA-256 hex digest of a token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# =============================================================================
# Endpoints
# =============================================================================


@router.post("", response_model=TokenCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_token(
    request: TokenCreateRequest,
    user: CurrentUser,
):
    """Create a new Personal Access Token.

    The raw token is returned **once** in the response. It cannot be retrieved
    afterwards -- only the first characters (prefix) are stored for identification.
    """
    db = get_db()

    # Parse optional expiry
    expires_at = None
    if request.expires_at:
        try:
            expiry_str = request.expires_at
            # If only a date is provided (YYYY-MM-DD), set to end of day
            if len(expiry_str) == 10 and "T" not in expiry_str:
                expiry_str = f"{expiry_str}T23:59:59"
            expires_at = datetime.fromisoformat(expiry_str)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid expires_at format. Use ISO 8601 (e.g. 2026-12-31T23:59:59).",
            )
        if expires_at <= datetime.utcnow():
            raise HTTPException(
                status_code=400,
                detail="expires_at must be in the future.",
            )

    # Generate token and hash
    raw_token = _generate_token()
    token_hash = _hash_token(raw_token)
    # Store first 12 chars (prefix + first few random chars) for display
    token_prefix = raw_token[:12]

    with db.session() as session:
        pat = PersonalAccessToken(
            user_id=user.id,
            name=request.name,
            token_prefix=token_prefix,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        session.add(pat)
        session.flush()

        return TokenCreateResponse(
            id=pat.id,
            name=pat.name,
            token_prefix=token_prefix,
            token=raw_token,
            expires_at=pat.expires_at.isoformat() if pat.expires_at else None,
            created_at=pat.created_at.isoformat() if pat.created_at else None,
        )


@router.get("", response_model=TokenListResponse)
async def list_tokens(user: CurrentUser):
    """List all Personal Access Tokens for the current user."""
    db = get_db()

    with db.session() as session:
        tokens = (
            session.query(PersonalAccessToken)
            .filter(PersonalAccessToken.user_id == user.id)
            .order_by(PersonalAccessToken.created_at.desc())
            .all()
        )

        return TokenListResponse(
            tokens=[
                TokenResponse(
                    id=t.id,
                    name=t.name,
                    token_prefix=t.token_prefix,
                    expires_at=t.expires_at.isoformat() if t.expires_at else None,
                    last_used_at=t.last_used_at.isoformat() if t.last_used_at else None,
                    created_at=t.created_at.isoformat() if t.created_at else None,
                    is_revoked=t.is_revoked,
                )
                for t in tokens
            ],
            total=len(tokens),
        )


@router.delete("/{token_id}")
async def revoke_token(
    token_id: int,
    user: CurrentUser,
):
    """Revoke (delete) a Personal Access Token."""
    db = get_db()

    with db.session() as session:
        pat = (
            session.query(PersonalAccessToken)
            .filter(
                PersonalAccessToken.id == token_id,
                PersonalAccessToken.user_id == user.id,
            )
            .first()
        )
        if not pat:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Token not found",
            )

        session.delete(pat)

    return {"message": "Token revoked successfully"}
