"""Activity tracking API endpoints."""

import json
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from jira_mcp.api.deps import CurrentUser, require_manager_or_admin
from jira_mcp.db import ActivityLog, Team, TeamMembership, User, UserRole, get_db
from jira_mcp.db.models import ActionType

router = APIRouter()


# =============================================================================
# Pydantic Models
# =============================================================================


class ActivityResponse(BaseModel):
    """Activity response model."""
    
    id: int
    username: str
    user_id: int | None
    ticket_key: str
    ticket_summary: str | None
    project_key: str | None
    action_type: str
    action_details: dict | None
    timestamp: str


class ActivityCreateRequest(BaseModel):
    """Request model for creating an activity."""
    
    ticket_key: str
    ticket_summary: str | None = None
    project_key: str | None = None
    action_type: str = "other"
    action_details: dict | None = None


class ActivityListResponse(BaseModel):
    """Response model for activity list."""
    
    activities: list[ActivityResponse]
    total: int


class ActivitySummaryResponse(BaseModel):
    """Summary of activities for a time period."""
    
    total_activities: int
    unique_tickets: int
    by_action_type: dict[str, int]
    by_project: dict[str, int]
    period_start: str
    period_end: str


# =============================================================================
# Helper Functions
# =============================================================================


def activity_to_response(activity: ActivityLog) -> ActivityResponse:
    """Convert ActivityLog model to response."""
    return ActivityResponse(
        id=activity.id,
        username=activity.username,
        user_id=activity.user_id,
        ticket_key=activity.ticket_key,
        ticket_summary=activity.ticket_summary,
        project_key=activity.project_key,
        action_type=activity.action_type.value if activity.action_type else "other",
        action_details=json.loads(activity.action_details) if activity.action_details else None,
        timestamp=activity.timestamp.isoformat() if activity.timestamp else None,
    )


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/my", response_model=ActivityListResponse)
async def get_my_activities(
    user: CurrentUser,
    start_date: datetime | None = Query(None, description="Filter by start date"),
    end_date: datetime | None = Query(None, description="Filter by end date"),
    project_key: str | None = Query(None, description="Filter by project"),
    action_type: str | None = Query(None, description="Filter by action type"),
    ticket_key: str | None = Query(None, description="Filter by ticket key"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Get the current user's activities."""
    db = get_db()
    
    with db.session() as session:
        query = session.query(ActivityLog).filter(ActivityLog.username == user.email)
        
        # Apply date filters
        if start_date:
            query = query.filter(ActivityLog.timestamp >= start_date)
        if end_date:
            query = query.filter(ActivityLog.timestamp <= end_date)
        
        # Apply other filters
        if project_key:
            query = query.filter(ActivityLog.project_key == project_key)
        if action_type:
            try:
                action_enum = ActionType(action_type.lower())
                query = query.filter(ActivityLog.action_type == action_enum)
            except ValueError:
                pass  # Invalid action type, ignore
        if ticket_key:
            query = query.filter(ActivityLog.ticket_key.ilike(f"%{ticket_key}%"))
        
        # Get total count
        total = query.count()
        
        # Apply pagination and ordering
        activities = (
            query.order_by(ActivityLog.timestamp.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        
        return ActivityListResponse(
            activities=[activity_to_response(a) for a in activities],
            total=total,
        )


@router.get("/my/summary", response_model=ActivitySummaryResponse)
async def get_my_activity_summary(
    user: CurrentUser,
    days: int = Query(7, ge=1, le=365, description="Number of days to summarize"),
):
    """Get a summary of the current user's activities."""
    db = get_db()
    
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    with db.session() as session:
        activities = (
            session.query(ActivityLog)
            .filter(
                ActivityLog.username == user.email,
                ActivityLog.timestamp >= start_date,
                ActivityLog.timestamp <= end_date,
            )
            .all()
        )
        
        # Calculate summaries
        unique_tickets = set()
        by_action_type = {}
        by_project = {}
        
        for a in activities:
            unique_tickets.add(a.ticket_key)
            
            action = a.action_type.value if a.action_type else "other"
            by_action_type[action] = by_action_type.get(action, 0) + 1
            
            if a.project_key:
                by_project[a.project_key] = by_project.get(a.project_key, 0) + 1
        
        return ActivitySummaryResponse(
            total_activities=len(activities),
            unique_tickets=len(unique_tickets),
            by_action_type=by_action_type,
            by_project=by_project,
            period_start=start_date.isoformat(),
            period_end=end_date.isoformat(),
        )


@router.post("", response_model=ActivityResponse, status_code=status.HTTP_201_CREATED)
async def create_activity(
    request: ActivityCreateRequest,
    user: CurrentUser,
):
    """Log a new activity manually."""
    db = get_db()
    
    # Extract project key from ticket if not provided
    project_key = request.project_key
    if not project_key and "-" in request.ticket_key:
        project_key = request.ticket_key.split("-")[0]
    
    # Map action type
    try:
        action_enum = ActionType(request.action_type.lower())
    except ValueError:
        action_enum = ActionType.OTHER
    
    with db.session() as session:
        activity = ActivityLog(
            username=user.email,
            user_id=user.id,
            ticket_key=request.ticket_key,
            ticket_summary=request.ticket_summary,
            project_key=project_key,
            action_type=action_enum,
            action_details=json.dumps(request.action_details) if request.action_details else None,
            timestamp=datetime.utcnow(),
        )
        session.add(activity)
        session.flush()
        
        return activity_to_response(activity)


@router.delete("/{activity_id}")
async def delete_activity(
    activity_id: int,
    user: CurrentUser,
):
    """Delete an activity (own activities only)."""
    db = get_db()
    
    with db.session() as session:
        activity = session.query(ActivityLog).filter(ActivityLog.id == activity_id).first()
        if not activity:
            raise HTTPException(status_code=404, detail="Activity not found")
        
        # Check ownership (by username/email or user_id)
        if activity.username != user.email and activity.user_id != user.id:
            # Allow admin to delete any activity
            if user.role != UserRole.ADMIN:
                raise HTTPException(status_code=403, detail="Can only delete your own activities")
        
        session.delete(activity)
    
    return {"message": "Activity deleted successfully"}


@router.get("/team/{team_id}", response_model=ActivityListResponse)
async def get_team_activities(
    team_id: int,
    user: Annotated[User, Depends(require_manager_or_admin)],
    start_date: datetime | None = Query(None, description="Filter by start date"),
    end_date: datetime | None = Query(None, description="Filter by end date"),
    project_key: str | None = Query(None, description="Filter by project"),
    member_id: int | None = Query(None, description="Filter by team member"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Get activities for all members of a team (manager or admin only)."""
    db = get_db()
    
    with db.session() as session:
        # Verify team exists and user has access
        team = session.query(Team).filter(Team.id == team_id).first()
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")
        
        # Check if user is manager of this team or admin
        if user.role != UserRole.ADMIN and team.manager_id != user.id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Get team member emails
        memberships = (
            session.query(TeamMembership)
            .filter(TeamMembership.team_id == team_id)
            .all()
        )
        member_ids = [m.user_id for m in memberships]
        
        # Include manager
        if team.manager_id:
            member_ids.append(team.manager_id)
        
        if member_id:
            if member_id not in member_ids:
                raise HTTPException(status_code=400, detail="User is not a member of this team")
            member_ids = [member_id]
        
        # Get member emails
        members = session.query(User).filter(User.id.in_(member_ids)).all()
        member_emails = [m.email for m in members]
        
        if not member_emails:
            return ActivityListResponse(activities=[], total=0)
        
        # Query activities
        query = session.query(ActivityLog).filter(ActivityLog.username.in_(member_emails))
        
        # Apply date filters
        if start_date:
            query = query.filter(ActivityLog.timestamp >= start_date)
        if end_date:
            query = query.filter(ActivityLog.timestamp <= end_date)
        
        # Apply other filters
        if project_key:
            query = query.filter(ActivityLog.project_key == project_key)
        
        # Get total count
        total = query.count()
        
        # Apply pagination and ordering
        activities = (
            query.order_by(ActivityLog.timestamp.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        
        return ActivityListResponse(
            activities=[activity_to_response(a) for a in activities],
            total=total,
        )


@router.get("/team/{team_id}/summary", response_model=dict)
async def get_team_activity_summary(
    team_id: int,
    user: Annotated[User, Depends(require_manager_or_admin)],
    days: int = Query(7, ge=1, le=365, description="Number of days to summarize"),
):
    """Get activity summary for a team (manager or admin only)."""
    db = get_db()
    
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    with db.session() as session:
        # Verify team exists and user has access
        team = session.query(Team).filter(Team.id == team_id).first()
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")
        
        if user.role != UserRole.ADMIN and team.manager_id != user.id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Get team member emails
        memberships = (
            session.query(TeamMembership)
            .filter(TeamMembership.team_id == team_id)
            .all()
        )
        member_ids = [m.user_id for m in memberships]
        if team.manager_id:
            member_ids.append(team.manager_id)
        
        members = session.query(User).filter(User.id.in_(member_ids)).all()
        member_emails = [m.email for m in members]
        
        # Get activities
        activities = (
            session.query(ActivityLog)
            .filter(
                ActivityLog.username.in_(member_emails),
                ActivityLog.timestamp >= start_date,
                ActivityLog.timestamp <= end_date,
            )
            .all()
        )
        
        # Calculate per-member summaries
        by_member = {}
        total_tickets = set()
        total_by_action = {}
        
        for a in activities:
            total_tickets.add(a.ticket_key)
            
            action = a.action_type.value if a.action_type else "other"
            total_by_action[action] = total_by_action.get(action, 0) + 1
            
            if a.username not in by_member:
                by_member[a.username] = {
                    "total_activities": 0,
                    "unique_tickets": set(),
                }
            by_member[a.username]["total_activities"] += 1
            by_member[a.username]["unique_tickets"].add(a.ticket_key)
        
        # Convert sets to counts
        member_summaries = {
            email: {
                "total_activities": data["total_activities"],
                "unique_tickets": len(data["unique_tickets"]),
            }
            for email, data in by_member.items()
        }
        
        return {
            "team_id": team_id,
            "team_name": team.name,
            "total_activities": len(activities),
            "total_unique_tickets": len(total_tickets),
            "by_action_type": total_by_action,
            "by_member": member_summaries,
            "period_start": start_date.isoformat(),
            "period_end": end_date.isoformat(),
        }
