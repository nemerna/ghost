"""Report management API endpoints."""

import json
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from sqlalchemy.orm import joinedload

from ghost.api.deps import CurrentUser, require_manager_or_admin
from ghost.db import (
    ManagementReport,
    ReportField,
    ReportProject,
    Team,
    TeamMembership,
    User,
    UserRole,
    WeeklyReport,
    get_db,
)
from ghost.tools import reports as report_tools

router = APIRouter()


# =============================================================================
# Pydantic Models
# =============================================================================


class WeeklyReportResponse(BaseModel):
    """Weekly report response model."""
    
    id: int
    username: str
    week_start: str
    week_end: str
    title: str
    summary: str
    content: str
    tickets_count: int
    projects: list[str]
    created_at: str | None
    updated_at: str | None
    visible_to_manager: bool | None = None


class WeeklyReportCreateRequest(BaseModel):
    """Request model for creating/updating a weekly report."""
    
    week_offset: int = 0
    custom_title: str | None = None
    custom_summary: str | None = None


class WeeklyReportListResponse(BaseModel):
    """Response model for weekly report list."""
    
    reports: list[WeeklyReportResponse]
    total: int


class ReportEntry(BaseModel):
    """A single entry in a management report with visibility control."""
    
    text: str
    private: bool = False
    ticket_key: str | None = None  # Associated ticket key for project/component tracking


class ManagementReportResponse(BaseModel):
    """Management report response model."""
    
    id: int
    username: str
    title: str
    project_key: str | None
    report_period: str | None
    content: str  # Raw content (for backwards compat)
    entries: list[ReportEntry] | None = None  # Parsed structured entries
    referenced_tickets: list[str]
    created_at: str | None
    updated_at: str | None
    visible_to_manager: bool | None = None


class VisibilityUpdateRequest(BaseModel):
    """Request model for updating visibility."""
    
    visible_to_manager: bool | None  # None = inherit from user preferences


class ReportEntryInput(BaseModel):
    """Input for a single report entry."""
    
    text: str
    private: bool = False
    ticket_key: str | None = None  # Optional ticket key for auto-detecting visibility


class ManagementReportCreateRequest(BaseModel):
    """Request model for creating a management report."""
    
    title: str
    content: str | None = None  # Legacy plain text content
    entries: list[ReportEntryInput] | None = None  # New structured entries
    project_key: str | None = None
    report_period: str | None = None
    referenced_tickets: list[str] | None = None


class ManagementReportUpdateRequest(BaseModel):
    """Request model for updating a management report."""
    
    title: str | None = None
    content: str | None = None  # Legacy plain text content
    entries: list[ReportEntryInput] | None = None  # New structured entries
    report_period: str | None = None
    referenced_tickets: list[str] | None = None


class ManagementReportListResponse(BaseModel):
    """Response model for management report list."""
    
    reports: list[ManagementReportResponse]
    total: int


class GeneratedReportResponse(BaseModel):
    """Response for a generated (not yet saved) report."""
    
    title: str
    summary: str
    content: str
    week_start: str
    week_end: str
    tickets_count: int
    projects: list[str]
    statistics: dict


# =============================================================================
# Helper Functions
# =============================================================================


def weekly_report_to_response(report: WeeklyReport) -> WeeklyReportResponse:
    """Convert WeeklyReport model to response."""
    return WeeklyReportResponse(
        id=report.id,
        username=report.username,
        week_start=report.week_start.isoformat() if report.week_start else None,
        week_end=report.week_end.isoformat() if report.week_end else None,
        title=report.title,
        summary=report.summary,
        content=report.content,
        tickets_count=report.tickets_count,
        projects=report.projects.split(",") if report.projects else [],
        created_at=report.created_at.isoformat() if report.created_at else None,
        updated_at=report.updated_at.isoformat() if report.updated_at else None,
        visible_to_manager=report.visible_to_manager,
    )


def management_report_to_response(report: ManagementReport) -> ManagementReportResponse:
    """Convert ManagementReport model to response with parsed entries."""
    return management_report_to_response_with_entries(report, filter_private=False)


def _get_user_visibility_defaults(user: User) -> dict:
    """Get visibility defaults from user preferences."""
    preferences = json.loads(user.preferences) if user.preferences else {}
    return preferences.get("visibility_defaults", {
        "activity_logs": "shared",
        "weekly_reports": "shared",
        "management_reports": "private",
    })


def _is_weekly_report_visible_to_manager(report: WeeklyReport, user_visibility_defaults: dict) -> bool:
    """Check if a weekly report is visible to manager based on item override or user defaults."""
    if report.visible_to_manager is not None:
        return report.visible_to_manager
    return user_visibility_defaults.get("weekly_reports", "shared") == "shared"


def _is_management_report_visible_to_manager(report: ManagementReport, user_visibility_defaults: dict) -> bool:
    """Check if a management report is visible to manager based on item override or user defaults."""
    if report.visible_to_manager is not None:
        return report.visible_to_manager
    return user_visibility_defaults.get("management_reports", "private") == "shared"


# =============================================================================
# Structured Entries Helper Functions
# =============================================================================


def _parse_structured_content(content: str) -> list[ReportEntry]:
    """Parse structured content from JSON format.
    
    Returns list of ReportEntry. If content is not valid structured JSON,
    returns an empty list.
    """
    if not content:
        return []
    
    # Check if content is structured JSON format
    content_stripped = content.strip()
    if not content_stripped.startswith('{"format":'):
        return []
    
    try:
        data = json.loads(content)
        if data.get("format") != "structured" or "entries" not in data:
            return []
        
        return [
            ReportEntry(
                text=e.get("text", ""),
                private=e.get("private", False),
                ticket_key=e.get("ticket_key"),
            )
            for e in data.get("entries", [])
        ]
    except (json.JSONDecodeError, TypeError):
        return []


def _serialize_structured_content(entries: list[ReportEntry]) -> str:
    """Serialize structured entries to JSON format for storage."""
    serialized_entries = []
    for e in entries:
        entry_dict = {"text": e.text, "private": e.private}
        if e.ticket_key:
            entry_dict["ticket_key"] = e.ticket_key
        serialized_entries.append(entry_dict)
    return json.dumps({
        "format": "structured",
        "entries": serialized_entries
    })


def _entries_to_markdown(entries: list[ReportEntry]) -> str:
    """Convert structured entries to markdown bullet list for display."""
    if not entries:
        return ""
    return "\n".join(f"- {e.text}" for e in entries)


def _filter_private_entries(entries: list[ReportEntry]) -> list[ReportEntry]:
    """Filter out private entries for manager view."""
    return [e for e in entries if not e.private]


def _get_filtered_content_for_manager(content: str) -> str:
    """Get content with private entries filtered out for manager view.
    
    Returns filtered markdown content from structured entries.
    """
    entries = _parse_structured_content(content)
    # Filter out private entries and convert to markdown
    public_entries = _filter_private_entries(entries)
    return _entries_to_markdown(public_entries)


def _get_filtered_entries_for_manager(content: str) -> list[tuple[int, str]]:
    """Get filtered entries as list of (index, text) tuples for manager view.
    
    Returns list of (original_index, text) for entries that are not private.
    The index represents the position in the original report (before filtering).
    """
    entries = _parse_structured_content(content)
    result = []
    for idx, entry in enumerate(entries):
        if not entry.private:
            result.append((idx, entry.text))
    return result


def management_report_to_response_with_entries(
    report: ManagementReport,
    filter_private: bool = False
) -> ManagementReportResponse:
    """Convert ManagementReport model to response with parsed entries.
    
    Args:
        report: The ManagementReport database model
        filter_private: If True, filter out private entries (for manager view)
    """
    entries = _parse_structured_content(report.content)
    
    if filter_private:
        entries = _filter_private_entries(entries)
        # Also update content to filtered markdown
        content = _entries_to_markdown(entries)
    else:
        content = report.content
    
    return ManagementReportResponse(
        id=report.id,
        username=report.username,
        title=report.title,
        project_key=report.project_key,
        report_period=report.report_period,
        content=content,
        entries=entries,
        referenced_tickets=report.referenced_tickets.split(",") if report.referenced_tickets else [],
        created_at=report.created_at.isoformat() if report.created_at else None,
        updated_at=report.updated_at.isoformat() if report.updated_at else None,
        visible_to_manager=report.visible_to_manager,
    )


# =============================================================================
# Weekly Report Endpoints
# =============================================================================


@router.get("/weekly/my", response_model=WeeklyReportListResponse)
async def get_my_weekly_reports(
    user: CurrentUser,
    limit: int = Query(10, ge=1, le=50),
    offset: int = Query(0, ge=0),
):
    """Get the current user's weekly reports."""
    db = get_db()
    
    with db.session() as session:
        query = session.query(WeeklyReport).filter(WeeklyReport.username == user.email)
        
        total = query.count()
        
        reports = (
            query.order_by(WeeklyReport.week_start.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        
        return WeeklyReportListResponse(
            reports=[weekly_report_to_response(r) for r in reports],
            total=total,
        )


@router.get("/weekly/generate", response_model=GeneratedReportResponse)
async def generate_weekly_report(
    user: CurrentUser,
    week_offset: int = Query(0, ge=-52, le=0, description="Week offset (0=current, -1=last week)"),
):
    """Generate a weekly report preview without saving."""
    result = report_tools.generate_weekly_report(
        username=user.email,
        week_offset=week_offset,
        include_details=True,
    )
    
    return GeneratedReportResponse(
        title=result["title"],
        summary=result["summary"],
        content=result["content"],
        week_start=result["week_start"],
        week_end=result["week_end"],
        tickets_count=result["tickets_count"],
        projects=result["projects"],
        statistics=result["statistics"],
    )


@router.post("/weekly", response_model=dict)
async def save_weekly_report(
    request: WeeklyReportCreateRequest,
    user: CurrentUser,
):
    """Save a weekly report."""
    result = report_tools.save_weekly_report(
        username=user.email,
        week_offset=request.week_offset,
        custom_title=request.custom_title,
        custom_summary=request.custom_summary,
    )
    
    return result


@router.get("/weekly/{report_id}", response_model=WeeklyReportResponse)
async def get_weekly_report(
    report_id: int,
    user: CurrentUser,
):
    """Get a specific weekly report."""
    db = get_db()
    
    with db.session() as session:
        report = session.query(WeeklyReport).filter(WeeklyReport.id == report_id).first()
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")
        
        # Check access (own report, manager of team, or admin)
        if report.username != user.email and user.role != UserRole.ADMIN:
            # Check if user is manager of a team that includes the report author
            # This is a simplified check - in production you might want more robust logic
            if user.role != UserRole.MANAGER:
                raise HTTPException(status_code=403, detail="Access denied")
        
        return weekly_report_to_response(report)


@router.delete("/weekly/{report_id}")
async def delete_weekly_report(
    report_id: int,
    user: CurrentUser,
):
    """Delete a weekly report (own reports only)."""
    db = get_db()
    
    with db.session() as session:
        report = session.query(WeeklyReport).filter(WeeklyReport.id == report_id).first()
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")
        
        if report.username != user.email and user.role != UserRole.ADMIN:
            raise HTTPException(status_code=403, detail="Can only delete your own reports")
        
        session.delete(report)
    
    return {"message": "Report deleted successfully"}


@router.patch("/weekly/{report_id}/visibility", response_model=WeeklyReportResponse)
async def update_weekly_report_visibility(
    report_id: int,
    request: VisibilityUpdateRequest,
    user: CurrentUser,
):
    """Update visibility of a weekly report to manager (own reports only).
    
    - visible_to_manager=true: Always visible to manager
    - visible_to_manager=false: Always hidden from manager
    - visible_to_manager=null: Inherit from user's visibility preferences
    """
    db = get_db()
    
    with db.session() as session:
        report = session.query(WeeklyReport).filter(WeeklyReport.id == report_id).first()
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")
        
        if report.username != user.email and user.role != UserRole.ADMIN:
            raise HTTPException(status_code=403, detail="Can only update visibility of your own reports")
        
        report.visible_to_manager = request.visible_to_manager
        session.flush()
        
        return weekly_report_to_response(report)


@router.get("/weekly/team/{team_id}", response_model=WeeklyReportListResponse)
async def get_team_weekly_reports(
    team_id: int,
    user: Annotated[User, Depends(require_manager_or_admin)],
    week_start: datetime | None = Query(None, description="Filter by week start date"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Get weekly reports for all team members (manager or admin only).
    
    Only returns reports that users have made visible to their manager.
    """
    db = get_db()
    
    with db.session() as session:
        # Verify team and access
        team = session.query(Team).filter(Team.id == team_id).first()
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")
        
        if user.role != UserRole.ADMIN and team.manager_id != user.id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Get team member emails
        memberships = session.query(TeamMembership).filter(TeamMembership.team_id == team_id).all()
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
        
        # Query reports
        query = session.query(WeeklyReport).filter(WeeklyReport.username.in_(member_emails))
        
        if week_start:
            query = query.filter(WeeklyReport.week_start == week_start)
        
        all_reports = query.order_by(WeeklyReport.week_start.desc(), WeeklyReport.username).all()
        
        # Filter by visibility
        visible_reports = [
            r for r in all_reports
            if _is_weekly_report_visible_to_manager(r, email_to_visibility.get(r.username, {}))
        ]
        
        # Apply pagination manually after visibility filtering
        total = len(visible_reports)
        paginated_reports = visible_reports[offset:offset + limit]
        
        return WeeklyReportListResponse(
            reports=[weekly_report_to_response(r) for r in paginated_reports],
            total=total,
        )


# =============================================================================
# Management Report Endpoints
# =============================================================================


@router.get("/management", response_model=ManagementReportListResponse)
async def list_management_reports(
    user: CurrentUser,
    project_key: str | None = Query(None, description="Filter by project"),
    author: str | None = Query(None, description="Filter by author email"),
    limit: int = Query(10, ge=1, le=50),
    offset: int = Query(0, ge=0),
):
    """List management reports."""
    db = get_db()
    
    with db.session() as session:
        query = session.query(ManagementReport)
        
        # Non-admins only see their own reports by default
        if user.role != UserRole.ADMIN and user.role != UserRole.MANAGER:
            query = query.filter(ManagementReport.username == user.email)
        elif author:
            query = query.filter(ManagementReport.username == author)
        
        if project_key:
            query = query.filter(ManagementReport.project_key == project_key)
        
        total = query.count()
        
        reports = (
            query.order_by(ManagementReport.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        
        return ManagementReportListResponse(
            reports=[management_report_to_response(r) for r in reports],
            total=total,
        )


@router.post("/management", response_model=ManagementReportResponse, status_code=status.HTTP_201_CREATED)
async def create_management_report(
    request: ManagementReportCreateRequest,
    user: CurrentUser,
):
    """Create a new management report.
    
    Supports both legacy plain text content and structured entries format.
    If entries are provided, they are serialized to JSON for storage.
    """
    db = get_db()
    
    # Determine content to store
    if request.entries is not None:
        # Convert structured entries to JSON content, auto-detecting ticket_key if not provided
        entries = []
        for e in request.entries:
            ticket_key = e.ticket_key
            if not ticket_key and e.text:
                ticket_key = report_tools._extract_ticket_key_from_text(e.text)
            entries.append(ReportEntry(text=e.text, private=e.private, ticket_key=ticket_key))
        content = _serialize_structured_content(entries)
    elif request.content is not None:
        content = request.content
    else:
        content = ""
    
    with db.session() as session:
        report = ManagementReport(
            username=user.email,
            title=request.title,
            content=content,
            project_key=request.project_key,
            report_period=request.report_period,
            referenced_tickets=",".join(request.referenced_tickets) if request.referenced_tickets else None,
            created_at=datetime.utcnow(),
        )
        session.add(report)
        session.flush()
        
        return management_report_to_response(report)


# NOTE: Team routes must be defined BEFORE individual report routes
# to avoid FastAPI matching "/management/team/1" as "/management/{report_id}"
@router.get("/management/team/{team_id}", response_model=ManagementReportListResponse)
async def get_team_management_reports(
    team_id: int,
    user: Annotated[User, Depends(require_manager_or_admin)],
    report_period: str | None = Query(None, description="Filter by report period"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Get management reports from all team members (manager or admin only).
    
    Only returns reports that users have made visible to their manager.
    """
    db = get_db()
    
    with db.session() as session:
        # Verify team and access
        team = session.query(Team).filter(Team.id == team_id).first()
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")
        
        if user.role != UserRole.ADMIN and team.manager_id != user.id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Get team member emails
        memberships = session.query(TeamMembership).filter(TeamMembership.team_id == team_id).all()
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
        
        # Query management reports from team members
        query = session.query(ManagementReport).filter(ManagementReport.username.in_(member_emails))
        
        if report_period:
            query = query.filter(ManagementReport.report_period == report_period)
        
        all_reports = query.order_by(ManagementReport.created_at.desc()).all()
        
        # Filter by visibility
        visible_reports = [
            r for r in all_reports
            if _is_management_report_visible_to_manager(r, email_to_visibility.get(r.username, {}))
        ]
        
        # Apply pagination manually after visibility filtering
        total = len(visible_reports)
        paginated_reports = visible_reports[offset:offset + limit]
        
        # Filter private entries from each report for manager view
        return ManagementReportListResponse(
            reports=[management_report_to_response_with_entries(r, filter_private=True) for r in paginated_reports],
            total=total,
        )


@router.get("/management/aggregate/{team_id}", response_model=dict)
async def get_team_report_aggregate(
    team_id: int,
    user: Annotated[User, Depends(require_manager_or_admin)],
    week_offset: int = Query(0, ge=-52, le=0, description="Week offset"),
):
    """Get aggregated data from team members' weekly reports for management report creation.
    
    Only includes reports that users have made visible to their manager.
    """
    db = get_db()
    
    # Calculate week boundaries
    today = datetime.utcnow().date()
    current_monday = today - timedelta(days=today.weekday())
    target_monday = current_monday + timedelta(weeks=week_offset)
    target_sunday = target_monday + timedelta(days=6)
    
    week_start = datetime.combine(target_monday, datetime.min.time())
    week_end = datetime.combine(target_sunday, datetime.max.time())
    
    with db.session() as session:
        # Verify team and access
        team = session.query(Team).filter(Team.id == team_id).first()
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")
        
        if user.role != UserRole.ADMIN and team.manager_id != user.id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Get team member emails
        memberships = session.query(TeamMembership).filter(TeamMembership.team_id == team_id).all()
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
        
        # Get weekly reports for this period
        all_reports = (
            session.query(WeeklyReport)
            .filter(
                WeeklyReport.username.in_(member_emails),
                WeeklyReport.week_start >= week_start,
                WeeklyReport.week_start <= week_end,
            )
            .all()
        )
        
        # Filter by visibility
        reports = [
            r for r in all_reports
            if _is_weekly_report_visible_to_manager(r, email_to_visibility.get(r.username, {}))
        ]
        
        # Aggregate data
        total_tickets = 0
        all_projects = set()
        member_summaries = []
        
        for report in reports:
            total_tickets += report.tickets_count
            if report.projects:
                all_projects.update(report.projects.split(","))
            
            member_summaries.append({
                "username": report.username,
                "title": report.title,
                "summary": report.summary,
                "tickets_count": report.tickets_count,
            })
        
        return {
            "team_id": team_id,
            "team_name": team.name,
            "week_start": week_start.date().isoformat(),
            "week_end": week_end.date().isoformat(),
            "total_members": len(member_emails),
            "reports_submitted": len(reports),
            "total_tickets": total_tickets,
            "all_projects": list(all_projects),
            "member_summaries": member_summaries,
        }


# Individual management report routes (must be after team routes)
@router.get("/management/{report_id}", response_model=ManagementReportResponse)
async def get_management_report(
    report_id: int,
    user: CurrentUser,
):
    """Get a specific management report."""
    db = get_db()
    
    with db.session() as session:
        report = session.query(ManagementReport).filter(ManagementReport.id == report_id).first()
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")
        
        # Access check - own report, manager, or admin
        if report.username != user.email:
            if user.role not in [UserRole.MANAGER, UserRole.ADMIN]:
                raise HTTPException(status_code=403, detail="Access denied")
        
        return management_report_to_response(report)


@router.put("/management/{report_id}", response_model=ManagementReportResponse)
async def update_management_report(
    report_id: int,
    request: ManagementReportUpdateRequest,
    user: CurrentUser,
):
    """Update a management report.
    
    Supports both legacy plain text content and structured entries format.
    If entries are provided, they are serialized to JSON for storage.
    """
    db = get_db()
    
    with db.session() as session:
        report = session.query(ManagementReport).filter(ManagementReport.id == report_id).first()
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")
        
        # Only author or admin can update
        if report.username != user.email and user.role != UserRole.ADMIN:
            raise HTTPException(status_code=403, detail="Can only update your own reports")
        
        if request.title is not None:
            report.title = request.title
        
        # Handle content update - prefer entries over plain content
        if request.entries is not None:
            # Auto-detect ticket_key if not provided
            entries = []
            for e in request.entries:
                ticket_key = e.ticket_key
                if not ticket_key and e.text:
                    ticket_key = report_tools._extract_ticket_key_from_text(e.text)
                entries.append(ReportEntry(text=e.text, private=e.private, ticket_key=ticket_key))
            report.content = _serialize_structured_content(entries)
        elif request.content is not None:
            report.content = request.content
        
        if request.report_period is not None:
            report.report_period = request.report_period
        if request.referenced_tickets is not None:
            report.referenced_tickets = ",".join(request.referenced_tickets)
        
        report.updated_at = datetime.utcnow()
        session.flush()
        
        return management_report_to_response(report)


@router.delete("/management/{report_id}")
async def delete_management_report(
    report_id: int,
    user: CurrentUser,
):
    """Delete a management report."""
    db = get_db()
    
    with db.session() as session:
        report = session.query(ManagementReport).filter(ManagementReport.id == report_id).first()
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")
        
        if report.username != user.email and user.role != UserRole.ADMIN:
            raise HTTPException(status_code=403, detail="Can only delete your own reports")
        
        session.delete(report)
    
    return {"message": "Report deleted successfully"}


@router.patch("/management/{report_id}/visibility", response_model=ManagementReportResponse)
async def update_management_report_visibility(
    report_id: int,
    request: VisibilityUpdateRequest,
    user: CurrentUser,
):
    """Update visibility of a management report to manager (own reports only).
    
    - visible_to_manager=true: Always visible to manager
    - visible_to_manager=false: Always hidden from manager
    - visible_to_manager=null: Inherit from user's visibility preferences
    """
    db = get_db()
    
    with db.session() as session:
        report = session.query(ManagementReport).filter(ManagementReport.id == report_id).first()
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")
        
        if report.username != user.email and user.role != UserRole.ADMIN:
            raise HTTPException(status_code=403, detail="Can only update visibility of your own reports")
        
        report.visible_to_manager = request.visible_to_manager
        session.flush()
        
        return management_report_to_response(report)


# =============================================================================
# Consolidated Report Models
# =============================================================================


class ConsolidatedUserEntry(BaseModel):
    """A single parsed entry from a user's report."""
    
    text: str
    index: int  # Position in the original report


class ConsolidatedEntry(BaseModel):
    """A single user's report in the consolidated view with parsed entries."""

    username: str
    report_id: int
    title: str
    content: str  # Combined markdown (for display/backwards compat)
    entries: list[ConsolidatedUserEntry]  # Individual entries for editing
    report_period: str | None
    created_at: str | None


class ConsolidatedProject(BaseModel):
    """Project with its entries in consolidated view (supports hierarchy)."""

    id: int
    name: str
    description: str | None
    parent_id: int | None = None
    is_leaf: bool = True
    entries: list[ConsolidatedEntry]  # Only populated for leaf projects
    children: list["ConsolidatedProject"] = []  # Nested subprojects


class ConsolidatedField(BaseModel):
    """Field with its projects (hierarchical) in consolidated view."""

    id: int
    name: str
    description: str | None
    projects: list[ConsolidatedProject]  # Top-level projects (with nested children)


class ConsolidatedReportResponse(BaseModel):
    """Response model for consolidated report."""

    team_id: int
    team_name: str
    report_period: str | None
    fields: list[ConsolidatedField]
    uncategorized: list[ConsolidatedEntry]
    total_entries: int


# =============================================================================
# Consolidated Report Endpoints
# =============================================================================


@router.get("/consolidated/{team_id}", response_model=ConsolidatedReportResponse)
async def get_consolidated_report(
    team_id: int,
    user: Annotated[User, Depends(require_manager_or_admin)],
    report_period: str | None = Query(None, description="Filter by report period"),
    limit: int = Query(100, ge=1, le=500),
):
    """Get consolidated management reports grouped by Field → Project → Entries.
    
    This endpoint aggregates team management reports and groups them based on
    the detected_project_id that was auto-assigned to referenced activities.
    
    Reports are organized as:
    - Fields (top level)
      - Projects (under each field)
        - Entries (reports from team members assigned to this project)
    - Uncategorized (reports with no detected project)
    
    Only includes reports that users have made visible to their manager.
    """
    db = get_db()

    with db.session() as session:
        # Verify team and access
        team = session.query(Team).filter(Team.id == team_id).first()
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")

        if user.role != UserRole.ADMIN and team.manager_id != user.id:
            raise HTTPException(status_code=403, detail="Access denied")

        # Get team member emails
        memberships = session.query(TeamMembership).filter(TeamMembership.team_id == team_id).all()
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

        # Get management reports from team members
        query = session.query(ManagementReport).filter(ManagementReport.username.in_(member_emails))

        if report_period:
            query = query.filter(ManagementReport.report_period == report_period)

        all_reports = query.order_by(ManagementReport.created_at.desc()).limit(limit).all()
        
        # Filter by visibility
        reports = [
            r for r in all_reports
            if _is_management_report_visible_to_manager(r, email_to_visibility.get(r.username, {}))
        ]

        # Get the latest report per user (for consolidation)
        latest_by_user: dict[str, ManagementReport] = {}
        for report in reports:
            if report.username not in latest_by_user:
                latest_by_user[report.username] = report
            elif report.created_at and latest_by_user[report.username].created_at:
                if report.created_at > latest_by_user[report.username].created_at:
                    latest_by_user[report.username] = report

        # Get all fields with projects (including nested hierarchy)
        fields = (
            session.query(ReportField)
            .options(joinedload(ReportField.projects))
            .order_by(ReportField.display_order)
            .all()
        )

        # Build project ID to field/project mapping (includes all projects, nested or not)
        project_to_field: dict[int, tuple[ReportField, ReportProject]] = {}
        for field in fields:
            for project in field.projects:
                project_to_field[project.id] = (field, project)

        # Group individual report entries by detected project
        # Each entry is assigned to its ticket's detected_project_id
        from ghost.db import ActivityLog

        entries_by_project: dict[int, list[ConsolidatedEntry]] = {}
        uncategorized_entries: list[ConsolidatedEntry] = []

        for username, report in latest_by_user.items():
            # Parse structured content to get entries with ticket_keys
            parsed_entries = _parse_structured_content(report.content)
            
            # Build a map of ticket_key -> detected_project_id
            ticket_to_project: dict[str, int | None] = {}
            all_ticket_keys = set()
            
            for entry in parsed_entries:
                if entry.ticket_key:
                    all_ticket_keys.add(entry.ticket_key)
            
            if all_ticket_keys:
                # Query activities to get detected_project_id for each ticket
                activities = (
                    session.query(ActivityLog.ticket_key, ActivityLog.detected_project_id)
                    .filter(
                        ActivityLog.ticket_key.in_(all_ticket_keys),
                    )
                    .order_by(ActivityLog.timestamp.desc())
                    .all()
                )
                
                # Use the most recent activity for each ticket
                for ticket_key, proj_id in activities:
                    if ticket_key not in ticket_to_project:
                        ticket_to_project[ticket_key] = proj_id
            
            # Group entries by project
            entries_grouped_by_project: dict[int | None, list[tuple[int, str]]] = {}
            
            for idx, entry in enumerate(parsed_entries):
                # Skip private entries for manager view
                if entry.private:
                    continue
                    
                proj_id = ticket_to_project.get(entry.ticket_key) if entry.ticket_key else None
                
                if proj_id not in entries_grouped_by_project:
                    entries_grouped_by_project[proj_id] = []
                entries_grouped_by_project[proj_id].append((idx, entry.text))
            
            # Create ConsolidatedEntry for each project group
            for proj_id, proj_entries in entries_grouped_by_project.items():
                consolidated_entry = ConsolidatedEntry(
                    username=username,
                    report_id=report.id,
                    title=report.title,
                    content="\n".join(f"- {text}" for _, text in proj_entries),
                    entries=[
                        ConsolidatedUserEntry(text=text, index=idx)
                        for idx, text in proj_entries
                    ],
                    report_period=report.report_period,
                    created_at=report.created_at.isoformat() if report.created_at else None,
                )
                
                if proj_id and proj_id in project_to_field:
                    if proj_id not in entries_by_project:
                        entries_by_project[proj_id] = []
                    entries_by_project[proj_id].append(consolidated_entry)
                else:
                    uncategorized_entries.append(consolidated_entry)

        # Build the response structure with hierarchical projects
        def build_consolidated_project_tree(
            projects: list, 
            parent_id: int | None,
            entries_by_project: dict[int, list[ConsolidatedEntry]]
        ) -> list[ConsolidatedProject]:
            """Recursively build consolidated project tree."""
            result = []
            level_projects = sorted(
                [p for p in projects if p.parent_id == parent_id],
                key=lambda p: p.display_order
            )
            
            for project in level_projects:
                children = build_consolidated_project_tree(
                    projects, project.id, entries_by_project
                )
                is_leaf = len(children) == 0
                project_entries = entries_by_project.get(project.id, []) if is_leaf else []
                
                # Include project if it has entries or any descendant has entries
                has_entries = len(project_entries) > 0
                has_child_entries = any(
                    len(c.entries) > 0 or len(c.children) > 0 
                    for c in children
                )
                
                if has_entries or has_child_entries:
                    result.append(
                        ConsolidatedProject(
                            id=project.id,
                            name=project.name,
                            description=project.description,
                            parent_id=project.parent_id,
                            is_leaf=is_leaf,
                            entries=project_entries,
                            children=children,
                        )
                    )
            
            return result
        
        consolidated_fields: list[ConsolidatedField] = []

        for field in fields:
            # Build hierarchical project tree for this field
            field_projects = build_consolidated_project_tree(
                list(field.projects), None, entries_by_project
            )

            if field_projects:  # Only include fields with projects that have entries
                consolidated_fields.append(
                    ConsolidatedField(
                        id=field.id,
                        name=field.name,
                        description=field.description,
                        projects=field_projects,
                    )
                )

        def count_entries_recursive(projects: list[ConsolidatedProject]) -> int:
            """Count entries across all projects including nested children."""
            total = 0
            for p in projects:
                total += len(p.entries)
                total += count_entries_recursive(p.children)
            return total
        
        total_entries = sum(
            count_entries_recursive(f.projects) for f in consolidated_fields
        ) + len(uncategorized_entries)

        response = ConsolidatedReportResponse(
            team_id=team_id,
            team_name=team.name,
            report_period=report_period,
            fields=consolidated_fields,
            uncategorized=uncategorized_entries,
            total_entries=total_entries,
        )

        # Auto-save snapshot on first view of this period (if there are entries)
        if total_entries > 0:
            from ghost.db import ConsolidatedReportSnapshot, SnapshotType
            
            # Determine the report period to use for snapshot
            # If not specified, use the current week
            snapshot_period = report_period
            if not snapshot_period:
                from datetime import datetime
                now = datetime.utcnow()
                week_num = now.isocalendar()[1]
                snapshot_period = f"Week {week_num}, {now.strftime('%b %Y')}"
            
            # Check if an auto-snapshot already exists for this period
            existing = session.query(ConsolidatedReportSnapshot).filter(
                ConsolidatedReportSnapshot.team_id == team_id,
                ConsolidatedReportSnapshot.report_period == snapshot_period,
                ConsolidatedReportSnapshot.snapshot_type == SnapshotType.AUTO,
            ).first()
            
            if not existing:
                # Create auto-snapshot
                snapshot = ConsolidatedReportSnapshot(
                    team_id=team_id,
                    created_by_id=user.id,
                    report_period=snapshot_period,
                    snapshot_type=SnapshotType.AUTO,
                    label=None,
                    content=json.dumps(response.model_dump()),
                )
                session.add(snapshot)

        return response


@router.get("/consolidated/{team_id}/filtered", response_model=ConsolidatedReportResponse)
async def get_filtered_consolidated_report(
    team_id: int,
    user: Annotated[User, Depends(require_manager_or_admin)],
    field_ids: str | None = Query(None, description="Comma-separated field IDs to include"),
    project_ids: str | None = Query(None, description="Comma-separated project IDs to include"),
    report_period: str | None = Query(None, description="Filter by report period"),
    limit: int = Query(100, ge=1, le=500),
):
    """Get a filtered consolidated report with only specified fields/projects.
    
    This endpoint returns a subset of the consolidated report based on the
    specified field IDs and/or project IDs. Useful for creating sub-reports
    for different stakeholders.
    
    - If field_ids is specified, only include those fields
    - If project_ids is specified, only include those projects (within selected fields)
    - If both are empty, returns the full report (same as main endpoint)
    """
    # Parse filter parameters
    filter_field_ids: set[int] = set()
    filter_project_ids: set[int] = set()
    
    if field_ids:
        try:
            filter_field_ids = {int(x.strip()) for x in field_ids.split(",") if x.strip()}
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid field_ids format")
    
    if project_ids:
        try:
            filter_project_ids = {int(x.strip()) for x in project_ids.split(",") if x.strip()}
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid project_ids format")
    
    # Get the full consolidated report
    full_report = await get_consolidated_report(
        team_id=team_id,
        user=user,
        report_period=report_period,
        limit=limit,
    )
    
    # If no filters, return full report
    if not filter_field_ids and not filter_project_ids:
        return full_report
    
    # Apply filters with support for hierarchical projects
    def filter_projects_recursive(
        projects: list[ConsolidatedProject],
        filter_ids: set[int] | None
    ) -> list[ConsolidatedProject]:
        """Recursively filter projects, keeping those that match or have matching descendants."""
        result = []
        for project in projects:
            # Recursively filter children
            filtered_children = filter_projects_recursive(project.children, filter_ids)
            
            # Include project if:
            # - No filter specified
            # - Project is in the filter list
            # - Any descendant is in the filter list (filtered_children not empty)
            should_include = (
                not filter_ids or 
                project.id in filter_ids or 
                len(filtered_children) > 0
            )
            
            if should_include:
                result.append(
                    ConsolidatedProject(
                        id=project.id,
                        name=project.name,
                        description=project.description,
                        parent_id=project.parent_id,
                        is_leaf=project.is_leaf,
                        entries=project.entries,
                        children=filtered_children,
                    )
                )
        return result
    
    filtered_fields: list[ConsolidatedField] = []
    
    for field in full_report.fields:
        # Check if field should be included
        if filter_field_ids and field.id not in filter_field_ids:
            continue
        
        # Filter projects within this field (recursively handles hierarchy)
        filtered_projects = filter_projects_recursive(
            field.projects, 
            filter_project_ids if filter_project_ids else None
        )
        
        # Only include field if it has projects after filtering
        if filtered_projects:
            filtered_fields.append(
                ConsolidatedField(
                    id=field.id,
                    name=field.name,
                    description=field.description,
                    projects=filtered_projects,
                )
            )
    
    # Recalculate total entries (recursively)
    def count_entries_recursive(projects: list[ConsolidatedProject]) -> int:
        total = 0
        for p in projects:
            total += len(p.entries)
            total += count_entries_recursive(p.children)
        return total
    
    total_entries = sum(count_entries_recursive(f.projects) for f in filtered_fields)
    
    # Note: uncategorized entries are excluded from filtered reports
    # since they don't belong to any specific field/project
    
    return ConsolidatedReportResponse(
        team_id=full_report.team_id,
        team_name=full_report.team_name,
        report_period=full_report.report_period,
        fields=filtered_fields,
        uncategorized=[],  # Exclude uncategorized from filtered reports
        total_entries=total_entries,
    )


# =============================================================================
# Consolidated Report Draft Models
# =============================================================================


class ConsolidatedDraftEntry(BaseModel):
    """A single entry in a consolidated draft."""

    text: str
    original_report_id: int | None = None
    original_username: str | None = None
    is_manager_added: bool = False


class ConsolidatedDraftProject(BaseModel):
    """Project with entries in a consolidated draft."""

    id: int
    name: str
    entries: list[ConsolidatedDraftEntry]


class ConsolidatedDraftField(BaseModel):
    """Field with projects in a consolidated draft."""

    id: int
    name: str
    projects: list[ConsolidatedDraftProject]


class ConsolidatedDraftContent(BaseModel):
    """Content structure for a consolidated draft."""

    format: str = "consolidated_v1"
    fields: list[ConsolidatedDraftField]
    uncategorized: list[ConsolidatedDraftEntry] = []


class ConsolidatedDraftResponse(BaseModel):
    """Response model for a consolidated draft."""

    id: int
    team_id: int
    manager_id: int
    title: str
    report_period: str | None
    content: ConsolidatedDraftContent
    created_at: str | None
    updated_at: str | None


class ConsolidatedDraftListResponse(BaseModel):
    """Response model for listing consolidated drafts."""

    drafts: list[ConsolidatedDraftResponse]
    total: int


class ConsolidatedDraftCreateRequest(BaseModel):
    """Request model for creating a consolidated draft."""

    title: str
    report_period: str | None = None
    content: ConsolidatedDraftContent | None = None  # If None, will initialize from current consolidated data


class ConsolidatedDraftUpdateRequest(BaseModel):
    """Request model for updating a consolidated draft."""

    title: str | None = None
    report_period: str | None = None
    content: ConsolidatedDraftContent | None = None


# =============================================================================
# Consolidated Report Draft Endpoints
# =============================================================================


def _draft_to_response(draft) -> ConsolidatedDraftResponse:
    """Convert a ConsolidatedReportDraft model to response."""
    content_data = json.loads(draft.content) if draft.content else {"format": "consolidated_v1", "fields": [], "uncategorized": []}
    
    return ConsolidatedDraftResponse(
        id=draft.id,
        team_id=draft.team_id,
        manager_id=draft.manager_id,
        title=draft.title,
        report_period=draft.report_period,
        content=ConsolidatedDraftContent(**content_data),
        created_at=draft.created_at.isoformat() if draft.created_at else None,
        updated_at=draft.updated_at.isoformat() if draft.updated_at else None,
    )


@router.get("/consolidated-drafts/{team_id}", response_model=ConsolidatedDraftListResponse)
async def list_consolidated_drafts(
    team_id: int,
    user: Annotated[User, Depends(require_manager_or_admin)],
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """List consolidated drafts for a team.
    
    Only the manager of the team (or admin) can view drafts.
    """
    from ghost.db import ConsolidatedReportDraft
    
    db = get_db()

    with db.session() as session:
        # Verify team and access
        team = session.query(Team).filter(Team.id == team_id).first()
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")

        if user.role != UserRole.ADMIN and team.manager_id != user.id:
            raise HTTPException(status_code=403, detail="Access denied")

        # Query drafts for this team owned by the current user (or all for admin)
        query = session.query(ConsolidatedReportDraft).filter(
            ConsolidatedReportDraft.team_id == team_id
        )
        
        # Non-admins only see their own drafts
        if user.role != UserRole.ADMIN:
            query = query.filter(ConsolidatedReportDraft.manager_id == user.id)

        total = query.count()
        
        drafts = (
            query.order_by(ConsolidatedReportDraft.updated_at.desc(), ConsolidatedReportDraft.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        return ConsolidatedDraftListResponse(
            drafts=[_draft_to_response(d) for d in drafts],
            total=total,
        )


@router.get("/consolidated-drafts/{team_id}/{draft_id}", response_model=ConsolidatedDraftResponse)
async def get_consolidated_draft(
    team_id: int,
    draft_id: int,
    user: Annotated[User, Depends(require_manager_or_admin)],
):
    """Get a specific consolidated draft.
    
    Only the manager who created the draft (or admin) can view it.
    """
    from ghost.db import ConsolidatedReportDraft
    
    db = get_db()

    with db.session() as session:
        # Verify team and access
        team = session.query(Team).filter(Team.id == team_id).first()
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")

        if user.role != UserRole.ADMIN and team.manager_id != user.id:
            raise HTTPException(status_code=403, detail="Access denied")

        draft = session.query(ConsolidatedReportDraft).filter(
            ConsolidatedReportDraft.id == draft_id,
            ConsolidatedReportDraft.team_id == team_id,
        ).first()
        
        if not draft:
            raise HTTPException(status_code=404, detail="Draft not found")

        # Non-admins can only see their own drafts
        if user.role != UserRole.ADMIN and draft.manager_id != user.id:
            raise HTTPException(status_code=403, detail="Access denied")

        return _draft_to_response(draft)


@router.post("/consolidated-drafts/{team_id}", response_model=ConsolidatedDraftResponse, status_code=status.HTTP_201_CREATED)
async def create_consolidated_draft(
    team_id: int,
    request: ConsolidatedDraftCreateRequest,
    user: Annotated[User, Depends(require_manager_or_admin)],
):
    """Create a new consolidated draft.
    
    If content is not provided, initializes from current consolidated report data.
    The draft captures the current state of team members' reports for editing.
    """
    from ghost.db import ConsolidatedReportDraft
    
    db = get_db()

    with db.session() as session:
        # Verify team and access
        team = session.query(Team).filter(Team.id == team_id).first()
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")

        if user.role != UserRole.ADMIN and team.manager_id != user.id:
            raise HTTPException(status_code=403, detail="Access denied")

        # Get content - either provided or initialized from current consolidated data
        if request.content:
            content_json = json.dumps(request.content.model_dump())
        else:
            # Initialize from current consolidated report
            # Fetch current consolidated data and convert to draft format
            content = await _get_consolidated_as_draft_content(session, team_id, user)
            content_json = json.dumps(content)

        draft = ConsolidatedReportDraft(
            team_id=team_id,
            manager_id=user.id,
            title=request.title,
            report_period=request.report_period,
            content=content_json,
            created_at=datetime.utcnow(),
        )
        session.add(draft)
        session.flush()

        return _draft_to_response(draft)


async def _get_consolidated_as_draft_content(session, team_id: int, user: User) -> dict:
    """Get current consolidated report data formatted as draft content.
    
    This converts the live consolidated data into editable draft format.
    """
    from ghost.db import ActivityLog
    
    # Get team member emails
    memberships = session.query(TeamMembership).filter(TeamMembership.team_id == team_id).all()
    member_ids = [m.user_id for m in memberships]
    
    team = session.query(Team).filter(Team.id == team_id).first()
    if team and team.manager_id:
        member_ids.append(team.manager_id)

    members = session.query(User).filter(User.id.in_(member_ids)).all()
    member_emails = [m.email for m in members]
    
    # Build visibility map
    email_to_visibility = {
        m.email: _get_user_visibility_defaults(m)
        for m in members
    }

    # Get management reports from team members
    all_reports = (
        session.query(ManagementReport)
        .filter(ManagementReport.username.in_(member_emails))
        .order_by(ManagementReport.created_at.desc())
        .limit(100)
        .all()
    )
    
    # Filter by visibility
    reports = [
        r for r in all_reports
        if _is_management_report_visible_to_manager(r, email_to_visibility.get(r.username, {}))
    ]

    # Get latest report per user
    latest_by_user: dict[str, ManagementReport] = {}
    for report in reports:
        if report.username not in latest_by_user:
            latest_by_user[report.username] = report
        elif report.created_at and latest_by_user[report.username].created_at:
            if report.created_at > latest_by_user[report.username].created_at:
                latest_by_user[report.username] = report

    # Get all fields with projects
    fields = (
        session.query(ReportField)
        .options(joinedload(ReportField.projects))
        .order_by(ReportField.display_order)
        .all()
    )

    # Build project ID to field/project mapping
    project_to_field: dict[int, tuple[ReportField, ReportProject]] = {}
    for field in fields:
        for project in field.projects:
            project_to_field[project.id] = (field, project)

    # Group individual report entries by detected project
    entries_by_project: dict[int, list[dict]] = {}
    uncategorized_entries: list[dict] = []

    for username, report in latest_by_user.items():
        # Parse structured content to get entries with ticket_keys
        parsed_entries = _parse_structured_content(report.content)
        
        # Build a map of ticket_key -> detected_project_id
        ticket_to_project: dict[str, int | None] = {}
        all_ticket_keys = set()
        
        for entry in parsed_entries:
            if entry.ticket_key:
                all_ticket_keys.add(entry.ticket_key)
        
        if all_ticket_keys:
            # Query activities to get detected_project_id for each ticket
            activities = (
                session.query(ActivityLog.ticket_key, ActivityLog.detected_project_id)
                .filter(
                    ActivityLog.ticket_key.in_(all_ticket_keys),
                )
                .order_by(ActivityLog.timestamp.desc())
                .all()
            )
            
            # Use the most recent activity for each ticket
            for ticket_key, proj_id in activities:
                if ticket_key not in ticket_to_project:
                    ticket_to_project[ticket_key] = proj_id
        
        # Group entries by project
        entries_grouped_by_project: dict[int | None, list[str]] = {}
        
        for entry in parsed_entries:
            # Skip private entries for manager view
            if entry.private:
                continue
                
            proj_id = ticket_to_project.get(entry.ticket_key) if entry.ticket_key else None
            
            if proj_id not in entries_grouped_by_project:
                entries_grouped_by_project[proj_id] = []
            entries_grouped_by_project[proj_id].append(entry.text)
        
        # Create draft entry for each project group
        for proj_id, proj_entry_texts in entries_grouped_by_project.items():
            draft_entry = {
                "text": "\n".join(f"- {text}" for text in proj_entry_texts),
                "original_report_id": report.id,
                "original_username": username,
                "is_manager_added": False,
            }
            
            if proj_id and proj_id in project_to_field:
                if proj_id not in entries_by_project:
                    entries_by_project[proj_id] = []
                entries_by_project[proj_id].append(draft_entry)
            else:
                uncategorized_entries.append(draft_entry)

    # Build draft content structure
    draft_fields: list[dict] = []
    for field in fields:
        field_projects: list[dict] = []
        for project in sorted(field.projects, key=lambda p: p.display_order):
            project_entries = entries_by_project.get(project.id, [])
            if project_entries:
                field_projects.append({
                    "id": project.id,
                    "name": project.name,
                    "entries": project_entries,
                })

        if field_projects:
            draft_fields.append({
                "id": field.id,
                "name": field.name,
                "projects": field_projects,
            })

    return {
        "format": "consolidated_v1",
        "fields": draft_fields,
        "uncategorized": uncategorized_entries,
    }


@router.put("/consolidated-drafts/{team_id}/{draft_id}", response_model=ConsolidatedDraftResponse)
async def update_consolidated_draft(
    team_id: int,
    draft_id: int,
    request: ConsolidatedDraftUpdateRequest,
    user: Annotated[User, Depends(require_manager_or_admin)],
):
    """Update a consolidated draft.
    
    Only the manager who created the draft (or admin) can update it.
    """
    from ghost.db import ConsolidatedReportDraft
    
    db = get_db()

    with db.session() as session:
        # Verify team and access
        team = session.query(Team).filter(Team.id == team_id).first()
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")

        if user.role != UserRole.ADMIN and team.manager_id != user.id:
            raise HTTPException(status_code=403, detail="Access denied")

        draft = session.query(ConsolidatedReportDraft).filter(
            ConsolidatedReportDraft.id == draft_id,
            ConsolidatedReportDraft.team_id == team_id,
        ).first()
        
        if not draft:
            raise HTTPException(status_code=404, detail="Draft not found")

        # Non-admins can only update their own drafts
        if user.role != UserRole.ADMIN and draft.manager_id != user.id:
            raise HTTPException(status_code=403, detail="Can only update your own drafts")

        # Update fields
        if request.title is not None:
            draft.title = request.title
        if request.report_period is not None:
            draft.report_period = request.report_period
        if request.content is not None:
            draft.content = json.dumps(request.content.model_dump())

        draft.updated_at = datetime.utcnow()
        session.flush()

        return _draft_to_response(draft)


@router.delete("/consolidated-drafts/{team_id}/{draft_id}")
async def delete_consolidated_draft(
    team_id: int,
    draft_id: int,
    user: Annotated[User, Depends(require_manager_or_admin)],
):
    """Delete a consolidated draft.
    
    Only the manager who created the draft (or admin) can delete it.
    """
    from ghost.db import ConsolidatedReportDraft
    
    db = get_db()

    with db.session() as session:
        # Verify team and access
        team = session.query(Team).filter(Team.id == team_id).first()
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")

        if user.role != UserRole.ADMIN and team.manager_id != user.id:
            raise HTTPException(status_code=403, detail="Access denied")

        draft = session.query(ConsolidatedReportDraft).filter(
            ConsolidatedReportDraft.id == draft_id,
            ConsolidatedReportDraft.team_id == team_id,
        ).first()
        
        if not draft:
            raise HTTPException(status_code=404, detail="Draft not found")

        # Non-admins can only delete their own drafts
        if user.role != UserRole.ADMIN and draft.manager_id != user.id:
            raise HTTPException(status_code=403, detail="Can only delete your own drafts")

        session.delete(draft)

    return {"message": "Draft deleted successfully"}


# =============================================================================
# Consolidated Report Snapshot Models
# =============================================================================


class SnapshotResponse(BaseModel):
    """Response model for a consolidated report snapshot."""

    id: int
    team_id: int
    created_by_id: int
    report_period: str
    snapshot_type: str  # "auto" | "manual"
    label: str | None
    content: ConsolidatedReportResponse
    created_at: str


class SnapshotListResponse(BaseModel):
    """Response model for snapshot list."""

    snapshots: list[SnapshotResponse]
    total: int


class SnapshotCreateRequest(BaseModel):
    """Request model for creating a manual snapshot."""

    report_period: str
    label: str | None = None


def _snapshot_to_response(snapshot) -> SnapshotResponse:
    """Convert ConsolidatedReportSnapshot model to response."""
    import json
    
    content_data = json.loads(snapshot.content) if snapshot.content else {}
    
    return SnapshotResponse(
        id=snapshot.id,
        team_id=snapshot.team_id,
        created_by_id=snapshot.created_by_id,
        report_period=snapshot.report_period,
        snapshot_type=snapshot.snapshot_type.value if snapshot.snapshot_type else "auto",
        label=snapshot.label,
        content=ConsolidatedReportResponse(**content_data),
        created_at=snapshot.created_at.isoformat() if snapshot.created_at else None,
    )


# =============================================================================
# Consolidated Report Snapshot Endpoints
# =============================================================================


@router.get("/consolidated-snapshots/{team_id}", response_model=SnapshotListResponse)
async def list_consolidated_snapshots(
    team_id: int,
    user: Annotated[User, Depends(require_manager_or_admin)],
    report_period: str | None = Query(None, description="Filter by report period"),
    limit: int = Query(50, ge=1, le=100),
):
    """List consolidated report snapshots for a team.
    
    Returns snapshots sorted by created_at descending (most recent first).
    """
    from ghost.db import ConsolidatedReportSnapshot
    
    db = get_db()

    with db.session() as session:
        # Verify team and access
        team = session.query(Team).filter(Team.id == team_id).first()
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")

        if user.role != UserRole.ADMIN and team.manager_id != user.id:
            raise HTTPException(status_code=403, detail="Access denied")

        query = session.query(ConsolidatedReportSnapshot).filter(
            ConsolidatedReportSnapshot.team_id == team_id
        )
        
        if report_period:
            query = query.filter(ConsolidatedReportSnapshot.report_period == report_period)

        total = query.count()
        snapshots = query.order_by(ConsolidatedReportSnapshot.created_at.desc()).limit(limit).all()

        return SnapshotListResponse(
            snapshots=[_snapshot_to_response(s) for s in snapshots],
            total=total,
        )


@router.get("/consolidated-snapshots/{team_id}/{snapshot_id}", response_model=SnapshotResponse)
async def get_consolidated_snapshot(
    team_id: int,
    snapshot_id: int,
    user: Annotated[User, Depends(require_manager_or_admin)],
):
    """Get a specific consolidated report snapshot."""
    from ghost.db import ConsolidatedReportSnapshot
    
    db = get_db()

    with db.session() as session:
        # Verify team and access
        team = session.query(Team).filter(Team.id == team_id).first()
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")

        if user.role != UserRole.ADMIN and team.manager_id != user.id:
            raise HTTPException(status_code=403, detail="Access denied")

        snapshot = session.query(ConsolidatedReportSnapshot).filter(
            ConsolidatedReportSnapshot.id == snapshot_id,
            ConsolidatedReportSnapshot.team_id == team_id,
        ).first()
        
        if not snapshot:
            raise HTTPException(status_code=404, detail="Snapshot not found")

        return _snapshot_to_response(snapshot)


@router.post("/consolidated-snapshots/{team_id}", response_model=SnapshotResponse, status_code=status.HTTP_201_CREATED)
async def create_consolidated_snapshot(
    team_id: int,
    request: SnapshotCreateRequest,
    user: Annotated[User, Depends(require_manager_or_admin)],
):
    """Create a manual snapshot of the current consolidated report.
    
    This creates a labeled snapshot that the manager can reference later.
    Use this for "Final Version", "Before Edits", etc.
    """
    from ghost.db import ConsolidatedReportSnapshot, SnapshotType
    
    db = get_db()

    with db.session() as session:
        # Verify team and access
        team = session.query(Team).filter(Team.id == team_id).first()
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")

        if user.role != UserRole.ADMIN and team.manager_id != user.id:
            raise HTTPException(status_code=403, detail="Access denied")

        # Get current consolidated report data
        # We need to fetch it fresh to get the latest state
        consolidated_data = await get_consolidated_report(
            team_id=team_id,
            user=user,
            report_period=request.report_period,
            limit=100,
        )

        snapshot = ConsolidatedReportSnapshot(
            team_id=team_id,
            created_by_id=user.id,
            report_period=request.report_period,
            snapshot_type=SnapshotType.MANUAL,
            label=request.label,
            content=json.dumps(consolidated_data.model_dump()),
        )
        session.add(snapshot)
        session.flush()
        session.refresh(snapshot)

        return _snapshot_to_response(snapshot)


@router.delete("/consolidated-snapshots/{team_id}/{snapshot_id}")
async def delete_consolidated_snapshot(
    team_id: int,
    snapshot_id: int,
    user: Annotated[User, Depends(require_manager_or_admin)],
):
    """Delete a consolidated report snapshot.
    
    Only admins can delete auto-saved snapshots.
    Managers can delete their own manual snapshots.
    """
    from ghost.db import ConsolidatedReportSnapshot, SnapshotType
    
    db = get_db()

    with db.session() as session:
        # Verify team and access
        team = session.query(Team).filter(Team.id == team_id).first()
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")

        if user.role != UserRole.ADMIN and team.manager_id != user.id:
            raise HTTPException(status_code=403, detail="Access denied")

        snapshot = session.query(ConsolidatedReportSnapshot).filter(
            ConsolidatedReportSnapshot.id == snapshot_id,
            ConsolidatedReportSnapshot.team_id == team_id,
        ).first()
        
        if not snapshot:
            raise HTTPException(status_code=404, detail="Snapshot not found")

        # Non-admins can only delete their own manual snapshots
        if user.role != UserRole.ADMIN:
            if snapshot.snapshot_type == SnapshotType.AUTO:
                raise HTTPException(status_code=403, detail="Cannot delete auto-saved snapshots")
            if snapshot.created_by_id != user.id:
                raise HTTPException(status_code=403, detail="Can only delete your own snapshots")

        session.delete(snapshot)

    return {"message": "Snapshot deleted successfully"}
