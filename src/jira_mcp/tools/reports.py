"""Activity tracking and weekly report generation tools."""

import json
import logging
import re
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func

from jira_mcp.db import ActivityLog, ManagementReport, TicketSource, WeeklyReport, get_db
from jira_mcp.db.models import ActionType

logger = logging.getLogger(__name__)


def _parse_ticket_key(
    ticket_key: str, github_repo: str | None = None
) -> tuple[TicketSource, str, str | None, str | None]:
    """
    Parse a ticket key and determine its source.

    Args:
        ticket_key: The ticket key (PROJ-123, owner/repo#123, or #123)
        github_repo: Optional GitHub repo for short #123 format

    Returns:
        Tuple of (source, normalized_key, project_key_or_none, github_repo_or_none)
    """
    # GitHub Issue patterns
    # Full format: owner/repo#123
    github_full_pattern = r"^([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)#(\d+)$"
    # Short format: #123 (requires github_repo)
    github_short_pattern = r"^#(\d+)$"

    # Check for full GitHub format (owner/repo#123)
    full_match = re.match(github_full_pattern, ticket_key)
    if full_match:
        repo = full_match.group(1)
        issue_num = full_match.group(2)
        return TicketSource.GITHUB, ticket_key, None, repo

    # Check for short GitHub format (#123)
    short_match = re.match(github_short_pattern, ticket_key)
    if short_match and github_repo:
        issue_num = short_match.group(1)
        full_key = f"{github_repo}#{issue_num}"
        return TicketSource.GITHUB, full_key, None, github_repo

    # Default: Jira ticket (PROJ-123 format)
    # Extract project key from Jira ticket
    project_key = None
    if "-" in ticket_key:
        project_key = ticket_key.split("-")[0]

    return TicketSource.JIRA, ticket_key, project_key, None


def log_activity(
    username: str,
    ticket_key: str,
    action_type: str,
    ticket_summary: str | None = None,
    project_key: str | None = None,
    github_repo: str | None = None,
    action_details: dict | None = None,
) -> dict[str, Any]:
    """
    Log a Jira or GitHub activity for tracking.

    Args:
        username: The username performing the action.
        ticket_key: The ticket key. Jira: 'PROJ-123'. GitHub: 'owner/repo#123' or '#123'.
        action_type: Type of action (view, create, update, comment, transition, link, other).
        ticket_summary: Optional ticket summary.
        project_key: Optional Jira project key (extracted from ticket_key if not provided).
        github_repo: Optional GitHub repo in 'owner/repo' format. Required for short '#123' format.
        action_details: Optional dict with additional context.

    Returns:
        Confirmation with activity ID and detected source.
    """
    db = get_db()

    # Parse ticket key and determine source
    source, normalized_key, detected_project, detected_repo = _parse_ticket_key(
        ticket_key, github_repo
    )

    # Use detected values or provided overrides
    final_project_key = project_key or detected_project
    final_github_repo = github_repo or detected_repo

    # Map action type string to enum
    try:
        action_enum = ActionType(action_type.lower())
    except ValueError:
        action_enum = ActionType.OTHER

    with db.session() as session:
        activity = ActivityLog(
            username=username,
            ticket_key=normalized_key,
            ticket_summary=ticket_summary,
            project_key=final_project_key,
            ticket_source=source,
            github_repo=final_github_repo,
            action_type=action_enum,
            action_details=json.dumps(action_details) if action_details else None,
            timestamp=datetime.utcnow(),
        )
        session.add(activity)
        session.flush()
        activity_id = activity.id

    logger.info(
        f"Logged activity {activity_id}: {username} {action_type} {normalized_key} (source: {source.value})"
    )

    return {
        "success": True,
        "activity_id": activity_id,
        "ticket_source": source.value,
        "ticket_key": normalized_key,
        "message": f"Activity logged: {action_type} on {normalized_key} ({source.value})",
    }


def get_weekly_activity(
    username: str,
    week_offset: int = 0,
    project: str | None = None,
    ticket_source: str | None = None,
) -> dict[str, Any]:
    """
    Get activity summary for a specific week.

    Args:
        username: The username to get activity for.
        week_offset: Week offset from current week (0 = current, -1 = last week, etc.).
        project: Optional project key to filter by (Jira only).
        ticket_source: Optional filter by source ('jira' or 'github').

    Returns:
        Activity summary with tickets worked on, grouped by action type and source.
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

        if ticket_source:
            try:
                source_enum = TicketSource(ticket_source.lower())
                query = query.filter(ActivityLog.ticket_source == source_enum)
            except ValueError:
                pass  # Invalid source, ignore filter

        activities = query.order_by(ActivityLog.timestamp.desc()).all()

        # Get unique tickets with source info
        unique_tickets_query = session.query(
            ActivityLog.ticket_key,
            ActivityLog.ticket_summary,
            ActivityLog.project_key,
            ActivityLog.ticket_source,
            ActivityLog.github_repo,
            func.count(ActivityLog.id).label("action_count"),
        ).filter(
            ActivityLog.username == username,
            ActivityLog.timestamp >= week_start,
            ActivityLog.timestamp <= week_end,
        )

        if project:
            unique_tickets_query = unique_tickets_query.filter(
                ActivityLog.project_key == project
            )

        if ticket_source:
            try:
                source_enum = TicketSource(ticket_source.lower())
                unique_tickets_query = unique_tickets_query.filter(
                    ActivityLog.ticket_source == source_enum
                )
            except ValueError:
                pass

        unique_tickets = unique_tickets_query.group_by(
            ActivityLog.ticket_key,
            ActivityLog.ticket_summary,
            ActivityLog.project_key,
            ActivityLog.ticket_source,
            ActivityLog.github_repo,
        ).all()

        # Group activities by action type
        by_action = {}
        for activity in activities:
            action = activity.action_type.value if activity.action_type else "other"
            if action not in by_action:
                by_action[action] = []
            by_action[action].append(
                {
                    "ticket_key": activity.ticket_key,
                    "ticket_summary": activity.ticket_summary,
                    "ticket_source": (
                        activity.ticket_source.value if activity.ticket_source else "jira"
                    ),
                    "github_repo": activity.github_repo,
                    "timestamp": activity.timestamp.isoformat(),
                    "action_details": (
                        json.loads(activity.action_details) if activity.action_details else None
                    ),
                }
            )

        # Count by source
        jira_count = sum(
            1 for t in unique_tickets if t.ticket_source == TicketSource.JIRA
        )
        github_count = sum(
            1 for t in unique_tickets if t.ticket_source == TicketSource.GITHUB
        )

    return {
        "username": username,
        "week_start": week_start.date().isoformat(),
        "week_end": week_end.date().isoformat(),
        "total_activities": len(activities),
        "unique_tickets": [
            {
                "ticket_key": t.ticket_key,
                "ticket_summary": t.ticket_summary,
                "ticket_source": t.ticket_source.value if t.ticket_source else "jira",
                "project_key": t.project_key,
                "github_repo": t.github_repo,
                "action_count": t.action_count,
            }
            for t in unique_tickets
        ],
        "by_source": {
            "jira": jira_count,
            "github": github_count,
        },
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
    by_source = activity.get("by_source", {"jira": 0, "github": 0})

    # Calculate statistics
    total_tickets = len(unique_tickets)
    jira_projects = list(
        set(t["project_key"] for t in unique_tickets if t["project_key"])
    )
    github_repos = list(
        set(t["github_repo"] for t in unique_tickets if t["github_repo"])
    )

    # Count by action type
    created_count = len(by_action.get("create", []))
    updated_count = len(by_action.get("update", []))
    commented_count = len(by_action.get("comment", []))
    transitioned_count = len(by_action.get("transition", []))

    # Build executive summary
    title = f"Weekly Report: {week_start} to {week_end}"

    summary_parts = [f"Worked on **{total_tickets} tickets**"]

    # Add source breakdown
    source_parts = []
    if by_source.get("jira", 0) > 0:
        source_parts.append(f"{by_source['jira']} Jira")
    if by_source.get("github", 0) > 0:
        source_parts.append(f"{by_source['github']} GitHub")
    if source_parts:
        summary_parts.append(f"({', '.join(source_parts)})")

    if jira_projects:
        summary_parts.append(f"across **{len(jira_projects)} Jira projects**")
    if github_repos:
        summary_parts.append(f"and **{len(github_repos)} GitHub repos**")

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
        f"- **Jira Tickets:** {by_source.get('jira', 0)}",
        f"- **GitHub Issues:** {by_source.get('github', 0)}",
        f"- **Jira Projects:** {', '.join(jira_projects) if jira_projects else 'N/A'}",
        f"- **GitHub Repos:** {', '.join(github_repos) if github_repos else 'N/A'}",
        f"- **Tickets Created:** {created_count}",
        f"- **Tickets Updated:** {updated_count}",
        f"- **Status Transitions:** {transitioned_count}",
        f"- **Comments Added:** {commented_count}",
        "",
    ]

    if include_details and unique_tickets:
        content_lines.extend(
            [
                "## Tickets Worked On",
                "",
                "| Source | Ticket | Summary | Project/Repo | Actions |",
                "|--------|--------|---------|--------------|---------|",
            ]
        )

        for ticket in unique_tickets:
            summary_text = (ticket["ticket_summary"] or "N/A")[:50]
            if len(ticket["ticket_summary"] or "") > 50:
                summary_text += "..."
            source = ticket.get("ticket_source", "jira")
            source_label = "Jira" if source == "jira" else "GitHub"
            project_or_repo = ticket["project_key"] or ticket.get("github_repo") or "N/A"
            content_lines.append(
                f"| {source_label} | {ticket['ticket_key']} | {summary_text} | "
                f"{project_or_repo} | {ticket['action_count']} |"
            )

        content_lines.append("")

    # Add activity breakdown if detailed
    if include_details and by_action:
        content_lines.extend(
            [
                "## Activity Breakdown",
                "",
            ]
        )

        for action_type, actions in by_action.items():
            if actions:
                content_lines.append(f"### {action_type.title()} ({len(actions)})")
                content_lines.append("")
                for action in actions[:10]:  # Limit to 10 per type
                    source = action.get("ticket_source", "jira")
                    source_label = "[Jira]" if source == "jira" else "[GitHub]"
                    line = f"- {source_label} **{action['ticket_key']}**: {action['ticket_summary'] or 'N/A'}"
                    if action.get("action_details"):
                        details = action["action_details"]
                        if isinstance(details, dict):
                            detail_str = "; ".join(f"{k}: {v}" for k, v in details.items())
                            line += f" — *{detail_str}*"
                        else:
                            line += f" — *{details}*"
                    content_lines.append(line)
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
        "projects": jira_projects,
        "github_repos": github_repos,
        "by_source": by_source,
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
    custom_title: str | None = None,
    custom_summary: str | None = None,
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
        existing = (
            session.query(WeeklyReport)
            .filter(
                WeeklyReport.username == username,
                WeeklyReport.week_start == week_start,
            )
            .first()
        )

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
        reports = (
            session.query(WeeklyReport)
            .filter(
                WeeklyReport.username == username,
            )
            .order_by(WeeklyReport.week_start.desc())
            .limit(limit)
            .all()
        )

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
        report = (
            session.query(WeeklyReport)
            .filter(
                WeeklyReport.id == report_id,
            )
            .first()
        )

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
        report = (
            session.query(WeeklyReport)
            .filter(
                WeeklyReport.id == report_id,
            )
            .first()
        )

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
    content: str,
    project_key: str | None = None,
    report_period: str | None = None,
    referenced_tickets: list[str] | None = None,
) -> dict[str, Any]:
    """
    Save a management report to the database.

    The report content should be a simple bullet list of work items with embedded links.
    No summaries, no future plans - just the list of completed/in-progress items.

    Args:
        username: The author/engineer username.
        title: Report title (e.g., "Week 4, January 2026").
        content: Bullet list of work items with embedded links.
        project_key: Optional project key this report focuses on.
        report_period: Optional period (e.g., "Week 3, Jan 2026").
        referenced_tickets: Optional list of ticket keys for indexing.

    Returns:
        Saved report details with ID.
    """
    db = get_db()

    with db.session() as session:
        report = ManagementReport(
            username=username,
            title=title,
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
    username: str | None = None,
    project_key: str | None = None,
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

        reports = query.order_by(ManagementReport.created_at.desc()).limit(limit).all()

        return [
            {
                "id": r.id,
                "title": r.title,
                "project_key": r.project_key,
                "report_period": r.report_period,
                "referenced_tickets": (
                    r.referenced_tickets.split(",") if r.referenced_tickets else []
                ),
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
        report = (
            session.query(ManagementReport)
            .filter(
                ManagementReport.id == report_id,
            )
            .first()
        )

        if not report:
            return {
                "error": True,
                "message": f"Management report {report_id} not found",
            }

        return report.to_dict()


def update_management_report(
    report_id: int,
    title: str | None = None,
    content: str | None = None,
    report_period: str | None = None,
    referenced_tickets: list[str] | None = None,
) -> dict[str, Any]:
    """
    Update an existing management report.

    Args:
        report_id: The report ID to update.
        title: Optional new title.
        content: Optional new content (bullet list of work items).
        report_period: Optional new period description.
        referenced_tickets: Optional new list of referenced tickets.

    Returns:
        Updated report confirmation.
    """
    db = get_db()

    with db.session() as session:
        report = (
            session.query(ManagementReport)
            .filter(
                ManagementReport.id == report_id,
            )
            .first()
        )

        if not report:
            return {
                "error": True,
                "message": f"Management report {report_id} not found",
            }

        if title is not None:
            report.title = title
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
        report = (
            session.query(ManagementReport)
            .filter(
                ManagementReport.id == report_id,
            )
            .first()
        )

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
