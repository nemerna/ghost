"""Activity tracking and management report tools."""

import json
import logging
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
    get_db,
)
from ghost.db.models import ActionType

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
) -> dict[str, Any]:
    """
    Re-run project detection on existing activities.
    
    Useful after configuration changes to update detected_project_id
    on historical activities.
    
    Args:
        username: Optional filter to only redetect for a specific user
        limit: Maximum number of activities to process
    
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


def _resolve_entry_projects(
    entries: list[dict[str, Any]],
    username: str,
    session,
) -> list[dict[str, Any]]:
    """
    Resolve detected_project_id for each entry from existing ActivityLog data.

    This runs during report creation/update so entries carry their own project
    assignment and the consolidated view never needs to query ActivityLog or
    reach out to Jira MCP at read time.

    For each entry with a ticket_key:
    1. Look up the most recent ActivityLog for that ticket to get its
       already-stored detected_project_id.
    2. If no activity exists, fall back to basic detection using only the
       ticket key format (Jira project key or GitHub repo pattern).
    """
    ticket_keys = {e.get("ticket_key") for e in entries if e.get("ticket_key")}
    if not ticket_keys:
        return entries

    # Batch-query ActivityLog for all ticket keys at once
    ticket_to_project: dict[str, int | None] = {}
    ticket_to_meta: dict[str, tuple[str | None, str | None, str | None]] = {}

    activities = (
        session.query(
            ActivityLog.ticket_key,
            ActivityLog.detected_project_id,
            ActivityLog.project_key,
            ActivityLog.github_repo,
            ActivityLog.jira_components,
        )
        .filter(
            ActivityLog.username == username,
            ActivityLog.ticket_key.in_(ticket_keys),
        )
        .order_by(ActivityLog.timestamp.desc())
        .all()
    )

    for tk, proj_id, proj_key, gh_repo, jira_comps in activities:
        if tk not in ticket_to_project:
            ticket_to_project[tk] = proj_id
            ticket_to_meta[tk] = (proj_key, gh_repo, jira_comps)

    # For ticket keys with no activity, try basic detection from ticket key format
    for tk in ticket_keys:
        if tk in ticket_to_project:
            continue
        source, normalized, proj_key, gh_repo = _parse_ticket_key(tk)
        detected = detect_project_for_activity(
            github_repo=gh_repo,
            jira_project_key=proj_key,
            jira_components=None,
            session=session,
        )
        ticket_to_project[tk] = detected

    # For entries whose activity had no detected_project_id, attempt detection
    # using the metadata we already have (no Jira MCP call)
    for tk, proj_id in list(ticket_to_project.items()):
        if proj_id is not None:
            continue
        meta = ticket_to_meta.get(tk)
        if not meta:
            continue
        proj_key, gh_repo, jira_comps = meta
        comps_list = (
            [c.strip() for c in jira_comps.split(",") if c.strip()]
            if jira_comps
            else None
        )
        detected = detect_project_for_activity(
            github_repo=gh_repo,
            jira_project_key=proj_key,
            jira_components=comps_list,
            session=session,
        )
        if detected:
            ticket_to_project[tk] = detected

    # Stamp detected_project_id onto each entry, preserving manual overrides
    result = []
    for e in entries:
        entry = dict(e)
        if entry.get("detected_project_id") is not None:
            # Manual override — keep as-is
            result.append(entry)
            continue
        tk = entry.get("ticket_key")
        if tk and tk in ticket_to_project:
            entry["detected_project_id"] = ticket_to_project[tk]
        result.append(entry)

    return result


def _serialize_entries_to_content(entries: list[dict[str, Any]]) -> str:
    """Serialize structured entries to JSON content for storage."""
    serialized_entries = []
    for e in entries:
        entry_dict = {"text": e.get("text", ""), "private": e.get("private", False)}
        if e.get("ticket_key"):
            entry_dict["ticket_key"] = e.get("ticket_key")
        if e.get("detected_project_id") is not None:
            entry_dict["detected_project_id"] = e.get("detected_project_id")
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
                        private = True
                
                processed_entries.append({
                    "text": text, "private": private, "ticket_key": ticket_key,
                    "detected_project_id": entry.get("detected_project_id"),
                })
            
            # Resolve field/project assignments (preserves manual overrides)
            processed_entries = _resolve_entry_projects(processed_entries, username, session)
            
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
                
                processed_entries.append({
                    "text": text, "private": private, "ticket_key": ticket_key,
                    "detected_project_id": entry.get("detected_project_id"),
                })
            
            # Resolve field/project assignments (preserves manual overrides)
            processed_entries = _resolve_entry_projects(processed_entries, report.username, session)
            
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
