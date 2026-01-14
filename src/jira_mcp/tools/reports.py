"""Activity tracking and weekly report generation tools."""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy import func, distinct

from jira_mcp.db import get_db, ActivityLog, WeeklyReport, ManagementReport
from jira_mcp.db.models import ActionType

logger = logging.getLogger(__name__)


def log_activity(
    username: str,
    ticket_key: str,
    action_type: str,
    ticket_summary: Optional[str] = None,
    project_key: Optional[str] = None,
    action_details: Optional[dict] = None,
) -> dict[str, Any]:
    """
    Log a Jira activity for tracking.
    
    Args:
        username: The username performing the action.
        ticket_key: The Jira ticket key (e.g., 'PROJ-123').
        action_type: Type of action (view, create, update, comment, transition, link, other).
        ticket_summary: Optional ticket summary.
        project_key: Optional project key (extracted from ticket_key if not provided).
        action_details: Optional dict with additional context.
        
    Returns:
        Confirmation with activity ID.
    """
    db = get_db()
    
    # Extract project key from ticket if not provided
    if not project_key and "-" in ticket_key:
        project_key = ticket_key.split("-")[0]
    
    # Map action type string to enum
    try:
        action_enum = ActionType(action_type.lower())
    except ValueError:
        action_enum = ActionType.OTHER
    
    with db.session() as session:
        activity = ActivityLog(
            username=username,
            ticket_key=ticket_key,
            ticket_summary=ticket_summary,
            project_key=project_key,
            action_type=action_enum,
            action_details=json.dumps(action_details) if action_details else None,
            timestamp=datetime.utcnow(),
        )
        session.add(activity)
        session.flush()
        activity_id = activity.id
    
    logger.info(f"Logged activity {activity_id}: {username} {action_type} {ticket_key}")
    
    return {
        "success": True,
        "activity_id": activity_id,
        "message": f"Activity logged: {action_type} on {ticket_key}",
    }


def get_weekly_activity(
    username: str,
    week_offset: int = 0,
    project: Optional[str] = None,
) -> dict[str, Any]:
    """
    Get activity summary for a specific week.
    
    Args:
        username: The username to get activity for.
        week_offset: Week offset from current week (0 = current, -1 = last week, etc.).
        project: Optional project key to filter by.
        
    Returns:
        Activity summary with tickets worked on, grouped by action type.
    """
    db = get_db()
    
    # Calculate week boundaries (Monday to Sunday)
    today = datetime.utcnow().date()
    current_monday = today - timedelta(days=today.weekday())
    target_monday = current_monday + timedelta(weeks=week_offset)
    target_sunday = target_monday + timedelta(days=6, hours=23, minutes=59, seconds=59)
    
    week_start = datetime.combine(target_monday, datetime.min.time())
    week_end = datetime.combine(target_sunday, datetime.max.time())
    
    with db.session() as session:
        query = session.query(ActivityLog).filter(
            ActivityLog.username == username,
            ActivityLog.timestamp >= week_start,
            ActivityLog.timestamp <= week_end,
        )
        
        if project:
            query = query.filter(ActivityLog.project_key == project)
        
        activities = query.order_by(ActivityLog.timestamp.desc()).all()
        
        # Get unique tickets
        unique_tickets = session.query(
            ActivityLog.ticket_key,
            ActivityLog.ticket_summary,
            ActivityLog.project_key,
            func.count(ActivityLog.id).label("action_count"),
        ).filter(
            ActivityLog.username == username,
            ActivityLog.timestamp >= week_start,
            ActivityLog.timestamp <= week_end,
        )
        
        if project:
            unique_tickets = unique_tickets.filter(ActivityLog.project_key == project)
        
        unique_tickets = unique_tickets.group_by(
            ActivityLog.ticket_key,
            ActivityLog.ticket_summary,
            ActivityLog.project_key,
        ).all()
        
        # Group activities by action type
        by_action = {}
        for activity in activities:
            action = activity.action_type.value if activity.action_type else "other"
            if action not in by_action:
                by_action[action] = []
            by_action[action].append({
                "ticket_key": activity.ticket_key,
                "ticket_summary": activity.ticket_summary,
                "timestamp": activity.timestamp.isoformat(),
            })
    
    return {
        "username": username,
        "week_start": week_start.date().isoformat(),
        "week_end": week_end.date().isoformat(),
        "total_activities": len(activities),
        "unique_tickets": [
            {
                "ticket_key": t.ticket_key,
                "ticket_summary": t.ticket_summary,
                "project_key": t.project_key,
                "action_count": t.action_count,
            }
            for t in unique_tickets
        ],
        "by_action_type": by_action,
    }


def generate_weekly_report(
    username: str,
    week_offset: int = 0,
    include_details: bool = True,
) -> dict[str, Any]:
    """
    Generate an executive weekly report for management.
    
    Args:
        username: The username to generate report for.
        week_offset: Week offset from current week (0 = current, -1 = last week, etc.).
        include_details: Whether to include detailed ticket list.
        
    Returns:
        Generated report with title, summary, and content.
    """
    # Get activity data
    activity = get_weekly_activity(username, week_offset)
    
    week_start = activity["week_start"]
    week_end = activity["week_end"]
    unique_tickets = activity["unique_tickets"]
    by_action = activity["by_action_type"]
    
    # Calculate statistics
    total_tickets = len(unique_tickets)
    projects = list(set(t["project_key"] for t in unique_tickets if t["project_key"]))
    
    # Count by action type
    created_count = len(by_action.get("create", []))
    updated_count = len(by_action.get("update", []))
    commented_count = len(by_action.get("comment", []))
    transitioned_count = len(by_action.get("transition", []))
    
    # Build executive summary
    title = f"Weekly Report: {week_start} to {week_end}"
    
    summary_parts = [f"Worked on **{total_tickets} tickets**"]
    if projects:
        summary_parts.append(f"across **{len(projects)} projects** ({', '.join(projects)})")
    
    action_summary = []
    if created_count:
        action_summary.append(f"{created_count} created")
    if updated_count:
        action_summary.append(f"{updated_count} updated")
    if transitioned_count:
        action_summary.append(f"{transitioned_count} status changes")
    if commented_count:
        action_summary.append(f"{commented_count} comments added")
    
    if action_summary:
        summary_parts.append(f"Actions: {', '.join(action_summary)}.")
    
    summary = " ".join(summary_parts)
    
    # Build full report content (Markdown)
    content_lines = [
        f"# {title}",
        "",
        f"**Engineer:** {username}",
        f"**Period:** {week_start} to {week_end}",
        "",
        "## Executive Summary",
        "",
        summary,
        "",
        "## Key Metrics",
        "",
        f"- **Total Tickets:** {total_tickets}",
        f"- **Projects:** {', '.join(projects) if projects else 'N/A'}",
        f"- **Tickets Created:** {created_count}",
        f"- **Tickets Updated:** {updated_count}",
        f"- **Status Transitions:** {transitioned_count}",
        f"- **Comments Added:** {commented_count}",
        "",
    ]
    
    if include_details and unique_tickets:
        content_lines.extend([
            "## Tickets Worked On",
            "",
            "| Ticket | Summary | Project | Actions |",
            "|--------|---------|---------|---------|",
        ])
        
        for ticket in unique_tickets:
            summary_text = (ticket["ticket_summary"] or "N/A")[:50]
            if len(ticket["ticket_summary"] or "") > 50:
                summary_text += "..."
            content_lines.append(
                f"| {ticket['ticket_key']} | {summary_text} | "
                f"{ticket['project_key'] or 'N/A'} | {ticket['action_count']} |"
            )
        
        content_lines.append("")
    
    # Add activity breakdown if detailed
    if include_details and by_action:
        content_lines.extend([
            "## Activity Breakdown",
            "",
        ])
        
        for action_type, actions in by_action.items():
            if actions:
                content_lines.append(f"### {action_type.title()} ({len(actions)})")
                content_lines.append("")
                for action in actions[:10]:  # Limit to 10 per type
                    content_lines.append(
                        f"- **{action['ticket_key']}**: {action['ticket_summary'] or 'N/A'}"
                    )
                if len(actions) > 10:
                    content_lines.append(f"- *...and {len(actions) - 10} more*")
                content_lines.append("")
    
    content = "\n".join(content_lines)
    
    return {
        "title": title,
        "summary": summary,
        "content": content,
        "username": username,
        "week_start": week_start,
        "week_end": week_end,
        "tickets_count": total_tickets,
        "projects": projects,
        "statistics": {
            "created": created_count,
            "updated": updated_count,
            "commented": commented_count,
            "transitioned": transitioned_count,
        },
    }


def save_weekly_report(
    username: str,
    week_offset: int = 0,
    custom_title: Optional[str] = None,
    custom_summary: Optional[str] = None,
) -> dict[str, Any]:
    """
    Generate and save a weekly report to the database.
    
    Args:
        username: The username to generate report for.
        week_offset: Week offset from current week (0 = current, -1 = last week, etc.).
        custom_title: Optional custom title override.
        custom_summary: Optional custom summary override.
        
    Returns:
        Saved report details with ID.
    """
    # Generate the report
    report_data = generate_weekly_report(username, week_offset, include_details=True)
    
    # Parse dates
    week_start = datetime.fromisoformat(report_data["week_start"])
    week_end = datetime.fromisoformat(report_data["week_end"])
    
    db = get_db()
    
    with db.session() as session:
        # Check for existing report for this week
        existing = session.query(WeeklyReport).filter(
            WeeklyReport.username == username,
            WeeklyReport.week_start == week_start,
        ).first()
        
        if existing:
            # Update existing report
            existing.title = custom_title or report_data["title"]
            existing.summary = custom_summary or report_data["summary"]
            existing.content = report_data["content"]
            existing.tickets_count = report_data["tickets_count"]
            existing.projects = ",".join(report_data["projects"])
            existing.updated_at = datetime.utcnow()
            report_id = existing.id
            created = False
        else:
            # Create new report
            report = WeeklyReport(
                username=username,
                week_start=week_start,
                week_end=week_end,
                title=custom_title or report_data["title"],
                summary=custom_summary or report_data["summary"],
                content=report_data["content"],
                tickets_count=report_data["tickets_count"],
                projects=",".join(report_data["projects"]),
            )
            session.add(report)
            session.flush()
            report_id = report.id
            created = True
    
    return {
        "success": True,
        "report_id": report_id,
        "created": created,
        "title": custom_title or report_data["title"],
        "week_start": report_data["week_start"],
        "week_end": report_data["week_end"],
        "message": f"Report {'created' if created else 'updated'} successfully",
    }


def list_saved_reports(
    username: str,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """
    List saved weekly reports for a user.
    
    Args:
        username: The username to list reports for.
        limit: Maximum number of reports to return.
        
    Returns:
        List of report summaries.
    """
    db = get_db()
    
    with db.session() as session:
        reports = session.query(WeeklyReport).filter(
            WeeklyReport.username == username,
        ).order_by(
            WeeklyReport.week_start.desc()
        ).limit(limit).all()
        
        return [
            {
                "id": r.id,
                "title": r.title,
                "summary": r.summary,
                "week_start": r.week_start.isoformat() if r.week_start else None,
                "week_end": r.week_end.isoformat() if r.week_end else None,
                "tickets_count": r.tickets_count,
                "projects": r.projects.split(",") if r.projects else [],
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in reports
        ]


def get_saved_report(
    report_id: int,
) -> dict[str, Any]:
    """
    Get a saved weekly report by ID.
    
    Args:
        report_id: The report ID.
        
    Returns:
        Full report details.
    """
    db = get_db()
    
    with db.session() as session:
        report = session.query(WeeklyReport).filter(
            WeeklyReport.id == report_id,
        ).first()
        
        if not report:
            return {
                "error": True,
                "message": f"Report {report_id} not found",
            }
        
        return report.to_dict()


def delete_saved_report(
    report_id: int,
) -> dict[str, Any]:
    """
    Delete a saved weekly report.
    
    Args:
        report_id: The report ID to delete.
        
    Returns:
        Confirmation of deletion.
    """
    db = get_db()
    
    with db.session() as session:
        report = session.query(WeeklyReport).filter(
            WeeklyReport.id == report_id,
        ).first()
        
        if not report:
            return {
                "error": True,
                "message": f"Report {report_id} not found",
            }
        
        session.delete(report)
    
    return {
        "success": True,
        "message": f"Report {report_id} deleted successfully",
    }


# =============================================================================
# Management Reports (AI-generated content for high-level stakeholders)
# =============================================================================


def save_management_report(
    username: str,
    title: str,
    executive_summary: str,
    content: str,
    one_liner: Optional[str] = None,
    project_key: Optional[str] = None,
    report_period: Optional[str] = None,
    referenced_tickets: Optional[list[str]] = None,
) -> dict[str, Any]:
    """
    Save an AI-generated management report to the database.
    
    Reports should be CONCISE and management-friendly:
    - one_liner: Single sentence (max 15 words) - the "elevator pitch"
    - executive_summary: 2-3 sentences, high-level outcomes only
    - content: Short Markdown (<500 words), bullet points, Jira links
    
    Args:
        username: The author/engineer username.
        title: Report title (e.g., "APPENG Progress - Week 3").
        executive_summary: 2-3 sentence high-level summary.
        content: Concise Markdown report (<500 words).
        one_liner: Optional single sentence elevator pitch (max 15 words).
        project_key: Optional project key this report focuses on.
        report_period: Optional period (e.g., "Week 3, Jan 2026").
        referenced_tickets: Optional list of Jira ticket keys.
        
    Returns:
        Saved report details with ID.
    """
    db = get_db()
    
    with db.session() as session:
        report = ManagementReport(
            username=username,
            title=title,
            one_liner=one_liner,
            executive_summary=executive_summary,
            content=content,
            project_key=project_key,
            report_period=report_period,
            referenced_tickets=",".join(referenced_tickets) if referenced_tickets else None,
        )
        session.add(report)
        session.flush()
        report_id = report.id
    
    logger.info(f"Saved management report {report_id}: {title}")
    
    return {
        "success": True,
        "report_id": report_id,
        "title": title,
        "project_key": project_key,
        "message": f"Management report saved successfully (ID: {report_id})",
    }


def list_management_reports(
    username: Optional[str] = None,
    project_key: Optional[str] = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """
    List saved management reports.
    
    Args:
        username: Optional filter by author.
        project_key: Optional filter by project.
        limit: Maximum number of reports to return.
        
    Returns:
        List of report summaries.
    """
    db = get_db()
    
    with db.session() as session:
        query = session.query(ManagementReport)
        
        if username:
            query = query.filter(ManagementReport.username == username)
        if project_key:
            query = query.filter(ManagementReport.project_key == project_key)
        
        reports = query.order_by(
            ManagementReport.created_at.desc()
        ).limit(limit).all()
        
        return [
            {
                "id": r.id,
                "title": r.title,
                "one_liner": r.one_liner,
                "executive_summary": r.executive_summary,
                "project_key": r.project_key,
                "report_period": r.report_period,
                "referenced_tickets": r.referenced_tickets.split(",") if r.referenced_tickets else [],
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "username": r.username,
            }
            for r in reports
        ]


def get_management_report(
    report_id: int,
) -> dict[str, Any]:
    """
    Get a saved management report by ID.
    
    Args:
        report_id: The report ID.
        
    Returns:
        Full report details including content.
    """
    db = get_db()
    
    with db.session() as session:
        report = session.query(ManagementReport).filter(
            ManagementReport.id == report_id,
        ).first()
        
        if not report:
            return {
                "error": True,
                "message": f"Management report {report_id} not found",
            }
        
        return report.to_dict()


def update_management_report(
    report_id: int,
    title: Optional[str] = None,
    one_liner: Optional[str] = None,
    executive_summary: Optional[str] = None,
    content: Optional[str] = None,
    report_period: Optional[str] = None,
    referenced_tickets: Optional[list[str]] = None,
) -> dict[str, Any]:
    """
    Update an existing management report.
    
    Args:
        report_id: The report ID to update.
        title: Optional new title.
        one_liner: Optional new one-liner elevator pitch.
        executive_summary: Optional new executive summary.
        content: Optional new full content.
        report_period: Optional new period description.
        referenced_tickets: Optional new list of referenced tickets.
        
    Returns:
        Updated report confirmation.
    """
    db = get_db()
    
    with db.session() as session:
        report = session.query(ManagementReport).filter(
            ManagementReport.id == report_id,
        ).first()
        
        if not report:
            return {
                "error": True,
                "message": f"Management report {report_id} not found",
            }
        
        if title is not None:
            report.title = title
        if one_liner is not None:
            report.one_liner = one_liner
        if executive_summary is not None:
            report.executive_summary = executive_summary
        if content is not None:
            report.content = content
        if report_period is not None:
            report.report_period = report_period
        if referenced_tickets is not None:
            report.referenced_tickets = ",".join(referenced_tickets)
        
        report.updated_at = datetime.utcnow()
    
    return {
        "success": True,
        "report_id": report_id,
        "message": f"Management report {report_id} updated successfully",
    }


def delete_management_report(
    report_id: int,
) -> dict[str, Any]:
    """
    Delete a management report.
    
    Args:
        report_id: The report ID to delete.
        
    Returns:
        Confirmation of deletion.
    """
    db = get_db()
    
    with db.session() as session:
        report = session.query(ManagementReport).filter(
            ManagementReport.id == report_id,
        ).first()
        
        if not report:
            return {
                "error": True,
                "message": f"Management report {report_id} not found",
            }
        
        session.delete(report)
    
    return {
        "success": True,
        "message": f"Management report {report_id} deleted successfully",
    }
