"""Activity tracking and weekly report generation tools."""

import json
import logging
import os
import re
from datetime import datetime, timedelta
from typing import Any

import fnmatch

from sqlalchemy import func
from sqlalchemy.orm import joinedload

from ghost.db import (
    ActivityLog,
    ManagementReport,
    ProjectGitRepo,
    ProjectJiraComponent,
    ReportField,
    ReportProject,
    TicketSource,
    WeeklyReport,
    get_db,
)
from ghost.db.models import ActionType

logger = logging.getLogger(__name__)


def _get_jira_ticket_details(ticket_key: str, jira_client=None) -> dict | None:
    """
    Get Jira ticket details using the provided Jira client.
    
    Args:
        ticket_key: The Jira ticket key (e.g., 'PROJ-123')
        jira_client: Optional JiraClient instance for fetching ticket details
    
    Returns ticket details dict or None if not available.
    """
    if not jira_client:
        logger.debug(f"No Jira client available for auto-fetching {ticket_key}")
        return None
    
    try:
        result = jira_client.get_issue(ticket_key)
        logger.debug(f"Auto-fetched Jira ticket {ticket_key}, components: {result.get('components')}")
        return result
    except Exception as e:
        logger.warning(f"Failed to fetch Jira ticket {ticket_key}: {e}")
        return None


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


def _match_repo_pattern(repo: str, pattern: str) -> bool:
    """
    Match a GitHub repo against a pattern.
    
    Supports:
    - Exact match: "org/repo" matches "org/repo"
    - Wildcard: "org/*" matches "org/repo1", "org/repo2"
    - Glob patterns: "org/repo-*" matches "org/repo-api", "org/repo-web"
    
    Args:
        repo: The GitHub repo (e.g., "org/repo")
        pattern: The pattern to match against (e.g., "org/*")
    
    Returns:
        True if the repo matches the pattern
    """
    # Normalize both to lowercase for case-insensitive matching
    repo_lower = repo.lower()
    pattern_lower = pattern.lower()
    
    # Use fnmatch for glob-style matching
    return fnmatch.fnmatch(repo_lower, pattern_lower)


def get_activity_details(username: str, ticket_key: str) -> dict[str, Any]:
    """
    Get detailed information about a specific activity by ticket key.
    
    Args:
        username: The username to filter by
        ticket_key: The ticket key to look up
    
    Returns:
        Activity details including jira_components, detected_project_id, and full path
    """
    db = get_db()
    
    with db.session() as session:
        activity = (
            session.query(ActivityLog)
            .filter(
                ActivityLog.username == username,
                ActivityLog.ticket_key == ticket_key,
            )
            .order_by(ActivityLog.timestamp.desc())
            .first()
        )
        
        if not activity:
            return {"error": True, "message": f"No activity found for {ticket_key}"}
        
        # Get detected project info if set
        detected_project_name = None
        detected_project_path = None
        detected_field_name = None
        if activity.detected_project_id:
            project = session.query(ReportProject).filter(
                ReportProject.id == activity.detected_project_id
            ).first()
            if project:
                detected_project_name = project.name
                detected_project_path = project.get_full_name()
                if project.field:
                    detected_field_name = project.field.name
        
        return {
            "activity_id": activity.id,
            "ticket_key": activity.ticket_key,
            "ticket_summary": activity.ticket_summary,
            "project_key": activity.project_key,
            "ticket_source": activity.ticket_source.value if activity.ticket_source else None,
            "jira_components": activity.jira_components,
            "detected_project_id": activity.detected_project_id,
            "detected_project_name": detected_project_name,
            "detected_project_path": detected_project_path,
            "detected_field_name": detected_field_name,
            "github_repo": activity.github_repo,
            "action_type": activity.action_type.value if activity.action_type else None,
            "timestamp": activity.timestamp.isoformat() if activity.timestamp else None,
        }


def _build_project_tree(projects: list, parent_id=None) -> list[dict]:
    """
    Build a hierarchical tree structure from a flat list of projects.
    
    Args:
        projects: Flat list of all projects belonging to a field
        parent_id: ID of parent to build children for (None for top-level)
    
    Returns:
        List of project dicts with nested 'children' arrays
    """
    result = []
    # Get projects at this level
    level_projects = sorted(
        [p for p in projects if p.parent_id == parent_id],
        key=lambda p: p.display_order
    )
    
    for project in level_projects:
        project_data = {
            "id": project.id,
            "name": project.name,
            "description": project.description,
            "display_order": project.display_order,
            "parent_id": project.parent_id,
            "is_leaf": project.is_leaf,
            "jira_components": [
                {"jira_project_key": jc.jira_project_key, "component_name": jc.component_name}
                for jc in project.jira_components
            ],
            "git_repos": [gr.repo_pattern for gr in project.git_repos],
            "children": _build_project_tree(projects, project.id),
        }
        result.append(project_data)
    
    return result


def list_report_fields() -> dict[str, Any]:
    """
    List all report fields and their projects with configured mappings.
    
    Returns hierarchical structure with nested children.
    
    Returns:
        Dictionary with fields, their projects (hierarchical), and configured mappings.
    """
    db = get_db()
    
    with db.session() as session:
        fields = (
            session.query(ReportField)
            .options(
                joinedload(ReportField.projects)
                .joinedload(ReportProject.git_repos),
                joinedload(ReportField.projects)
                .joinedload(ReportProject.jira_components),
            )
            .order_by(ReportField.display_order)
            .all()
        )
        
        result = []
        total_projects = 0
        
        for field in fields:
            # Build hierarchical project tree
            projects_tree = _build_project_tree(list(field.projects))
            
            field_data = {
                "id": field.id,
                "name": field.name,
                "description": field.description,
                "display_order": field.display_order,
                "projects": projects_tree,
            }
            result.append(field_data)
            total_projects += len(field.projects)
        
        return {
            "fields": result,
            "total_fields": len(result),
            "total_projects": total_projects,
        }


def _get_leaf_projects_in_priority_order(projects: list, parent_id=None) -> list:
    """
    Recursively collect leaf projects (no children) in depth-first order.
    
    This ensures that detection follows the hierarchy:
    - Field display_order first
    - Then project display_order at each level
    - Depth-first traversal (parent before siblings, but only leaves returned)
    """
    result = []
    # Get projects at this level, sorted by display_order
    level_projects = sorted(
        [p for p in projects if p.parent_id == parent_id],
        key=lambda p: p.display_order
    )
    
    for project in level_projects:
        # Check if this project has children
        children = [p for p in projects if p.parent_id == project.id]
        if not children:
            # This is a leaf project - include it
            result.append(project)
        else:
            # Not a leaf - recurse into children
            result.extend(_get_leaf_projects_in_priority_order(projects, project.id))
    
    return result


def detect_project_for_activity(
    github_repo: str | None = None,
    jira_project_key: str | None = None,
    jira_components: list[str] | None = None,
    session=None,
) -> int | None:
    """
    Detect which report project an activity belongs to.
    
    Only matches against leaf projects (projects with no children).
    Matching is done in priority order:
    - Field display_order
    - Project hierarchy depth-first (following display_order at each level)
    First match wins.
    
    Args:
        github_repo: GitHub repo in 'owner/repo' format (for GitHub activities)
        jira_project_key: Jira project key (e.g., "APPENG")
        jira_components: List of Jira component names
        session: Optional SQLAlchemy session (will create one if not provided)
    
    Returns:
        project_id of the first matching leaf ReportProject, or None if no match
    """
    db = get_db()
    close_session = session is None
    
    if session is None:
        session = db.get_session()
    
    try:
        # Get all fields with their projects (including nested), ordered by display_order
        fields = (
            session.query(ReportField)
            .options(
                joinedload(ReportField.projects)
                .joinedload(ReportProject.git_repos),
                joinedload(ReportField.projects)
                .joinedload(ReportProject.jira_components),
            )
            .order_by(ReportField.display_order)
            .all()
        )
        
        # Check each field's leaf projects in priority order
        for field in fields:
            # Get leaf projects in depth-first priority order
            leaf_projects = _get_leaf_projects_in_priority_order(list(field.projects))
            
            for project in leaf_projects:
                # Check GitHub repo patterns
                if github_repo:
                    for git_repo in project.git_repos:
                        if _match_repo_pattern(github_repo, git_repo.repo_pattern):
                            logger.debug(
                                f"Activity matched leaf project {project.get_full_name()} via git repo "
                                f"pattern {git_repo.repo_pattern}"
                            )
                            return project.id
                
                # Check Jira components
                if jira_project_key and jira_components:
                    for jira_comp in project.jira_components:
                        if (
                            jira_comp.jira_project_key.upper() == jira_project_key.upper()
                            and jira_comp.component_name.lower() in [c.lower() for c in jira_components]
                        ):
                            logger.debug(
                                f"Activity matched leaf project {project.get_full_name()} via Jira component "
                                f"{jira_comp.jira_project_key}/{jira_comp.component_name}"
                            )
                            return project.id
        
        return None
    
    finally:
        if close_session:
            session.close()


def redetect_project_assignments(
    username: str | None = None,
    limit: int = 1000,
    jira_client=None,
) -> dict[str, Any]:
    """
    Re-run project detection on existing activities.
    
    Useful after configuration changes to update detected_project_id
    on historical activities.
    
    Args:
        username: Optional filter to only redetect for a specific user
        limit: Maximum number of activities to process
        jira_client: Optional JiraClient for auto-fetching ticket components
    
    Returns:
        Summary of redetection results
    """
    db = get_db()
    
    updated_count = 0
    processed_count = 0
    
    with db.session() as session:
        # Query activities that need redetection
        query = session.query(ActivityLog)
        
        if username:
            query = query.filter(ActivityLog.username == username)
        
        activities = query.order_by(ActivityLog.timestamp.desc()).limit(limit).all()
        
        for activity in activities:
            processed_count += 1
            
            # Parse jira_components string to list
            components_list = None
            if activity.jira_components:
                components_list = [c.strip() for c in activity.jira_components.split(",") if c.strip()]
            
            # Auto-fetch Jira components if missing for Jira tickets
            if activity.ticket_source == TicketSource.JIRA and not components_list:
                ticket_details = _get_jira_ticket_details(activity.ticket_key, jira_client)
                if ticket_details and ticket_details.get("components"):
                    components_list = ticket_details["components"]
                    # Also update the stored components
                    activity.jira_components = ",".join(components_list)
                    logger.info(f"Auto-fetched and stored Jira components for {activity.ticket_key}: {components_list}")
            
            # Detect project
            new_project_id = detect_project_for_activity(
                github_repo=activity.github_repo,
                jira_project_key=activity.project_key,
                jira_components=components_list,
                session=session,
            )
            
            # Update if changed
            if new_project_id != activity.detected_project_id:
                activity.detected_project_id = new_project_id
                updated_count += 1
    
    logger.info(f"Redetection complete: {updated_count} activities updated out of {processed_count} processed")
    
    return {
        "success": True,
        "processed_count": processed_count,
        "updated_count": updated_count,
        "message": f"Redetected {updated_count} activities out of {processed_count} processed",
    }


def log_activity(
    username: str,
    ticket_key: str,
    action_type: str,
    ticket_summary: str | None = None,
    project_key: str | None = None,
    github_repo: str | None = None,
    jira_components: list[str] | None = None,
    action_details: dict | None = None,
    jira_client=None,
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
        jira_components: Optional list of Jira component names for auto-detection.
        action_details: Optional dict with additional context.
        jira_client: Optional JiraClient for auto-fetching ticket components.

    Returns:
        Confirmation with activity ID, detected source, and detected project.
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

    # Auto-fetch Jira components if this is a Jira ticket and components not provided
    if source == TicketSource.JIRA and not jira_components:
        ticket_details = _get_jira_ticket_details(normalized_key, jira_client)
        if ticket_details and ticket_details.get("components"):
            jira_components = ticket_details["components"]
            logger.info(f"Auto-fetched Jira components for {normalized_key}: {jira_components}")

    # Convert jira_components list to comma-separated string
    jira_components_str = None
    if jira_components:
        jira_components_str = ",".join(jira_components)

    with db.session() as session:
        # Auto-detect project for report consolidation
        detected_project_id = detect_project_for_activity(
            github_repo=final_github_repo,
            jira_project_key=final_project_key,
            jira_components=jira_components,
            session=session,
        )
        
        activity = ActivityLog(
            username=username,
            ticket_key=normalized_key,
            ticket_summary=ticket_summary,
            project_key=final_project_key,
            ticket_source=source,
            github_repo=final_github_repo,
            jira_components=jira_components_str,
            detected_project_id=detected_project_id,
            action_type=action_enum,
            action_details=json.dumps(action_details) if action_details else None,
            timestamp=datetime.utcnow(),
        )
        session.add(activity)
        session.flush()
        activity_id = activity.id
        
        # Get project name for logging
        detected_project_name = None
        if detected_project_id:
            project = session.query(ReportProject).filter(ReportProject.id == detected_project_id).first()
            if project:
                detected_project_name = project.name

    log_msg = f"Logged activity {activity_id}: {username} {action_type} {normalized_key} (source: {source.value})"
    if detected_project_name:
        log_msg += f" -> detected project: {detected_project_name}"
    logger.info(log_msg)

    return {
        "success": True,
        "activity_id": activity_id,
        "ticket_source": source.value,
        "ticket_key": normalized_key,
        "detected_project_id": detected_project_id,
        "detected_project_name": detected_project_name,
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


def _get_ticket_link(ticket_key: str, source: str, github_repo: str | None = None) -> str:
    """
    Generate a clickable markdown link for a ticket.

    Args:
        ticket_key: The ticket key (e.g., PROJ-123 or owner/repo#123)
        source: The ticket source ('jira' or 'github')
        github_repo: GitHub repository in 'owner/repo' format (for GitHub issues)

    Returns:
        Markdown link string for the ticket
    """
    if source == "github":
        # For GitHub issues, extract issue number and construct URL
        if "#" in ticket_key:
            # Extract repo and issue number from key like "owner/repo#123"
            parts = ticket_key.split("#")
            if len(parts) == 2:
                repo = parts[0] if parts[0] else github_repo
                issue_num = parts[1]
                if repo:
                    return f"[{ticket_key}](https://github.com/{repo}/issues/{issue_num})"
        return ticket_key  # Fallback to plain text if can't parse
    else:
        # For Jira tickets, use the JIRA_SERVER_URL from environment
        jira_url = os.environ.get("JIRA_SERVER_URL", "").rstrip("/")
        if jira_url:
            return f"[{ticket_key}]({jira_url}/browse/{ticket_key})"
        return ticket_key  # Fallback to plain text if no URL configured


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
    by_source = activity.get("by_source", {"jira": 0, "github": 0})

    # Calculate statistics
    total_tickets = len(unique_tickets)
    jira_projects = list(
        set(t["project_key"] for t in unique_tickets if t["project_key"])
    )
    github_repos = list(
        set(t["github_repo"] for t in unique_tickets if t["github_repo"])
    )

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
            # Generate clickable link for the ticket
            ticket_link = _get_ticket_link(
                ticket["ticket_key"], source, ticket.get("github_repo")
            )
            content_lines.append(
                f"| {source_label} | {ticket_link} | {summary_text} | "
                f"{project_or_repo} | {ticket['action_count']} |"
            )

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


def _get_activity_visibility(ticket_key: str, username: str, session) -> bool | None:
    """
    Get the visibility setting for an activity by ticket key.
    
    Returns the visible_to_manager value of the most recent matching activity,
    or None if no activity found.
    """
    activity = (
        session.query(ActivityLog)
        .filter(
            ActivityLog.username == username,
            ActivityLog.ticket_key == ticket_key,
        )
        .order_by(ActivityLog.timestamp.desc())
        .first()
    )
    return activity.visible_to_manager if activity else None


def _extract_ticket_key_from_text(text: str) -> str | None:
    """
    Extract a ticket key from text containing Jira or GitHub URLs.
    
    Supports:
    - Jira URLs: https://issues.redhat.com/browse/PROJ-123 -> PROJ-123
    - GitHub issue URLs: https://github.com/owner/repo/issues/123 -> owner/repo#123
    - GitHub PR URLs: https://github.com/owner/repo/pull/123 -> owner/repo#123
    
    Returns the first ticket key found, or None if no ticket key is detected.
    """
    # Try Jira URL pattern first (e.g., https://issues.redhat.com/browse/APPENG-4347)
    jira_pattern = r'https?://[^/]+/browse/([A-Z][A-Z0-9]+-\d+)'
    jira_match = re.search(jira_pattern, text)
    if jira_match:
        return jira_match.group(1)
    
    # Try GitHub issue/PR URL pattern (e.g., https://github.com/owner/repo/issues/123)
    github_pattern = r'https?://github\.com/([^/]+/[^/]+)/(?:issues|pull)/(\d+)'
    github_match = re.search(github_pattern, text)
    if github_match:
        return f"{github_match.group(1)}#{github_match.group(2)}"
    
    # Try plain Jira ticket key pattern (e.g., PROJ-123 in text)
    plain_jira_pattern = r'\b([A-Z][A-Z0-9]+-\d+)\b'
    plain_match = re.search(plain_jira_pattern, text)
    if plain_match:
        return plain_match.group(1)
    
    return None


def _serialize_entries_to_content(entries: list[dict[str, Any]]) -> str:
    """Serialize structured entries to JSON content for storage."""
    serialized_entries = []
    for e in entries:
        entry_dict = {"text": e.get("text", ""), "private": e.get("private", False)}
        if e.get("ticket_key"):
            entry_dict["ticket_key"] = e.get("ticket_key")
        serialized_entries.append(entry_dict)
    return json.dumps({
        "format": "structured",
        "entries": serialized_entries
    })


def save_management_report(
    username: str,
    title: str,
    content: str | None = None,
    entries: list[dict[str, Any]] | None = None,
    project_key: str | None = None,
    report_period: str | None = None,
    referenced_tickets: list[str] | None = None,
) -> dict[str, Any]:
    """
    Save a management report to the database.

    The report content can be either:
    - Plain text (legacy): A simple bullet list of work items with embedded links.
    - Structured entries: A list of entry objects with text and visibility control.

    When using structured entries, each entry can include a ticket_key to auto-detect
    visibility from the corresponding activity's visible_to_manager setting.

    Args:
        username: The author/engineer username.
        title: Report title (e.g., "Week 4, January 2026").
        content: (Legacy) Bullet list of work items with embedded links.
        entries: (New) List of entry dicts with keys: text, private (bool), ticket_key (optional).
                 If ticket_key is provided, visibility is auto-detected from activity settings.
        project_key: Optional project key this report focuses on.
        report_period: Optional period (e.g., "Week 3, Jan 2026").
        referenced_tickets: Optional list of ticket keys for indexing.

    Returns:
        Saved report details with ID.
    """
    db = get_db()

    with db.session() as session:
        # Process entries if provided
        if entries is not None:
            processed_entries = []
            for entry in entries:
                text = entry.get("text", "")
                private = entry.get("private", False)
                ticket_key = entry.get("ticket_key")
                
                # Auto-detect ticket_key from text if not provided
                if not ticket_key and text:
                    ticket_key = _extract_ticket_key_from_text(text)
                
                # Auto-detect visibility from activity if ticket_key is available
                if ticket_key and not private:
                    activity_visibility = _get_activity_visibility(ticket_key, username, session)
                    if activity_visibility is False:
                        # Activity is explicitly hidden, so mark entry as private
                        private = True
                
                processed_entries.append({"text": text, "private": private, "ticket_key": ticket_key})
            
            final_content = _serialize_entries_to_content(processed_entries)
        elif content is not None:
            final_content = content
        else:
            final_content = ""
        
        report = ManagementReport(
            username=username,
            title=title,
            content=final_content,
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
    entries: list[dict[str, Any]] | None = None,
    report_period: str | None = None,
    referenced_tickets: list[str] | None = None,
) -> dict[str, Any]:
    """
    Update an existing management report.

    Args:
        report_id: The report ID to update.
        title: Optional new title.
        content: (Legacy) Optional new content (bullet list of work items).
        entries: (New) Optional list of entry dicts with keys: text, private (bool).
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
        
        # Handle content update - prefer entries over plain content
        if entries is not None:
            processed_entries = []
            for entry in entries:
                text = entry.get("text", "")
                private = entry.get("private", False)
                ticket_key = entry.get("ticket_key")
                
                # Auto-detect ticket_key from text if not provided
                if not ticket_key and text:
                    ticket_key = _extract_ticket_key_from_text(text)
                
                # Auto-detect visibility from activity if ticket_key is available
                if ticket_key and not private:
                    activity_visibility = _get_activity_visibility(ticket_key, report.username, session)
                    if activity_visibility is False:
                        private = True
                
                processed_entries.append({"text": text, "private": private, "ticket_key": ticket_key})
            
            report.content = _serialize_entries_to_content(processed_entries)
        elif content is not None:
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
