"""FastAPI dependencies for authentication and authorization."""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from ghost.db import Team, TeamMembership, User, UserRole, get_db


def get_current_user(request: Request) -> User:
    """Get the current authenticated user from request state.
    
    The OAuth middleware sets request.state.user after validating headers.
    
    Raises:
        HTTPException: 401 if user is not authenticated
    """
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return user


# Type alias for dependency injection
CurrentUser = Annotated[User, Depends(get_current_user)]


class RoleChecker:
    """Dependency class for role-based access control."""
    
    def __init__(self, allowed_roles: list[UserRole]):
        """Initialize with list of allowed roles.
        
        Args:
            allowed_roles: List of UserRole values that are allowed access
        """
        self.allowed_roles = allowed_roles
    
    def __call__(self, user: CurrentUser) -> User:
        """Check if user has one of the allowed roles.
        
        Args:
            user: The current authenticated user
            
        Returns:
            The user if authorized
            
        Raises:
            HTTPException: 403 if user doesn't have required role
        """
        if user.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {[r.value for r in self.allowed_roles]}",
            )
        return user


# Pre-configured role checkers
require_admin = RoleChecker([UserRole.ADMIN])
require_manager_or_admin = RoleChecker([UserRole.MANAGER, UserRole.ADMIN])
require_any_role = RoleChecker([UserRole.USER, UserRole.MANAGER, UserRole.ADMIN])


class TeamAccessChecker:
    """Dependency class for team-based access control."""
    
    def __init__(self, require_manager: bool = False):
        """Initialize team access checker.
        
        Args:
            require_manager: If True, only team managers (or admins) can access
        """
        self.require_manager = require_manager
    
    def __call__(self, team_id: int, user: CurrentUser) -> tuple[User, Team]:
        """Check if user has access to the specified team.
        
        Args:
            team_id: The team ID to check access for
            user: The current authenticated user
            
        Returns:
            Tuple of (user, team) if authorized
            
        Raises:
            HTTPException: 404 if team not found, 403 if access denied
        """
        db = get_db()
        
        with db.session() as session:
            # Get the team
            team = session.query(Team).filter(Team.id == team_id).first()
            if not team:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Team {team_id} not found",
                )
            
            # Admins always have access
            if user.role == UserRole.ADMIN:
                session.expunge(team)
                return user, team
            
            # Check if user is the team manager
            is_manager = team.manager_id == user.id
            
            if self.require_manager:
                # Only managers (of this team) or admins can access
                if not is_manager:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Only team managers can perform this action",
                    )
                session.expunge(team)
                return user, team
            
            # Check if user is a member of the team
            membership = (
                session.query(TeamMembership)
                .filter(
                    TeamMembership.user_id == user.id,
                    TeamMembership.team_id == team_id,
                )
                .first()
            )
            
            if not membership and not is_manager:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You are not a member of this team",
                )
            
            session.expunge(team)
            return user, team


# Pre-configured team access checkers
require_team_member = TeamAccessChecker(require_manager=False)
require_team_manager = TeamAccessChecker(require_manager=True)


def get_user_teams(user: CurrentUser) -> list[Team]:
    """Get all teams the user is a member of or manages.
    
    Args:
        user: The current authenticated user
        
    Returns:
        List of Team objects
    """
    db = get_db()
    
    with db.session() as session:
        # Get teams user is a member of
        member_teams = (
            session.query(Team)
            .join(TeamMembership, Team.id == TeamMembership.team_id)
            .filter(TeamMembership.user_id == user.id)
            .all()
        )
        
        # Get teams user manages
        managed_teams = (
            session.query(Team)
            .filter(Team.manager_id == user.id)
            .all()
        )
        
        # Combine and dedupe
        all_teams = {t.id: t for t in member_teams + managed_teams}
        teams = list(all_teams.values())
        
        # Detach from session
        for team in teams:
            session.expunge(team)
        
        return teams


UserTeams = Annotated[list[Team], Depends(get_user_teams)]
