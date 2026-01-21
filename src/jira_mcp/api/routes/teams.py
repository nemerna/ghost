"""Team management API endpoints."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from jira_mcp.api.deps import (
    CurrentUser,
    UserTeams,
    require_admin,
    require_manager_or_admin,
    require_team_manager,
    require_team_member,
)
from jira_mcp.db import Team, TeamMembership, User, UserRole, get_db

router = APIRouter()


# =============================================================================
# Pydantic Models
# =============================================================================


class TeamMemberResponse(BaseModel):
    """Team member response model."""
    
    id: int
    email: str
    display_name: str | None
    role: str
    joined_at: str | None


class TeamResponse(BaseModel):
    """Team response model."""
    
    id: int
    name: str
    description: str | None
    manager_id: int | None
    manager_email: str | None
    manager_name: str | None
    member_count: int
    created_at: str | None
    updated_at: str | None


class TeamDetailResponse(TeamResponse):
    """Detailed team response with members."""
    
    members: list[TeamMemberResponse]


class TeamCreateRequest(BaseModel):
    """Request model for creating a team."""
    
    name: str
    description: str | None = None
    manager_id: int | None = None


class TeamUpdateRequest(BaseModel):
    """Request model for updating a team."""
    
    name: str | None = None
    description: str | None = None
    manager_id: int | None = None


class AddMemberRequest(BaseModel):
    """Request model for adding a team member."""
    
    user_id: int


class TeamListResponse(BaseModel):
    """Response model for team list."""
    
    teams: list[TeamResponse]
    total: int


# =============================================================================
# Helper Functions
# =============================================================================


def team_to_response(team: Team, session) -> TeamResponse:
    """Convert Team model to response."""
    member_count = (
        session.query(TeamMembership)
        .filter(TeamMembership.team_id == team.id)
        .count()
    )
    
    return TeamResponse(
        id=team.id,
        name=team.name,
        description=team.description,
        manager_id=team.manager_id,
        manager_email=team.manager.email if team.manager else None,
        manager_name=team.manager.display_name if team.manager else None,
        member_count=member_count,
        created_at=team.created_at.isoformat() if team.created_at else None,
        updated_at=team.updated_at.isoformat() if team.updated_at else None,
    )


# =============================================================================
# Endpoints
# =============================================================================


@router.get("", response_model=TeamListResponse)
async def list_teams(
    user: CurrentUser,
    all_teams: bool = Query(False, description="Show all teams (admin only)"),
    search: str | None = Query(None, description="Search by team name"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """List teams the user has access to.
    
    Regular users see teams they're members of.
    Admins can see all teams with all_teams=true.
    """
    db = get_db()
    
    with db.session() as session:
        if all_teams and user.role == UserRole.ADMIN:
            # Admin viewing all teams
            query = session.query(Team)
        else:
            # Get user's teams (member of or manager)
            team_ids = (
                session.query(TeamMembership.team_id)
                .filter(TeamMembership.user_id == user.id)
                .subquery()
            )
            query = session.query(Team).filter(
                (Team.id.in_(team_ids)) | (Team.manager_id == user.id)
            )
        
        # Apply search filter
        if search:
            query = query.filter(Team.name.ilike(f"%{search}%"))
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        teams = query.order_by(Team.name).offset(offset).limit(limit).all()
        
        return TeamListResponse(
            teams=[team_to_response(t, session) for t in teams],
            total=total,
        )


@router.post("", response_model=TeamResponse, status_code=status.HTTP_201_CREATED)
async def create_team(
    request: TeamCreateRequest,
    user: Annotated[User, Depends(require_admin)],
):
    """Create a new team (admin only)."""
    db = get_db()
    
    with db.session() as session:
        # Check if team name already exists
        existing = session.query(Team).filter(Team.name == request.name).first()
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Team '{request.name}' already exists",
            )
        
        # Verify manager exists if provided
        if request.manager_id:
            manager = session.query(User).filter(User.id == request.manager_id).first()
            if not manager:
                raise HTTPException(status_code=400, detail="Manager not found")
        
        # Create team
        team = Team(
            name=request.name,
            description=request.description,
            manager_id=request.manager_id,
            created_at=datetime.utcnow(),
        )
        session.add(team)
        session.flush()
        
        return team_to_response(team, session)


@router.get("/{team_id}", response_model=TeamDetailResponse)
async def get_team(
    team_id: int,
    user: CurrentUser,
):
    """Get team details including members."""
    db = get_db()
    
    with db.session() as session:
        team = session.query(Team).filter(Team.id == team_id).first()
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")
        
        # Check access (member, manager, or admin)
        if user.role != UserRole.ADMIN:
            is_manager = team.manager_id == user.id
            is_member = (
                session.query(TeamMembership)
                .filter(
                    TeamMembership.team_id == team_id,
                    TeamMembership.user_id == user.id,
                )
                .first()
            )
            if not is_manager and not is_member:
                raise HTTPException(status_code=403, detail="Access denied")
        
        # Get members
        memberships = (
            session.query(TeamMembership)
            .filter(TeamMembership.team_id == team_id)
            .all()
        )
        
        members = []
        for m in memberships:
            member_user = session.query(User).filter(User.id == m.user_id).first()
            if member_user:
                members.append(
                    TeamMemberResponse(
                        id=member_user.id,
                        email=member_user.email,
                        display_name=member_user.display_name,
                        role=member_user.role.value if member_user.role else "user",
                        joined_at=m.joined_at.isoformat() if m.joined_at else None,
                    )
                )
        
        member_count = len(members)
        
        return TeamDetailResponse(
            id=team.id,
            name=team.name,
            description=team.description,
            manager_id=team.manager_id,
            manager_email=team.manager.email if team.manager else None,
            manager_name=team.manager.display_name if team.manager else None,
            member_count=member_count,
            created_at=team.created_at.isoformat() if team.created_at else None,
            updated_at=team.updated_at.isoformat() if team.updated_at else None,
            members=members,
        )


@router.put("/{team_id}", response_model=TeamResponse)
async def update_team(
    team_id: int,
    request: TeamUpdateRequest,
    user: Annotated[User, Depends(require_manager_or_admin)],
):
    """Update a team (manager or admin only)."""
    db = get_db()
    
    with db.session() as session:
        team = session.query(Team).filter(Team.id == team_id).first()
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")
        
        # Check if user is manager of this team or admin
        if user.role != UserRole.ADMIN and team.manager_id != user.id:
            raise HTTPException(status_code=403, detail="Only team manager or admin can update")
        
        # Update fields
        if request.name is not None:
            # Check if new name is unique
            existing = (
                session.query(Team)
                .filter(Team.name == request.name, Team.id != team_id)
                .first()
            )
            if existing:
                raise HTTPException(status_code=400, detail=f"Team '{request.name}' already exists")
            team.name = request.name
        
        if request.description is not None:
            team.description = request.description
        
        if request.manager_id is not None:
            # Verify manager exists
            manager = session.query(User).filter(User.id == request.manager_id).first()
            if not manager:
                raise HTTPException(status_code=400, detail="Manager not found")
            team.manager_id = request.manager_id
        
        session.flush()
        
        return team_to_response(team, session)


@router.delete("/{team_id}")
async def delete_team(
    team_id: int,
    user: Annotated[User, Depends(require_admin)],
):
    """Delete a team (admin only)."""
    db = get_db()
    
    with db.session() as session:
        team = session.query(Team).filter(Team.id == team_id).first()
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")
        
        session.delete(team)
    
    return {"message": f"Team '{team.name}' deleted successfully"}


@router.post("/{team_id}/members", response_model=TeamMemberResponse, status_code=status.HTTP_201_CREATED)
async def add_team_member(
    team_id: int,
    request: AddMemberRequest,
    user: Annotated[User, Depends(require_manager_or_admin)],
):
    """Add a member to a team (manager or admin only)."""
    db = get_db()
    
    with db.session() as session:
        team = session.query(Team).filter(Team.id == team_id).first()
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")
        
        # Check if user is manager of this team or admin
        if user.role != UserRole.ADMIN and team.manager_id != user.id:
            raise HTTPException(status_code=403, detail="Only team manager or admin can add members")
        
        # Check if user to add exists
        new_member = session.query(User).filter(User.id == request.user_id).first()
        if not new_member:
            raise HTTPException(status_code=400, detail="User not found")
        
        # Check if already a member
        existing = (
            session.query(TeamMembership)
            .filter(
                TeamMembership.team_id == team_id,
                TeamMembership.user_id == request.user_id,
            )
            .first()
        )
        if existing:
            raise HTTPException(status_code=400, detail="User is already a member of this team")
        
        # Add membership
        membership = TeamMembership(
            user_id=request.user_id,
            team_id=team_id,
            joined_at=datetime.utcnow(),
        )
        session.add(membership)
        session.flush()
        
        return TeamMemberResponse(
            id=new_member.id,
            email=new_member.email,
            display_name=new_member.display_name,
            role=new_member.role.value if new_member.role else "user",
            joined_at=membership.joined_at.isoformat() if membership.joined_at else None,
        )


@router.delete("/{team_id}/members/{member_id}")
async def remove_team_member(
    team_id: int,
    member_id: int,
    user: Annotated[User, Depends(require_manager_or_admin)],
):
    """Remove a member from a team (manager or admin only)."""
    db = get_db()
    
    with db.session() as session:
        team = session.query(Team).filter(Team.id == team_id).first()
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")
        
        # Check if user is manager of this team or admin
        if user.role != UserRole.ADMIN and team.manager_id != user.id:
            raise HTTPException(status_code=403, detail="Only team manager or admin can remove members")
        
        # Find membership
        membership = (
            session.query(TeamMembership)
            .filter(
                TeamMembership.team_id == team_id,
                TeamMembership.user_id == member_id,
            )
            .first()
        )
        if not membership:
            raise HTTPException(status_code=404, detail="User is not a member of this team")
        
        session.delete(membership)
    
    return {"message": f"Member removed from team successfully"}
