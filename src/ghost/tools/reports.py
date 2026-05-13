"""Management report tools."""

import json
import logging
import re
from datetime import datetime
from typing import Any

import fnmatch

from sqlalchemy.orm import joinedload

from ghost.db import (
    ManagementReport,
    ProjectGitRepo,
    ProjectJiraComponent,
    ReportField,
    ReportProject,
    TicketSource,
    get_db,
)

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
        return TicketSource.GITHUB, ticket_key, None, repo

    # Check for short GitHub format (#123)
    short_match = re.match(github_short_pattern, ticket_key)
    if short_match and github_repo:
        issue_num = short_match.group(1)
        full_key = f"{github_repo}#{issue_num}"
        return TicketSource.GITHUB, full_key, None, github_repo

    # Default: Jira ticket (PROJ-123 format)
    project_key = None
    if "-" in ticket_key:
        project_key = ticket_key.split("-")[0]

    return TicketSource.JIRA, ticket_key, project_key, None


def _match_repo_pattern(repo: str, pattern: str) -> bool:
    """
    Match a GitHub repo against a pattern.

    Supports exact match, wildcard (*), and glob patterns.
    """
    return fnmatch.fnmatch(repo.lower(), pattern.lower())


def _build_project_tree(projects: list, parent_id=None) -> list[dict]:
    """
    Build a hierarchical tree structure from a flat list of projects.
    """
    result = []
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
    """
    result = []
    level_projects = sorted(
        [p for p in projects if p.parent_id == parent_id],
        key=lambda p: p.display_order
    )

    for project in level_projects:
        children = [p for p in projects if p.parent_id == project.id]
        if not children:
            result.append(project)
        else:
            result.extend(_get_leaf_projects_in_priority_order(projects, project.id))

    return result


def detect_project_for_activity(
    github_repo: str | None = None,
    jira_project_key: str | None = None,
    jira_components: list[str] | None = None,
    session=None,
) -> int | None:
    """
    Detect which report project a ticket belongs to.

    Only matches against leaf projects (projects with no children).
    Matching is done in priority order: field display_order then project
    hierarchy depth-first. First match wins.

    Args:
        github_repo: GitHub repo in 'owner/repo' format
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

        for field in fields:
            leaf_projects = _get_leaf_projects_in_priority_order(list(field.projects))

            for project in leaf_projects:
                if github_repo:
                    for git_repo in project.git_repos:
                        if _match_repo_pattern(github_repo, git_repo.repo_pattern):
                            logger.debug(
                                f"Ticket matched leaf project {project.get_full_name()} via git repo "
                                f"pattern {git_repo.repo_pattern}"
                            )
                            return project.id

                if jira_project_key and jira_components:
                    for jira_comp in project.jira_components:
                        if (
                            jira_comp.jira_project_key.upper() == jira_project_key.upper()
                            and jira_comp.component_name.lower() in [c.lower() for c in jira_components]
                        ):
                            logger.debug(
                                f"Ticket matched leaf project {project.get_full_name()} via Jira component "
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
    Re-run project detection on existing management report entries.

    Useful after configuration changes to update detected_project_id
    on historical report entries.

    Args:
        username: Optional filter to only redetect for a specific user
        limit: Maximum number of reports to process

    Returns:
        Summary of redetection results
    """
    db = get_db()

    updated_count = 0
    processed_count = 0

    with db.session() as session:
        query = session.query(ManagementReport)

        if username:
            query = query.filter(ManagementReport.username == username)

        reports = query.order_by(ManagementReport.created_at.desc()).limit(limit).all()

        for report in reports:
            # Only process structured content
            try:
                data = json.loads(report.content)
                if not isinstance(data, dict) or data.get("format") != "structured":
                    continue
                entries = data.get("entries", [])
            except (json.JSONDecodeError, TypeError):
                continue

            entries_changed = False
            new_entries = []
            for entry in entries:
                processed_count += 1
                ticket_key = entry.get("ticket_key")

                if not ticket_key:
                    new_entries.append(entry)
                    continue

                _, _, proj_key, gh_repo = _parse_ticket_key(ticket_key)
                new_project_id = detect_project_for_activity(
                    github_repo=gh_repo,
                    jira_project_key=proj_key,
                    jira_components=None,
                    session=session,
                )

                if new_project_id != entry.get("detected_project_id"):
                    entry = dict(entry)
                    entry["detected_project_id"] = new_project_id
                    updated_count += 1
                    entries_changed = True

                new_entries.append(entry)

            if entries_changed:
                data["entries"] = new_entries
                report.content = json.dumps(data)

    logger.info(f"Redetection complete: {updated_count} entries updated out of {processed_count} processed")

    return {
        "success": True,
        "processed_count": processed_count,
        "updated_count": updated_count,
        "message": f"Redetected {updated_count} entries out of {processed_count} processed",
    }


# =============================================================================
# Management Reports
# =============================================================================


def _extract_ticket_key_from_text(text: str) -> str | None:
    """
    Extract a ticket key from text containing Jira or GitHub URLs.

    Supports:
    - Jira URLs: https://redhat.atlassian.net/browse/PROJ-123 -> PROJ-123
    - GitHub issue URLs: https://github.com/owner/repo/issues/123 -> owner/repo#123
    - GitHub PR URLs: https://github.com/owner/repo/pull/123 -> owner/repo#123
    """
    jira_pattern = r'https?://[^/]+/browse/([A-Z][A-Z0-9]+-\d+)'
    jira_match = re.search(jira_pattern, text)
    if jira_match:
        return jira_match.group(1)

    github_pattern = r'https?://github\.com/([^/]+/[^/]+)/(?:issues|pull)/(\d+)'
    github_match = re.search(github_pattern, text)
    if github_match:
        return f"{github_match.group(1)}#{github_match.group(2)}"

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
    Resolve detected_project_id for each entry using ticket_key + field/project config.

    Runs during report creation/update so entries carry their own project
    assignment and the consolidated view never needs external queries at read time.

    For each entry with a ticket_key, the key is parsed to extract source/project/repo
    info which is matched against configured field/project rules.
    Manual overrides (detected_project_id already set on entry) are preserved as-is.
    """
    result = []
    for e in entries:
        entry = dict(e)
        if entry.get("detected_project_id") is not None:
            # Manual override — keep as-is
            result.append(entry)
            continue
        tk = entry.get("ticket_key")
        if tk:
            _, _, proj_key, gh_repo = _parse_ticket_key(tk)
            detected = detect_project_for_activity(
                github_repo=gh_repo,
                jira_project_key=proj_key,
                jira_components=None,
                session=session,
            )
            entry["detected_project_id"] = detected
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

    Each entry can include a ticket_key for automatic project detection via the
    configured field/project rules.

    Args:
        username: The author/engineer username.
        title: Report title (e.g., "Week 4, January 2026").
        content: (Legacy) Bullet list of work items with embedded links.
        entries: (New) List of entry dicts with keys: text, private (bool), ticket_key (optional).
        project_key: Optional project key this report focuses on.
        report_period: Optional period (e.g., "Week 3, Jan 2026").
        referenced_tickets: Optional list of ticket keys for indexing.

    Returns:
        Saved report details with ID.
    """
    db = get_db()

    with db.session() as session:
        if entries is not None:
            processed_entries = []
            for entry in entries:
                text = entry.get("text", "")
                private = entry.get("private", False)
                ticket_key = entry.get("ticket_key")

                # Auto-detect ticket_key from text if not provided
                if not ticket_key and text:
                    ticket_key = _extract_ticket_key_from_text(text)

                processed_entries.append({
                    "text": text, "private": private, "ticket_key": ticket_key,
                    "detected_project_id": entry.get("detected_project_id"),
                })

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
    """
    db = get_db()

    with db.session() as session:
        report = (
            session.query(ManagementReport)
            .filter(ManagementReport.id == report_id)
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
    """
    db = get_db()

    with db.session() as session:
        report = (
            session.query(ManagementReport)
            .filter(ManagementReport.id == report_id)
            .first()
        )

        if not report:
            return {
                "error": True,
                "message": f"Management report {report_id} not found",
            }

        if title is not None:
            report.title = title

        if entries is not None:
            processed_entries = []
            for entry in entries:
                text = entry.get("text", "")
                private = entry.get("private", False)
                ticket_key = entry.get("ticket_key")

                if not ticket_key and text:
                    ticket_key = _extract_ticket_key_from_text(text)

                processed_entries.append({
                    "text": text, "private": private, "ticket_key": ticket_key,
                    "detected_project_id": entry.get("detected_project_id"),
                })

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
    """
    db = get_db()

    with db.session() as session:
        report = (
            session.query(ManagementReport)
            .filter(ManagementReport.id == report_id)
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
