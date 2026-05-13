"""Activity API endpoints — ticket activity derived from existing report entry data."""

import json
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ghost.api.deps import require_manager_or_admin
from ghost.db import (
    ManagementReport,
    Team,
    TeamMembership,
    User,
    UserRole,
    get_db,
)

ManagerOrAdmin = Annotated[User, Depends(require_manager_or_admin)]

router = APIRouter()


# =============================================================================
# Helpers
# =============================================================================


def _parse_entries(content: str) -> list[dict]:
    """Return structured entries from a report content blob."""
    try:
        data = json.loads(content or "{}")
        if data.get("format") == "structured":
            return data.get("entries", [])
    except Exception:
        pass
    return []


def _get_member_ids_for_team(session, team: Team) -> list[int]:
    memberships = session.query(TeamMembership).filter(TeamMembership.team_id == team.id).all()
    ids = [m.user_id for m in memberships]
    if team.manager_id:
        ids.append(team.manager_id)
    return list(set(ids))


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/tickets")
def get_ticket_activity(
    user: ManagerOrAdmin,
    team_id: int | None = Query(default=None),
    period_days: int = Query(default=30, ge=7, le=365),
):
    """Return unique ticket counts per team member derived from report entry ticket_key fields.

    Reads existing management_reports data — no external calls needed.
    Access restricted to managers and admins.
    """
    db = get_db()
    with db.session() as session:
        if team_id is not None:
            if user.role != UserRole.ADMIN:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only admins can specify team_id",
                )
            team = session.query(Team).filter(Team.id == team_id).first()
            if not team:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
            teams = [team]
        else:
            managed_teams = session.query(Team).filter(Team.manager_id == user.id).all()
            if not managed_teams and user.role == UserRole.ADMIN:
                managed_teams = session.query(Team).all()
            if not managed_teams:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No managed team found")
            teams = managed_teams

        member_ids: set[int] = set()
        for t in teams:
            member_ids.update(_get_member_ids_for_team(session, t))
        members = session.query(User).filter(User.id.in_(member_ids)).all()

        since = datetime.utcnow() - timedelta(days=period_days)

        member_stats = []
        all_tickets: set[str] = set()

        for member in members:
            reports = (
                session.query(ManagementReport)
                .filter(
                    ManagementReport.username == member.email,
                    ManagementReport.created_at >= since,
                )
                .all()
            )

            # Collect unique ticket_key values for this member (deduplicated)
            member_tickets: set[str] = set()
            for report in reports:
                for entry in _parse_entries(report.content):
                    key = entry.get("ticket_key")
                    if key and isinstance(key, str) and key.strip():
                        member_tickets.add(key.strip())

            all_tickets.update(member_tickets)

            member_stats.append({
                "user_id": member.id,
                "email": member.email,
                "display_name": member.display_name,
                "unique_tickets": len(member_tickets),
                "tickets": sorted(member_tickets),
            })

        session.expunge_all()

    member_stats.sort(key=lambda m: m["unique_tickets"], reverse=True)

    return {
        "team_unique_tickets": len(all_tickets),
        "period_days": period_days,
        "members": member_stats,
    }
