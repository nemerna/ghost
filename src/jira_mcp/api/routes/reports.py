"""Report management API endpoints."""

import json
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from sqlalchemy.orm import joinedload

from jira_mcp.api.deps import CurrentUser, require_manager_or_admin
from jira_mcp.db import (
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
from jira_mcp.tools import reports as report_tools

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


class WeeklyReportCreateRequest(BaseModel):
    """Request model for creating/updating a weekly report."""
    
    week_offset: int = 0
    custom_title: str | None = None
    custom_summary: str | None = None


class WeeklyReportListResponse(BaseModel):
    """Response model for weekly report list."""
    
    reports: list[WeeklyReportResponse]
    total: int


class ManagementReportResponse(BaseModel):
    """Management report response model."""
    
    id: int
    username: str
    title: str
    project_key: str | None
    report_period: str | None
    content: str
    referenced_tickets: list[str]
    created_at: str | None
    updated_at: str | None


class ManagementReportCreateRequest(BaseModel):
    """Request model for creating a management report."""
    
    title: str
    content: str
    project_key: str | None = None
    report_period: str | None = None
    referenced_tickets: list[str] | None = None


class ManagementReportUpdateRequest(BaseModel):
    """Request model for updating a management report."""
    
    title: str | None = None
    content: str | None = None
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
    )


def management_report_to_response(report: ManagementReport) -> ManagementReportResponse:
    """Convert ManagementReport model to response."""
    return ManagementReportResponse(
        id=report.id,
        username=report.username,
        title=report.title,
        project_key=report.project_key,
        report_period=report.report_period,
        content=report.content,
        referenced_tickets=report.referenced_tickets.split(",") if report.referenced_tickets else [],
        created_at=report.created_at.isoformat() if report.created_at else None,
        updated_at=report.updated_at.isoformat() if report.updated_at else None,
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


@router.get("/weekly/team/{team_id}", response_model=WeeklyReportListResponse)
async def get_team_weekly_reports(
    team_id: int,
    user: Annotated[User, Depends(require_manager_or_admin)],
    week_start: datetime | None = Query(None, description="Filter by week start date"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Get weekly reports for all team members (manager or admin only)."""
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
        
        # Query reports
        query = session.query(WeeklyReport).filter(WeeklyReport.username.in_(member_emails))
        
        if week_start:
            query = query.filter(WeeklyReport.week_start == week_start)
        
        total = query.count()
        
        reports = (
            query.order_by(WeeklyReport.week_start.desc(), WeeklyReport.username)
            .offset(offset)
            .limit(limit)
            .all()
        )
        
        return WeeklyReportListResponse(
            reports=[weekly_report_to_response(r) for r in reports],
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
    """Create a new management report."""
    db = get_db()
    
    with db.session() as session:
        report = ManagementReport(
            username=user.email,
            title=request.title,
            content=request.content,
            project_key=request.project_key,
            report_period=request.report_period,
            referenced_tickets=",".join(request.referenced_tickets) if request.referenced_tickets else None,
            created_at=datetime.utcnow(),
        )
        session.add(report)
        session.flush()
        
        return management_report_to_response(report)


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
    """Update a management report."""
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
        if request.content is not None:
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


@router.get("/management/team/{team_id}", response_model=ManagementReportListResponse)
async def get_team_management_reports(
    team_id: int,
    user: Annotated[User, Depends(require_manager_or_admin)],
    report_period: str | None = Query(None, description="Filter by report period"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Get management reports from all team members (manager or admin only)."""
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
        
        # Query management reports from team members
        query = session.query(ManagementReport).filter(ManagementReport.username.in_(member_emails))
        
        if report_period:
            query = query.filter(ManagementReport.report_period == report_period)
        
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


@router.get("/management/aggregate/{team_id}", response_model=dict)
async def get_team_report_aggregate(
    team_id: int,
    user: Annotated[User, Depends(require_manager_or_admin)],
    week_offset: int = Query(0, ge=-52, le=0, description="Week offset"),
):
    """Get aggregated data from team members' weekly reports for management report creation."""
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
        
        # Get weekly reports for this period
        reports = (
            session.query(WeeklyReport)
            .filter(
                WeeklyReport.username.in_(member_emails),
                WeeklyReport.week_start >= week_start,
                WeeklyReport.week_start <= week_end,
            )
            .all()
        )
        
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


# =============================================================================
# Consolidated Report Models
# =============================================================================


class ConsolidatedEntry(BaseModel):
    """A single entry (report) in the consolidated view."""

    username: str
    report_id: int
    title: str
    content: str
    report_period: str | None
    created_at: str | None


class ConsolidatedProject(BaseModel):
    """Project with its entries in consolidated view."""

    id: int
    name: str
    description: str | None
    entries: list[ConsolidatedEntry]


class ConsolidatedField(BaseModel):
    """Field with its projects in consolidated view."""

    id: int
    name: str
    description: str | None
    projects: list[ConsolidatedProject]


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

        # Get management reports from team members
        query = session.query(ManagementReport).filter(ManagementReport.username.in_(member_emails))

        if report_period:
            query = query.filter(ManagementReport.report_period == report_period)

        reports = query.order_by(ManagementReport.created_at.desc()).limit(limit).all()

        # Get the latest report per user (for consolidation)
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

        # Group reports by detected project
        # For each report, look at its referenced_tickets and find activities
        # with detected_project_id to determine which project it belongs to
        from jira_mcp.db import ActivityLog

        entries_by_project: dict[int, list[ConsolidatedEntry]] = {}
        uncategorized_entries: list[ConsolidatedEntry] = []

        for username, report in latest_by_user.items():
            entry = ConsolidatedEntry(
                username=username,
                report_id=report.id,
                title=report.title,
                content=report.content,
                report_period=report.report_period,
                created_at=report.created_at.isoformat() if report.created_at else None,
            )

            # Find the most common detected_project_id from referenced tickets
            detected_project_id = None
            if report.referenced_tickets:
                ticket_keys = [t.strip() for t in report.referenced_tickets.split(",") if t.strip()]
                if ticket_keys:
                    # Query activities for these tickets to get detected_project_id
                    activities = (
                        session.query(ActivityLog.detected_project_id)
                        .filter(
                            ActivityLog.ticket_key.in_(ticket_keys),
                            ActivityLog.detected_project_id.isnot(None),
                        )
                        .all()
                    )

                    if activities:
                        # Get the most common project ID (mode)
                        project_counts: dict[int, int] = {}
                        for (proj_id,) in activities:
                            if proj_id:
                                project_counts[proj_id] = project_counts.get(proj_id, 0) + 1

                        if project_counts:
                            detected_project_id = max(project_counts.items(), key=lambda x: x[1])[0]

            if detected_project_id and detected_project_id in project_to_field:
                if detected_project_id not in entries_by_project:
                    entries_by_project[detected_project_id] = []
                entries_by_project[detected_project_id].append(entry)
            else:
                uncategorized_entries.append(entry)

        # Build the response structure
        consolidated_fields: list[ConsolidatedField] = []

        for field in fields:
            field_projects: list[ConsolidatedProject] = []

            for project in sorted(field.projects, key=lambda p: p.display_order):
                project_entries = entries_by_project.get(project.id, [])
                if project_entries:  # Only include projects with entries
                    field_projects.append(
                        ConsolidatedProject(
                            id=project.id,
                            name=project.name,
                            description=project.description,
                            entries=project_entries,
                        )
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

        total_entries = sum(
            len(p.entries) for f in consolidated_fields for p in f.projects
        ) + len(uncategorized_entries)

        return ConsolidatedReportResponse(
            team_id=team_id,
            team_name=team.name,
            report_period=report_period,
            fields=consolidated_fields,
            uncategorized=uncategorized_entries,
            total_entries=total_entries,
        )
