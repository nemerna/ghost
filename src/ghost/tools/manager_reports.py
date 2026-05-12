"""Manager-facing MCP tool implementations.

These tools are only accessible to users with the MANAGER or ADMIN role.
Each tool resolves the caller's managed team from the DB; admins may pass
an optional team_id override.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import joinedload

from ghost.db import (
    ConsolidatedReportSnapshot,
    ManagementReport,
    ReportField,
    Team,
    TeamMembership,
    User,
    UserRole,
    get_db,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Internal helpers (adapted from api/routes/reports.py)
# =============================================================================


@dataclass
class _ReportEntry:
    text: str
    private: bool = False
    ticket_key: str | None = None
    detected_project_id: int | None = None


def _get_user_visibility_defaults(user: User) -> dict:
    """Get visibility defaults from user preferences."""
    preferences = json.loads(user.preferences) if user.preferences else {}
    return preferences.get("visibility_defaults", {"management_reports": "private"})


def _is_report_visible_to_manager(
    report: ManagementReport, visibility_defaults: dict
) -> bool:
    """Check if a management report is visible to the manager."""
    if report.visible_to_manager is not None:
        return report.visible_to_manager
    return visibility_defaults.get("management_reports", "private") == "shared"


def _parse_structured_content(content: str) -> list[_ReportEntry]:
    """Parse structured JSON content from a management report."""
    if not content:
        return []
    content_stripped = content.strip()
    if not content_stripped.startswith('{"format":'):
        return []
    try:
        data = json.loads(content)
        if data.get("format") != "structured" or "entries" not in data:
            return []
        return [
            _ReportEntry(
                text=e.get("text", ""),
                private=e.get("private", False),
                ticket_key=e.get("ticket_key"),
                detected_project_id=e.get("detected_project_id"),
            )
            for e in data.get("entries", [])
        ]
    except (json.JSONDecodeError, TypeError):
        return []


def _resolve_manager_team(
    session,
    manager_user_id: int,
    team_id_override: int | None,
) -> tuple[User, Team]:
    """Resolve the manager user and their team.

    Admins may pass an explicit team_id override; managers always get their
    own managed team (Team.manager_id == user.id).
    """
    user = session.query(User).filter(User.id == manager_user_id).first()
    if not user:
        raise ValueError("Manager user not found")

    if team_id_override is not None:
        if user.role != UserRole.ADMIN:
            raise ValueError("Only admins can specify a team_id override")
        team = session.query(Team).filter(Team.id == team_id_override).first()
        if not team:
            raise ValueError(f"Team {team_id_override} not found")
        return user, team

    team = session.query(Team).filter(Team.manager_id == manager_user_id).first()
    if not team:
        raise ValueError("No managed team found for this manager")
    return user, team


def _count_project_entries(projects: list[dict]) -> int:
    """Recursively count individual bullet entries across all projects."""
    total = 0
    for p in projects:
        total += sum(len(e.get("entries", [])) for e in p.get("entries", []))
        total += _count_project_entries(p.get("children", []))
    return total


# =============================================================================
# Tool implementations
# =============================================================================


def get_consolidated_report(
    manager_user_id: int,
    report_period: str | None = None,
    team_id_override: int | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    """Get consolidated management reports grouped by Field → Project → Entries.

    Returns reports from the manager's team for the given period (current week
    by default). Only entries that team members have made visible to their
    manager are included.
    """
    db = get_db()

    with db.session() as session:
        user, team = _resolve_manager_team(session, manager_user_id, team_id_override)
        team_id = team.id

        # Collect team member emails (members + the manager themselves)
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
        email_to_visibility = {m.email: _get_user_visibility_defaults(m) for m in members}

        # Fetch reports for the target period
        query = session.query(ManagementReport).filter(
            ManagementReport.username.in_(member_emails)
        )

        if report_period:
            query = query.filter(ManagementReport.report_period == report_period)
        else:
            today = datetime.utcnow().date()
            current_monday = today - timedelta(days=today.weekday())
            current_sunday = current_monday + timedelta(days=6)
            week_start = datetime.combine(current_monday, datetime.min.time())
            week_end = datetime.combine(current_sunday, datetime.max.time())
            query = query.filter(
                ManagementReport.created_at >= week_start,
                ManagementReport.created_at <= week_end,
            )

        all_reports = query.order_by(ManagementReport.created_at.desc()).limit(limit).all()

        # Filter to only reports visible to the manager
        visible_reports = [
            r
            for r in all_reports
            if _is_report_visible_to_manager(r, email_to_visibility.get(r.username, {}))
        ]

        # Keep only the latest report per user for consolidation
        latest_by_user: dict[str, ManagementReport] = {}
        for report in visible_reports:
            if report.username not in latest_by_user:
                latest_by_user[report.username] = report

        # Load fields with all their projects
        fields = (
            session.query(ReportField)
            .options(joinedload(ReportField.projects))
            .order_by(ReportField.display_order)
            .all()
        )

        project_to_field: dict[int, tuple] = {
            project.id: (field, project)
            for field in fields
            for project in field.projects
        }

        # Group parsed entries by detected project
        entries_by_project: dict[int, list[dict]] = {}
        uncategorized: list[dict] = []

        for username, report in latest_by_user.items():
            parsed = _parse_structured_content(report.content)
            grouped: dict[int | None, list[tuple[int, str]]] = {}
            for idx, entry in enumerate(parsed):
                if entry.private:
                    continue
                grouped.setdefault(entry.detected_project_id, []).append((idx, entry.text))

            for proj_id, proj_entries in grouped.items():
                consolidated_entry = {
                    "username": username,
                    "report_id": report.id,
                    "title": report.title,
                    "content": "\n".join(f"- {text}" for _, text in proj_entries),
                    "entries": [{"text": text, "index": idx} for idx, text in proj_entries],
                    "report_period": report.report_period,
                    "created_at": report.created_at.isoformat() if report.created_at else None,
                }
                if proj_id and proj_id in project_to_field:
                    entries_by_project.setdefault(proj_id, []).append(consolidated_entry)
                else:
                    uncategorized.append(consolidated_entry)

        # Build hierarchical field → project → entries response
        def _build_project_tree(projects: list, parent_id: int | None) -> list[dict]:
            result = []
            for project in sorted(
                [p for p in projects if p.parent_id == parent_id],
                key=lambda p: p.display_order,
            ):
                children = _build_project_tree(projects, project.id)
                is_leaf = len(children) == 0
                proj_entries = entries_by_project.get(project.id, []) if is_leaf else []
                has_entries = bool(proj_entries)
                has_child_entries = any(
                    c.get("entries") or c.get("children") for c in children
                )
                if has_entries or has_child_entries:
                    result.append(
                        {
                            "id": project.id,
                            "name": project.name,
                            "description": project.description,
                            "parent_id": project.parent_id,
                            "is_leaf": is_leaf,
                            "entries": proj_entries,
                            "children": children,
                        }
                    )
            return result

        consolidated_fields = []
        for field in fields:
            field_projects = _build_project_tree(list(field.projects), None)
            if field_projects:
                consolidated_fields.append(
                    {
                        "id": field.id,
                        "name": field.name,
                        "description": field.description,
                        "projects": field_projects,
                    }
                )

        total_entries = (
            sum(_count_project_entries(f["projects"]) for f in consolidated_fields)
            + sum(len(e.get("entries", [])) for e in uncategorized)
        )

        if not report_period:
            now = datetime.utcnow()
            week_num = now.isocalendar()[1]
            report_period = f"Week {week_num}, {now.strftime('%b %Y')}"

        return {
            "team_id": team_id,
            "team_name": team.name,
            "report_period": report_period,
            "fields": consolidated_fields,
            "uncategorized": uncategorized,
            "total_entries": total_entries,
        }


def get_filtered_report(
    manager_user_id: int,
    field_ids: list[int] | None = None,
    project_ids: list[int] | None = None,
    report_period: str | None = None,
    team_id_override: int | None = None,
) -> dict[str, Any]:
    """Get a filtered consolidated report restricted to specified fields/projects.

    Useful for producing stakeholder-specific sub-reports from the full team rollup.
    Uncategorized entries are excluded from filtered results.
    """
    full = get_consolidated_report(
        manager_user_id=manager_user_id,
        report_period=report_period,
        team_id_override=team_id_override,
    )

    filter_field_ids: set[int] = set(field_ids) if field_ids else set()
    filter_project_ids: set[int] = set(project_ids) if project_ids else set()

    if not filter_field_ids and not filter_project_ids:
        return full

    def _filter_projects(projects: list[dict], proj_filter: set[int]) -> list[dict]:
        result = []
        for project in projects:
            filtered_children = _filter_projects(project.get("children", []), proj_filter)
            should_include = (
                not proj_filter
                or project["id"] in proj_filter
                or bool(filtered_children)
            )
            if should_include:
                result.append({**project, "children": filtered_children})
        return result

    filtered_fields = []
    for field in full["fields"]:
        if filter_field_ids and field["id"] not in filter_field_ids:
            continue
        filtered_projects = _filter_projects(
            field["projects"],
            filter_project_ids if filter_project_ids else set(),
        )
        if filtered_projects:
            filtered_fields.append({**field, "projects": filtered_projects})

    total_entries = sum(_count_project_entries(f["projects"]) for f in filtered_fields)

    return {
        "team_id": full["team_id"],
        "team_name": full["team_name"],
        "report_period": full["report_period"],
        "fields": filtered_fields,
        "uncategorized": [],
        "total_entries": total_entries,
    }


def get_team_progress(
    manager_user_id: int,
    week_offset: int = 0,
    team_id_override: int | None = None,
) -> dict[str, Any]:
    """Get per-member reporting progress for a given week.

    Returns done / in_progress / missing status for each team member, plus
    summary counts. Week 0 = current week, -1 = last week, etc.
    """
    db = get_db()

    today = datetime.utcnow().date()
    current_monday = today - timedelta(days=today.weekday())
    target_monday = current_monday + timedelta(weeks=week_offset)
    target_sunday = target_monday + timedelta(days=6)
    week_start = datetime.combine(target_monday, datetime.min.time())
    week_end = datetime.combine(target_sunday, datetime.max.time())

    with db.session() as session:
        _, team = _resolve_manager_team(session, manager_user_id, team_id_override)
        team_id = team.id

        memberships = (
            session.query(TeamMembership)
            .filter(TeamMembership.team_id == team_id)
            .all()
        )
        member_ids = [m.user_id for m in memberships]
        if team.manager_id:
            member_ids.append(team.manager_id)

        members = session.query(User).filter(User.id.in_(member_ids)).all()
        email_to_user = {m.email: m for m in members}
        email_to_visibility = {m.email: _get_user_visibility_defaults(m) for m in members}

        reports = (
            session.query(ManagementReport)
            .filter(
                ManagementReport.username.in_(list(email_to_user.keys())),
                ManagementReport.created_at >= week_start,
                ManagementReport.created_at <= week_end,
            )
            .order_by(ManagementReport.created_at.desc())
            .all()
        )

        reports_by_user: dict[str, list[ManagementReport]] = {}
        for report in reports:
            reports_by_user.setdefault(report.username, []).append(report)

        done_count = in_progress_count = missing_count = 0
        member_statuses = []

        for email, u in email_to_user.items():
            user_reports = reports_by_user.get(email, [])
            if not user_reports:
                status = "missing"
                missing_count += 1
                member_statuses.append(
                    {
                        "user_id": u.id,
                        "email": email,
                        "display_name": u.display_name,
                        "status": status,
                        "report_count": 0,
                        "latest_report_title": None,
                        "latest_report_updated_at": None,
                    }
                )
            else:
                vis_defaults = email_to_visibility.get(email, {})
                has_visible = any(
                    _is_report_visible_to_manager(r, vis_defaults) for r in user_reports
                )
                latest = user_reports[0]
                updated = latest.updated_at or latest.created_at
                if has_visible:
                    status = "done"
                    done_count += 1
                else:
                    status = "in_progress"
                    in_progress_count += 1

                member_statuses.append(
                    {
                        "user_id": u.id,
                        "email": email,
                        "display_name": u.display_name,
                        "status": status,
                        "report_count": len(user_reports),
                        "latest_report_title": latest.title,
                        "latest_report_updated_at": updated.isoformat() if updated else None,
                    }
                )

        status_order = {"missing": 0, "in_progress": 1, "done": 2}
        member_statuses.sort(key=lambda m: status_order.get(m["status"], 3))

        return {
            "team_id": team_id,
            "team_name": team.name,
            "week_start": target_monday.isoformat(),
            "week_end": target_sunday.isoformat(),
            "members": member_statuses,
            "summary": {
                "done": done_count,
                "in_progress": in_progress_count,
                "missing": missing_count,
                "total": len(members),
            },
        }


def get_member_history(
    manager_user_id: int,
    username: str,
    limit: int = 20,
) -> dict[str, Any]:
    """Get report history for a specific team member.

    Returns the member's management reports that are visible to the manager,
    newest first. Verifies the member belongs to the caller's team.
    """
    db = get_db()

    with db.session() as session:
        _, team = _resolve_manager_team(session, manager_user_id, None)
        team_id = team.id

        memberships = (
            session.query(TeamMembership)
            .filter(TeamMembership.team_id == team_id)
            .all()
        )
        member_ids = [m.user_id for m in memberships]
        if team.manager_id:
            member_ids.append(team.manager_id)

        members = session.query(User).filter(User.id.in_(member_ids)).all()
        member_emails = {m.email for m in members}

        if username not in member_emails:
            raise ValueError(
                f"User '{username}' is not a member of the managed team"
            )

        target_user = next((m for m in members if m.email == username), None)
        visibility_defaults = _get_user_visibility_defaults(target_user) if target_user else {}

        reports = (
            session.query(ManagementReport)
            .filter(ManagementReport.username == username)
            .order_by(ManagementReport.created_at.desc())
            .limit(limit)
            .all()
        )

        visible_reports = [
            r for r in reports if _is_report_visible_to_manager(r, visibility_defaults)
        ]

        report_list = [
            {
                "id": r.id,
                "title": r.title,
                "report_period": r.report_period,
                "content": r.content,
                "referenced_tickets": (
                    r.referenced_tickets.split(",") if r.referenced_tickets else []
                ),
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in visible_reports
        ]

        return {
            "username": username,
            "display_name": target_user.display_name if target_user else None,
            "team_id": team_id,
            "team_name": team.name,
            "total_visible": len(report_list),
            "reports": report_list,
        }


def list_snapshots(
    manager_user_id: int,
    report_period: str | None = None,
    team_id_override: int | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """List consolidated report snapshots for the manager's team.

    Returns metadata (without full content) sorted newest first.
    """
    db = get_db()

    with db.session() as session:
        _, team = _resolve_manager_team(session, manager_user_id, team_id_override)
        team_id = team.id

        query = session.query(ConsolidatedReportSnapshot).filter(
            ConsolidatedReportSnapshot.team_id == team_id
        )
        if report_period:
            query = query.filter(
                ConsolidatedReportSnapshot.report_period == report_period
            )

        snapshots = (
            query.order_by(ConsolidatedReportSnapshot.created_at.desc())
            .limit(limit)
            .all()
        )

        snapshot_list = [
            {
                "id": s.id,
                "team_id": s.team_id,
                "report_period": s.report_period,
                "snapshot_type": s.snapshot_type.value if s.snapshot_type else None,
                "label": s.label,
                "created_by_id": s.created_by_id,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in snapshots
        ]

        return {
            "team_id": team_id,
            "team_name": team.name,
            "total": len(snapshot_list),
            "snapshots": snapshot_list,
        }


def get_snapshot(
    manager_user_id: int,
    snapshot_id: int,
) -> dict[str, Any]:
    """Get the full content of a specific consolidated report snapshot.

    The caller must be the manager of the team the snapshot belongs to, or an admin.
    """
    db = get_db()

    with db.session() as session:
        user = session.query(User).filter(User.id == manager_user_id).first()
        if not user:
            raise ValueError("Manager user not found")

        snapshot = (
            session.query(ConsolidatedReportSnapshot)
            .filter(ConsolidatedReportSnapshot.id == snapshot_id)
            .first()
        )
        if not snapshot:
            raise ValueError(f"Snapshot {snapshot_id} not found")

        # Verify the caller has access to this snapshot's team
        if user.role != UserRole.ADMIN:
            team = session.query(Team).filter(Team.id == snapshot.team_id).first()
            if not team or team.manager_id != manager_user_id:
                raise ValueError("Access denied: snapshot belongs to a different team")

        return snapshot.to_dict()


def list_all_teams(manager_user_id: int) -> dict[str, Any]:
    """List teams available to the caller.

    Managers see only their own managed team. Admins see all teams in the system.
    Call this first inside any prompt to discover which team(s) are available
    before asking the user to choose.
    """
    db = get_db()

    with db.session() as session:
        user = session.query(User).filter(User.id == manager_user_id).first()
        if not user:
            raise ValueError("Manager user not found")

        if user.role == UserRole.ADMIN:
            teams = session.query(Team).order_by(Team.name).all()
        else:
            teams = session.query(Team).filter(Team.manager_id == manager_user_id).all()

        return {
            "role": user.role.value,
            "is_admin": user.role == UserRole.ADMIN,
            "teams": [
                {
                    "id": t.id,
                    "name": t.name,
                    "description": t.description,
                    "manager_id": t.manager_id,
                }
                for t in teams
            ],
            "total": len(teams),
        }


def list_team_members(
    manager_user_id: int,
    team_id_override: int | None = None,
) -> dict[str, Any]:
    """List team members with their role and latest report date.

    Returns the roster for the manager's team, sorted alphabetically by email.
    """
    db = get_db()

    with db.session() as session:
        _, team = _resolve_manager_team(session, manager_user_id, team_id_override)
        team_id = team.id

        memberships = (
            session.query(TeamMembership)
            .filter(TeamMembership.team_id == team_id)
            .all()
        )
        member_ids = [m.user_id for m in memberships]
        if team.manager_id:
            member_ids.append(team.manager_id)

        members = session.query(User).filter(User.id.in_(member_ids)).all()

        # Fetch latest report date per member (any report, not just visible)
        latest_report_by_email: dict[str, str | None] = {}
        for member in members:
            latest = (
                session.query(ManagementReport)
                .filter(ManagementReport.username == member.email)
                .order_by(ManagementReport.created_at.desc())
                .first()
            )
            latest_report_by_email[member.email] = (
                latest.created_at.isoformat() if latest and latest.created_at else None
            )

        member_list = sorted(
            [
                {
                    "id": m.id,
                    "email": m.email,
                    "display_name": m.display_name,
                    "role": m.role.value if m.role else None,
                    "is_manager": m.id == team.manager_id,
                    "latest_report_at": latest_report_by_email.get(m.email),
                }
                for m in members
            ],
            key=lambda m: m["email"],
        )

        return {
            "team_id": team_id,
            "team_name": team.name,
            "total_members": len(member_list),
            "members": member_list,
        }
