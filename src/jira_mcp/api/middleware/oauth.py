"""OAuth Proxy middleware for OpenShift authentication.

This middleware reads user information from headers set by the OpenShift OAuth Proxy
sidecar and auto-provisions users in the database on first access.

Headers expected from OAuth Proxy:
- X-Forwarded-User: OpenShift username
- X-Forwarded-Email: User's email address (primary identifier)
- X-Forwarded-Access-Token: OAuth access token (optional)

Role assignment is determined by:
1. ADMIN_EMAILS environment variable (comma-separated list)
2. MANAGER_EMAILS environment variable (comma-separated list)
3. Default: USER role
"""

import logging
import os
from datetime import datetime
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from jira_mcp.db import User, UserRole, get_db


def _get_email_list(env_var: str) -> set[str]:
    """Get a set of emails from an environment variable (comma-separated, case-insensitive)."""
    value = os.environ.get(env_var, "")
    if not value:
        return set()
    return {email.strip().lower() for email in value.split(",") if email.strip()}

logger = logging.getLogger(__name__)

# Paths that don't require authentication
PUBLIC_PATHS = {
    "/api/health",
    "/api/health/",
    "/health",
    "/health/",
    "/docs",
    "/openapi.json",
    "/redoc",
}


class OAuthProxyMiddleware(BaseHTTPMiddleware):
    """Middleware to handle OpenShift OAuth Proxy authentication.
    
    This middleware:
    1. Reads X-Forwarded-* headers from the OAuth proxy
    2. Looks up or creates the user in the database
    3. Attaches the user to the request state
    4. Rejects unauthenticated requests to protected endpoints
    """

    def __init__(self, app, dev_mode: bool = False, dev_email: str | None = None):
        """Initialize the OAuth middleware.
        
        Args:
            app: The ASGI application
            dev_mode: If True, bypass OAuth headers and use dev_email
            dev_email: Email to use in dev mode (required if dev_mode=True)
        """
        super().__init__(app)
        self.dev_mode = dev_mode
        self.dev_email = dev_email
        
        if dev_mode:
            logger.warning("OAuth middleware running in DEVELOPMENT mode - authentication bypassed!")
            if not dev_email:
                raise ValueError("dev_email is required when dev_mode is True")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process the request, authenticating the user from OAuth headers."""
        
        # Skip auth for public paths
        if self._is_public_path(request.url.path):
            return await call_next(request)
        
        # Skip auth for static files
        if request.url.path.startswith("/static") or request.url.path.startswith("/assets"):
            return await call_next(request)
        
        # Get user info from headers or dev mode
        if self.dev_mode:
            email = self.dev_email
            username = self.dev_email.split("@")[0] if self.dev_email else "dev-user"
            groups = []
        else:
            email = request.headers.get("X-Forwarded-Email")
            username = request.headers.get("X-Forwarded-User")
            groups_header = request.headers.get("X-Forwarded-Groups", "")
            groups = [g.strip() for g in groups_header.split(",") if g.strip()]
        
        # Reject if no email (required for user identification)
        if not email:
            logger.warning(f"Request to {request.url.path} rejected - no X-Forwarded-Email header")
            return JSONResponse(
                status_code=401,
                content={
                    "error": "unauthorized",
                    "message": "Authentication required. Please log in via OpenShift.",
                },
            )
        
        # Look up or create user
        try:
            user = await self._get_or_create_user(email, username, groups)
            request.state.user = user
            request.state.user_email = email
            request.state.user_groups = groups
        except Exception as e:
            logger.exception(f"Error processing user {email}: {e}")
            return JSONResponse(
                status_code=500,
                content={
                    "error": "internal_error",
                    "message": "Failed to process user authentication.",
                },
            )
        
        # Continue with the request
        response = await call_next(request)
        return response

    def _is_public_path(self, path: str) -> bool:
        """Check if the path is public (no auth required)."""
        # Exact match
        if path in PUBLIC_PATHS:
            return True
        
        # Prefix match for certain paths
        if path.startswith("/docs") or path.startswith("/redoc"):
            return True
        
        return False

    async def _get_or_create_user(
        self, email: str, username: str | None, groups: list[str]
    ) -> User:
        """Get existing user or create a new one.
        
        Args:
            email: User's email address (primary identifier)
            username: OpenShift username (used for display name if no existing name)
            groups: User's groups from OAuth (can be used for role mapping)
            
        Returns:
            The User object from the database
        """
        db = get_db()
        
        # Determine role from email lists and groups (used for both new and existing users)
        role_from_groups = self._determine_role(email, groups)
        
        with db.session() as session:
            # Look up user by email
            user = session.query(User).filter(User.email == email).first()
            
            if user:
                # Update last_seen
                user.last_seen = datetime.utcnow()
                
                # Update display name if not set and username provided
                if not user.display_name and username:
                    user.display_name = username
                
                # Sync role on every login based on ADMIN_EMAILS, MANAGER_EMAILS, or groups
                # This ensures role changes when configuration changes
                if user.role != role_from_groups:
                    logger.info(
                        f"User {email} role changed from {user.role.value} to "
                        f"{role_from_groups.value}"
                    )
                    user.role = role_from_groups
                
                session.flush()
                
                # Detach from session for use outside
                session.expunge(user)
                logger.debug(f"Existing user authenticated: {email}")
            else:
                # Create new user with role from groups
                user = User(
                    email=email,
                    display_name=username or email.split("@")[0],
                    role=role_from_groups,
                    first_seen=datetime.utcnow(),
                    last_seen=datetime.utcnow(),
                )
                session.add(user)
                session.flush()
                
                # Detach from session
                session.expunge(user)
                logger.info(f"New user created: {email} with role {role_from_groups.value}")
        
        return user

    def _determine_role(self, email: str, groups: list[str]) -> UserRole:
        """Determine user role based on email lists and OAuth groups.
        
        Priority:
        1. ADMIN_EMAILS environment variable
        2. MANAGER_EMAILS environment variable
        3. OAuth groups (if passed by proxy)
        4. Default: USER
        
        Args:
            email: User's email address
            groups: List of group names from OAuth (may be empty)
            
        Returns:
            The appropriate UserRole
        """
        email_lower = email.lower()
        
        # Check email-based role assignment (highest priority)
        admin_emails = _get_email_list("ADMIN_EMAILS")
        if email_lower in admin_emails:
            return UserRole.ADMIN
        
        manager_emails = _get_email_list("MANAGER_EMAILS")
        if email_lower in manager_emails:
            return UserRole.MANAGER
        
        # Fall back to group-based role assignment
        admin_groups = {"admin", "admins", "cluster-admins", "system:cluster-admins"}
        manager_groups = {"managers", "team-leads", "project-leads"}
        
        groups_lower = {g.lower() for g in groups}
        
        if groups_lower & admin_groups:
            return UserRole.ADMIN
        elif groups_lower & manager_groups:
            return UserRole.MANAGER
        
        return UserRole.USER
