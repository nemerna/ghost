"""GitHub Token Configuration API endpoints.

Manage named token configurations with repo patterns for multi-PAT GitHub support.
Token values are never stored -- only the name-to-patterns mapping lives in the DB.
"""

import re
from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, field_validator

from ghost.api.deps import CurrentUser
from ghost.db import GitHubTokenConfig, get_db

router = APIRouter()


# =============================================================================
# Pydantic Models
# =============================================================================


class GitHubTokenConfigCreate(BaseModel):
    """Request model for creating a GitHub token config."""

    name: str
    patterns: list[str]

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate token config name (used as header suffix)."""
        v = v.strip().lower()
        if not v:
            raise ValueError("Name cannot be empty")
        if not re.match(r"^[a-z0-9][a-z0-9_-]*$", v):
            raise ValueError(
                "Name must start with a letter or digit and contain only "
                "lowercase letters, digits, hyphens, and underscores"
            )
        if len(v) > 50:
            raise ValueError("Name must be 50 characters or fewer")
        return v

    @field_validator("patterns")
    @classmethod
    def validate_patterns(cls, v: list[str]) -> list[str]:
        """Validate patterns list."""
        if not v:
            raise ValueError("At least one pattern is required")
        cleaned = []
        for p in v:
            p = p.strip()
            if p:
                cleaned.append(p)
        if not cleaned:
            raise ValueError("At least one non-empty pattern is required")
        return cleaned


class GitHubTokenConfigUpdate(BaseModel):
    """Request model for updating a GitHub token config."""

    patterns: list[str] | None = None
    display_order: int | None = None

    @field_validator("patterns")
    @classmethod
    def validate_patterns(cls, v: list[str] | None) -> list[str] | None:
        """Validate patterns list if provided."""
        if v is None:
            return v
        if not v:
            raise ValueError("At least one pattern is required")
        cleaned = []
        for p in v:
            p = p.strip()
            if p:
                cleaned.append(p)
        if not cleaned:
            raise ValueError("At least one non-empty pattern is required")
        return cleaned


class GitHubTokenConfigResponse(BaseModel):
    """Response model for a GitHub token config."""

    id: int
    name: str
    patterns: list[str]
    display_order: int
    created_at: str | None
    updated_at: str | None


class GitHubTokenConfigListResponse(BaseModel):
    """Response model for listing GitHub token configs."""

    configs: list[GitHubTokenConfigResponse]
    total: int


# =============================================================================
# Endpoints
# =============================================================================


@router.post("", response_model=GitHubTokenConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_github_token_config(
    request: GitHubTokenConfigCreate,
    user: CurrentUser,
):
    """Create a new GitHub token configuration.

    Defines a named token slot with repo patterns. The actual token value
    is passed via the X-GitHub-Token-{name} header, not stored here.
    """
    db = get_db()

    with db.session() as session:
        # Check for duplicate name
        existing = (
            session.query(GitHubTokenConfig)
            .filter(
                GitHubTokenConfig.user_id == user.id,
                GitHubTokenConfig.name == request.name,
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A token config named '{request.name}' already exists",
            )

        # Get next display_order
        max_order = (
            session.query(GitHubTokenConfig.display_order)
            .filter(GitHubTokenConfig.user_id == user.id)
            .order_by(GitHubTokenConfig.display_order.desc())
            .first()
        )
        next_order = (max_order[0] + 1) if max_order else 0

        config = GitHubTokenConfig(
            user_id=user.id,
            name=request.name,
            patterns=request.patterns,
            display_order=next_order,
        )
        session.add(config)
        session.flush()

        return GitHubTokenConfigResponse(
            id=config.id,
            name=config.name,
            patterns=config.patterns,
            display_order=config.display_order,
            created_at=config.created_at.isoformat() if config.created_at else None,
            updated_at=config.updated_at.isoformat() if config.updated_at else None,
        )


@router.get("", response_model=GitHubTokenConfigListResponse)
async def list_github_token_configs(user: CurrentUser):
    """List all GitHub token configurations for the current user."""
    db = get_db()

    with db.session() as session:
        configs = (
            session.query(GitHubTokenConfig)
            .filter(GitHubTokenConfig.user_id == user.id)
            .order_by(GitHubTokenConfig.display_order)
            .all()
        )

        return GitHubTokenConfigListResponse(
            configs=[
                GitHubTokenConfigResponse(
                    id=c.id,
                    name=c.name,
                    patterns=c.patterns,
                    display_order=c.display_order,
                    created_at=c.created_at.isoformat() if c.created_at else None,
                    updated_at=c.updated_at.isoformat() if c.updated_at else None,
                )
                for c in configs
            ],
            total=len(configs),
        )


@router.put("/{config_id}", response_model=GitHubTokenConfigResponse)
async def update_github_token_config(
    config_id: int,
    request: GitHubTokenConfigUpdate,
    user: CurrentUser,
):
    """Update a GitHub token configuration's patterns or display order."""
    db = get_db()

    with db.session() as session:
        config = (
            session.query(GitHubTokenConfig)
            .filter(
                GitHubTokenConfig.id == config_id,
                GitHubTokenConfig.user_id == user.id,
            )
            .first()
        )
        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Token config not found",
            )

        if request.patterns is not None:
            config.patterns = request.patterns
        if request.display_order is not None:
            config.display_order = request.display_order

        config.updated_at = datetime.utcnow()
        session.flush()

        return GitHubTokenConfigResponse(
            id=config.id,
            name=config.name,
            patterns=config.patterns,
            display_order=config.display_order,
            created_at=config.created_at.isoformat() if config.created_at else None,
            updated_at=config.updated_at.isoformat() if config.updated_at else None,
        )


@router.delete("/{config_id}")
async def delete_github_token_config(
    config_id: int,
    user: CurrentUser,
):
    """Delete a GitHub token configuration."""
    db = get_db()

    with db.session() as session:
        config = (
            session.query(GitHubTokenConfig)
            .filter(
                GitHubTokenConfig.id == config_id,
                GitHubTokenConfig.user_id == user.id,
            )
            .first()
        )
        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Token config not found",
            )

        session.delete(config)

    return {"message": "Token config deleted successfully"}
