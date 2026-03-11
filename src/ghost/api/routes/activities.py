"""Activity tracking API endpoints."""

import json
import re
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from ghost.api.deps import CurrentUser, require_manager_or_admin
from ghost.db import ActivityLog, Team, TeamMembership, TicketSource, User, UserRole, get_db
from ghost.db.models import ActionType

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
    ticket_source: str
    project_key: str | None
    github_repo: str | None
    action_type: str
    action_details: dict | None
    timestamp: str
    visible_to_manager: bool | None = None


class VisibilityUpdateRequest(BaseModel):
    """Request model for updating visibility."""
    
    visible_to_manager: bool | None  # None = inherit from user preferences


class ActivityCreateRequest(BaseModel):
    """Request model for creating an activity."""
    
    ticket_key: str
    ticket_summary: str | None = None
    project_key: str | None = None
    github_repo: str | None = None
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
    by_source: dict[str, int]
    period_start: str
    period_end: str


# =============================================================================
# Helper Functions
# =============================================================================


def _parse_ticket_source(
    ticket_key: str, github_repo: str | None = None
) -> tuple[TicketSource, str, str | None, str | None]:
    """
    Parse a ticket key and determine its source.
    
    Returns: (source, normalized_key, project_key, github_repo)
    """
    # GitHub Issue patterns
    github_full_pattern = r"^([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)#(\d+)$"
    github_short_pattern = r"^#(\d+)$"

    # Check for full GitHub format (owner/repo#123)
    full_match = re.match(github_full_pattern, ticket_key)
    if full_match:
        repo = full_match.group(1)
        return TicketSource.GITHUB, ticket_key, None, repo

    # Check for short GitHub format (#123)
    short_match = re.match(github_short_pattern, ticket_key)
    if short_match and github_repo:
        issue_num = short_match.group(1)
        full_key = f"{github_repo}#{issue_num}"
        return TicketSource.GITHUB, full_key, None, github_repo

    # Default: Jira ticket
    project_key = None
    if "-" in ticket_key:
        project_key = ticket_key.split("-")[0]

    return TicketSource.JIRA, ticket_key, project_key, None


def activity_to_response(activity: ActivityLog) -> ActivityResponse:
    """Convert ActivityLog model to response."""
    return ActivityResponse(
        id=activity.id,
        username=activity.username,
        user_id=activity.user_id,
        ticket_key=activity.ticket_key,
        ticket_summary=activity.ticket_summary,
        ticket_source=activity.ticket_source.value if activity.ticket_source else "jira",
        project_key=activity.project_key,
        github_repo=activity.github_repo,
        action_type=activity.action_type.value if activity.action_type else "other",
        action_details=json.loads(activity.action_details) if activity.action_details else None,
        timestamp=activity.timestamp.isoformat() if activity.timestamp else None,
        visible_to_manager=activity.visible_to_manager,
    )


def _get_user_visibility_defaults(user: User) -> dict:
    """Get visibility defaults from user preferences."""
    preferences = json.loads(user.preferences) if user.preferences else {}
    return preferences.get("visibility_defaults", {
        "activity_logs": "shared",
        "management_reports": "private",
    })


def _is_activity_visible_to_manager(activity: ActivityLog, user_visibility_defaults: dict) -> bool:
    """Check if an activity is visible to manager based on item override or user defaults."""
    if activity.visible_to_manager is not None:
        return activity.visible_to_manager
    # Fall back to user's type default
    return user_visibility_defaults.get("activity_logs", "shared") == "shared"


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/my", response_model=ActivityListResponse)
async def get_my_activities(
    user: CurrentUser,
    start_date: datetime | None = Query(None, description="Filter by start date"),
    end_date: datetime | None = Query(None, description="Filter by end date"),
    project_key: str | None = Query(None, description="Filter by Jira project"),
    ticket_source: str | None = Query(None, description="Filter by source: 'jira' or 'github'"),
    github_repo: str | None = Query(None, description="Filter by GitHub repo (owner/repo)"),
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
        
        # Apply source filters
        if ticket_source:
            try:
                source_enum = TicketSource(ticket_source.lower())
                query = query.filter(ActivityLog.ticket_source == source_enum)
            except ValueError:
                pass  # Invalid source, ignore
        if project_key:
            query = query.filter(ActivityLog.project_key == project_key)
        if github_repo:
            query = query.filter(ActivityLog.github_repo == github_repo)
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
    ticket_source: str | None = Query(None, description="Filter by source: 'jira' or 'github'"),
):
    """Get a summary of the current user's activities."""
    db = get_db()
    
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    with db.session() as session:
        query = session.query(ActivityLog).filter(
            ActivityLog.username == user.email,
            ActivityLog.timestamp >= start_date,
            ActivityLog.timestamp <= end_date,
        )
        
        if ticket_source:
            try:
                source_enum = TicketSource(ticket_source.lower())
                query = query.filter(ActivityLog.ticket_source == source_enum)
            except ValueError:
                pass
        
        activities = query.all()
        
        # Calculate summaries
        unique_tickets = set()
        by_action_type = {}
        by_project = {}
        by_source = {"jira": 0, "github": 0}
        
        for a in activities:
            unique_tickets.add(a.ticket_key)
            
            action = a.action_type.value if a.action_type else "other"
            by_action_type[action] = by_action_type.get(action, 0) + 1
            
            if a.project_key:
                by_project[a.project_key] = by_project.get(a.project_key, 0) + 1
            
            source = a.ticket_source.value if a.ticket_source else "jira"
            by_source[source] = by_source.get(source, 0) + 1
        
        return ActivitySummaryResponse(
            total_activities=len(activities),
            unique_tickets=len(unique_tickets),
            by_action_type=by_action_type,
            by_project=by_project,
            by_source=by_source,
            period_start=start_date.isoformat(),
            period_end=end_date.isoformat(),
        )


@router.post("", response_model=ActivityResponse, status_code=status.HTTP_201_CREATED)
async def create_activity(
    request: ActivityCreateRequest,
    user: CurrentUser,
):
    """Log a new activity manually. Supports both Jira (PROJ-123) and GitHub (owner/repo#123) tickets."""
    db = get_db()
    
    # Parse ticket source and normalize key
    source, normalized_key, detected_project, detected_repo = _parse_ticket_source(
        request.ticket_key, request.github_repo
    )
    
    # Use detected values or provided overrides
    project_key = request.project_key or detected_project
    github_repo = request.github_repo or detected_repo
    
    # Map action type
    try:
        action_enum = ActionType(request.action_type.lower())
    except ValueError:
        action_enum = ActionType.OTHER
    
    with db.session() as session:
        activity = ActivityLog(
            username=user.email,
            user_id=user.id,
            ticket_key=normalized_key,
            ticket_summary=request.ticket_summary,
            ticket_source=source,
            project_key=project_key,
            github_repo=github_repo,
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


@router.patch("/{activity_id}/visibility", response_model=ActivityResponse)
async def update_activity_visibility(
    activity_id: int,
    request: VisibilityUpdateRequest,
    user: CurrentUser,
):
    """Update visibility of an activity to manager (own activities only).
    
    - visible_to_manager=true: Always visible to manager
    - visible_to_manager=false: Always hidden from manager
    - visible_to_manager=null: Inherit from user's visibility preferences
    """
    db = get_db()
    
    with db.session() as session:
        activity = session.query(ActivityLog).filter(ActivityLog.id == activity_id).first()
        if not activity:
            raise HTTPException(status_code=404, detail="Activity not found")
        
        # Check ownership (by username/email or user_id)
        if activity.username != user.email and activity.user_id != user.id:
            if user.role != UserRole.ADMIN:
                raise HTTPException(status_code=403, detail="Can only update visibility of your own activities")
        
        activity.visible_to_manager = request.visible_to_manager
        session.flush()
        
        return activity_to_response(activity)


@router.get("/team/{team_id}", response_model=ActivityListResponse)
async def get_team_activities(
    team_id: int,
    user: Annotated[User, Depends(require_manager_or_admin)],
    start_date: datetime | None = Query(None, description="Filter by start date"),
    end_date: datetime | None = Query(None, description="Filter by end date"),
    project_key: str | None = Query(None, description="Filter by Jira project"),
    ticket_source: str | None = Query(None, description="Filter by source: 'jira' or 'github'"),
    github_repo: str | None = Query(None, description="Filter by GitHub repo"),
    member_id: int | None = Query(None, description="Filter by team member"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Get activities for all members of a team (manager or admin only).
    
    Only returns activities that users have made visible to their manager.
    """
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
        
        # Get members with their preferences for visibility filtering
        members = session.query(User).filter(User.id.in_(member_ids)).all()
        member_emails = [m.email for m in members]
        
        # Build a map of email -> visibility defaults
        email_to_visibility = {
            m.email: _get_user_visibility_defaults(m)
            for m in members
        }
        
        if not member_emails:
            return ActivityListResponse(activities=[], total=0)
        
        # Query activities
        query = session.query(ActivityLog).filter(ActivityLog.username.in_(member_emails))
        
        # Apply date filters
        if start_date:
            query = query.filter(ActivityLog.timestamp >= start_date)
        if end_date:
            query = query.filter(ActivityLog.timestamp <= end_date)
        
        # Apply source filters
        if ticket_source:
            try:
                source_enum = TicketSource(ticket_source.lower())
                query = query.filter(ActivityLog.ticket_source == source_enum)
            except ValueError:
                pass
        if project_key:
            query = query.filter(ActivityLog.project_key == project_key)
        if github_repo:
            query = query.filter(ActivityLog.github_repo == github_repo)
        
        # Get all matching activities (we'll filter by visibility in Python)
        all_activities = query.order_by(ActivityLog.timestamp.desc()).all()
        
        # Filter by visibility
        visible_activities = [
            a for a in all_activities
            if _is_activity_visible_to_manager(a, email_to_visibility.get(a.username, {}))
        ]
        
        # Apply pagination manually after visibility filtering
        total = len(visible_activities)
        paginated_activities = visible_activities[offset:offset + limit]
        
        return ActivityListResponse(
            activities=[activity_to_response(a) for a in paginated_activities],
            total=total,
        )


@router.get("/team/{team_id}/summary", response_model=dict)
async def get_team_activity_summary(
    team_id: int,
    user: Annotated[User, Depends(require_manager_or_admin)],
    days: int = Query(7, ge=1, le=365, description="Number of days to summarize"),
    ticket_source: str | None = Query(None, description="Filter by source: 'jira' or 'github'"),
):
    """Get activity summary for a team (manager or admin only).
    
    Only includes activities that users have made visible to their manager.
    """
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
        
        # Build a map of email -> visibility defaults
        email_to_visibility = {
            m.email: _get_user_visibility_defaults(m)
            for m in members
        }
        
        # Get activities
        query = session.query(ActivityLog).filter(
            ActivityLog.username.in_(member_emails),
            ActivityLog.timestamp >= start_date,
            ActivityLog.timestamp <= end_date,
        )
        
        if ticket_source:
            try:
                source_enum = TicketSource(ticket_source.lower())
                query = query.filter(ActivityLog.ticket_source == source_enum)
            except ValueError:
                pass
        
        all_activities = query.all()
        
        # Filter by visibility
        activities = [
            a for a in all_activities
            if _is_activity_visible_to_manager(a, email_to_visibility.get(a.username, {}))
        ]
        
        # Calculate per-member summaries
        by_member = {}
        total_tickets = set()
        total_by_action = {}
        total_by_source = {"jira": 0, "github": 0}
        
        for a in activities:
            total_tickets.add(a.ticket_key)
            
            action = a.action_type.value if a.action_type else "other"
            total_by_action[action] = total_by_action.get(action, 0) + 1
            
            source = a.ticket_source.value if a.ticket_source else "jira"
            total_by_source[source] = total_by_source.get(source, 0) + 1
            
            if a.username not in by_member:
                by_member[a.username] = {
                    "total_activities": 0,
                    "unique_tickets": set(),
                    "jira_count": 0,
                    "github_count": 0,
                }
            by_member[a.username]["total_activities"] += 1
            by_member[a.username]["unique_tickets"].add(a.ticket_key)
            if source == "jira":
                by_member[a.username]["jira_count"] += 1
            else:
                by_member[a.username]["github_count"] += 1
        
        # Convert sets to counts
        member_summaries = {
            email: {
                "total_activities": data["total_activities"],
                "unique_tickets": len(data["unique_tickets"]),
                "jira_count": data["jira_count"],
                "github_count": data["github_count"],
            }
            for email, data in by_member.items()
        }
        
        return {
            "team_id": team_id,
            "team_name": team.name,
            "total_activities": len(activities),
            "total_unique_tickets": len(total_tickets),
            "by_action_type": total_by_action,
            "by_source": total_by_source,
            "by_member": member_summaries,
            "period_start": start_date.isoformat(),
            "period_end": end_date.isoformat(),
        }
