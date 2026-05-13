"""Goals API endpoints — team and individual goal tracking."""

import json
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import or_

from ghost.api.deps import CurrentUser
from ghost.db import (
    Goal,
    GoalEntryLink,
    GoalHorizon,
    GoalNote,
    GoalScope,
    GoalStatus,
    ManagementReport,
    Team,
    TeamMembership,
    User,
    UserRole,
    get_db,
)

router = APIRouter()


# =============================================================================
# Pydantic Models
# =============================================================================


class GoalCreateRequest(BaseModel):
    title: str
    description: str | None = None
    scope: str  # 'team' or 'individual'
    team_id: int
    horizon: str = "sprint"  # 'sprint', 'quarter', 'ongoing'
    due_date: str | None = None  # ISO date string; auto-calculated if omitted


class GoalUpdateRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None  # 'active', 'completed', 'dropped'
    horizon: str | None = None
    due_date: str | None = None  # ISO date string or empty string to clear


class GoalNoteCreateRequest(BaseModel):
    body: str


class GoalLinkRequest(BaseModel):
    report_id: int
    entry_index: int


# =============================================================================
# Helpers
# =============================================================================


def _enrich_goal(session, goal: Goal) -> dict:
    """Return goal.to_dict() plus live entry_link_count and owner identity."""
    d = goal.to_dict()
    d["entry_link_count"] = (
        session.query(GoalEntryLink).filter(GoalEntryLink.goal_id == goal.id).count()
    )
    if goal.owner_id:
        owner = session.query(User).filter(User.id == goal.owner_id).first()
        d["owner_email"] = owner.email if owner else None
        d["owner_display_name"] = owner.display_name if owner else None
    else:
        d["owner_email"] = None
        d["owner_display_name"] = None
    return d


def _get_user_team_ids(session, user: User) -> set[int]:
    memberships = session.query(TeamMembership).filter(TeamMembership.user_id == user.id).all()
    managed = session.query(Team).filter(Team.manager_id == user.id).all()
    return {m.team_id for m in memberships} | {t.id for t in managed}


def _assert_team_access(session, team_id: int, user: User) -> Team:
    """Return the Team or raise 404 / 403."""
    team = session.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    if user.role == UserRole.ADMIN:
        return team
    is_manager = team.manager_id == user.id
    membership = session.query(TeamMembership).filter(
        TeamMembership.user_id == user.id,
        TeamMembership.team_id == team_id,
    ).first()
    if not is_manager and not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not a member of this team")
    return team


def _assert_goal_write_access(session, goal: Goal, user: User) -> None:
    """Raise 403 if the caller cannot modify this goal."""
    if user.role == UserRole.ADMIN:
        return
    team = session.query(Team).filter(Team.id == goal.team_id).first()
    is_team_manager = team and team.manager_id == user.id
    is_owner = goal.owner_id == user.id
    if not is_team_manager and not is_owner:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")


def _default_due_date(horizon: GoalHorizon) -> datetime | None:
    """Calculate a sensible default due date from a horizon."""
    now = datetime.utcnow()
    if horizon == GoalHorizon.SPRINT:
        return now + timedelta(days=14)
    if horizon == GoalHorizon.QUARTER:
        # End of the current calendar quarter
        month = now.month
        if month <= 3:
            return datetime(now.year, 3, 31)
        if month <= 6:
            return datetime(now.year, 6, 30)
        if month <= 9:
            return datetime(now.year, 9, 30)
        return datetime(now.year, 12, 31)
    return None  # Ongoing — no due date


def _extract_entry_text(report: ManagementReport, entry_index: int) -> tuple[str | None, str | None]:
    """Return (entry_text, ticket_key) for a given entry index, or (None, None)."""
    try:
        content = json.loads(report.content or "{}")
        if content.get("format") == "structured":
            entries = content.get("entries", [])
            if 0 <= entry_index < len(entries):
                e = entries[entry_index]
                return e.get("text"), e.get("ticket_key")
    except Exception:
        pass
    return None, None


# =============================================================================
# Endpoints
# =============================================================================


@router.get("")
def list_goals(user: CurrentUser):
    """List goals visible to the caller: team goals for their teams + own individual goals.

    Admins see everything.  Managers see all goals in their teams (team + individual).
    Regular users see team goals + only their own individual goals.
    """
    db = get_db()
    with db.session() as session:
        if user.role == UserRole.ADMIN:
            goals = session.query(Goal).order_by(Goal.created_at.desc()).all()
        else:
            team_ids = _get_user_team_ids(session, user)
            if not team_ids:
                return {"goals": [], "total": 0}

            is_manager = user.role == UserRole.MANAGER
            if is_manager:
                goals = (
                    session.query(Goal)
                    .filter(Goal.team_id.in_(team_ids))
                    .order_by(Goal.created_at.desc())
                    .all()
                )
            else:
                goals = (
                    session.query(Goal)
                    .filter(
                        Goal.team_id.in_(team_ids),
                        or_(
                            Goal.scope == GoalScope.TEAM,
                            Goal.owner_id == user.id,
                        ),
                    )
                    .order_by(Goal.created_at.desc())
                    .all()
                )

        result = [_enrich_goal(session, g) for g in goals]
        session.expunge_all()
        return {"goals": result, "total": len(result)}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_goal(body: GoalCreateRequest, user: CurrentUser):
    """Create a new goal. Team goals require manager or admin role."""
    try:
        scope = GoalScope(body.scope)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid scope '{body.scope}'. Use 'team' or 'individual'.")
    try:
        horizon = GoalHorizon(body.horizon)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid horizon '{body.horizon}'. Use 'sprint', 'quarter', or 'ongoing'.")

    if scope == GoalScope.TEAM and user.role == UserRole.USER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only managers can create team goals.")

    db = get_db()
    with db.session() as session:
        _assert_team_access(session, body.team_id, user)

        # Parse or auto-calculate due date
        if body.due_date:
            try:
                due = datetime.fromisoformat(body.due_date.replace("Z", "+00:00")).replace(tzinfo=None)
            except ValueError:
                raise HTTPException(status_code=422, detail="Invalid due_date format. Use ISO 8601.")
        else:
            due = _default_due_date(horizon)

        goal = Goal(
            title=body.title,
            description=body.description,
            scope=scope,
            team_id=body.team_id,
            owner_id=user.id if scope == GoalScope.INDIVIDUAL else None,
            horizon=horizon,
            status=GoalStatus.ACTIVE,
            due_date=due,
        )
        session.add(goal)
        session.flush()
        result = _enrich_goal(session, goal)
        session.expunge_all()
        return result


@router.patch("/{goal_id}")
def update_goal(goal_id: int, body: GoalUpdateRequest, user: CurrentUser):
    """Update a goal's title, description, status, or horizon."""
    db = get_db()
    with db.session() as session:
        goal = session.query(Goal).filter(Goal.id == goal_id).first()
        if not goal:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found")
        _assert_goal_write_access(session, goal, user)

        if body.title is not None:
            goal.title = body.title
        if body.description is not None:
            goal.description = body.description
        if body.status is not None:
            try:
                goal.status = GoalStatus(body.status)
            except ValueError:
                raise HTTPException(status_code=422, detail=f"Invalid status '{body.status}'.")
        if body.horizon is not None:
            try:
                goal.horizon = GoalHorizon(body.horizon)
            except ValueError:
                raise HTTPException(status_code=422, detail=f"Invalid horizon '{body.horizon}'.")
        if body.due_date is not None:
            if body.due_date == "":
                goal.due_date = None
            else:
                try:
                    goal.due_date = datetime.fromisoformat(body.due_date.replace("Z", "+00:00")).replace(tzinfo=None)
                except ValueError:
                    raise HTTPException(status_code=422, detail="Invalid due_date format. Use ISO 8601.")

        session.flush()
        result = _enrich_goal(session, goal)
        session.expunge_all()
        return result


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_goal(goal_id: int, user: CurrentUser):
    """Delete a goal and all its entry links."""
    db = get_db()
    with db.session() as session:
        goal = session.query(Goal).filter(Goal.id == goal_id).first()
        if not goal:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found")
        _assert_goal_write_access(session, goal, user)
        session.delete(goal)


@router.get("/{goal_id}/links")
def list_goal_links(goal_id: int, user: CurrentUser):
    """List all entry links for a goal, enriched with entry text and author."""
    db = get_db()
    with db.session() as session:
        goal = session.query(Goal).filter(Goal.id == goal_id).first()
        if not goal:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found")

        links = (
            session.query(GoalEntryLink)
            .filter(GoalEntryLink.goal_id == goal_id)
            .order_by(GoalEntryLink.created_at.desc())
            .all()
        )

        result = []
        for link in links:
            d = link.to_dict()
            report = session.query(ManagementReport).filter(
                ManagementReport.id == link.report_id
            ).first()
            if report:
                d["username"] = report.username
                d["report_title"] = report.title
                d["report_period"] = report.report_period
                text, ticket_key = _extract_entry_text(report, link.entry_index)
                d["entry_text"] = text
                d["entry_ticket_key"] = ticket_key
            else:
                d["username"] = None
                d["report_title"] = None
                d["report_period"] = None
                d["entry_text"] = None
                d["entry_ticket_key"] = None
            result.append(d)

        session.expunge_all()
        return {"links": result, "total": len(result)}


@router.post("/{goal_id}/links", status_code=status.HTTP_201_CREATED)
def create_goal_link(goal_id: int, body: GoalLinkRequest, user: CurrentUser):
    """Link a specific report entry to a goal."""
    db = get_db()
    with db.session() as session:
        goal = session.query(Goal).filter(Goal.id == goal_id).first()
        if not goal:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found")

        report = session.query(ManagementReport).filter(
            ManagementReport.id == body.report_id
        ).first()
        if not report:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

        # Regular users can only link their own reports
        if user.role == UserRole.USER and report.username != user.email:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only link entries from your own reports.",
            )

        # Idempotent — return existing link silently
        existing = session.query(GoalEntryLink).filter(
            GoalEntryLink.goal_id == goal_id,
            GoalEntryLink.report_id == body.report_id,
            GoalEntryLink.entry_index == body.entry_index,
        ).first()
        if existing:
            result = existing.to_dict()
            session.expunge_all()
            return result

        link = GoalEntryLink(
            goal_id=goal_id,
            report_id=body.report_id,
            entry_index=body.entry_index,
        )
        session.add(link)
        session.flush()
        result = link.to_dict()
        session.expunge_all()
        return result


@router.delete("/{goal_id}/links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_goal_link(goal_id: int, link_id: int, user: CurrentUser):
    """Remove an entry link from a goal."""
    db = get_db()
    with db.session() as session:
        link = session.query(GoalEntryLink).filter(
            GoalEntryLink.id == link_id,
            GoalEntryLink.goal_id == goal_id,
        ).first()
        if not link:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")

        if user.role != UserRole.ADMIN:
            report = session.query(ManagementReport).filter(
                ManagementReport.id == link.report_id
            ).first()
            is_own = report and report.username == user.email
            goal = session.query(Goal).filter(Goal.id == goal_id).first()
            team = session.query(Team).filter(Team.id == goal.team_id).first() if goal else None
            is_manager = team and team.manager_id == user.id
            if not is_own and not is_manager:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

        session.delete(link)


# =============================================================================
# Goal Notes (Jira-comment-style timeline)
# =============================================================================


@router.get("/{goal_id}/notes")
def list_goal_notes(goal_id: int, user: CurrentUser):
    """Return all notes for a goal, enriched with author display name."""
    db = get_db()
    with db.session() as session:
        goal = session.query(Goal).filter(Goal.id == goal_id).first()
        if not goal:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found")

        notes = (
            session.query(GoalNote)
            .filter(GoalNote.goal_id == goal_id)
            .order_by(GoalNote.created_at.asc())
            .all()
        )

        result = []
        for note in notes:
            d = note.to_dict()
            author = session.query(User).filter(User.id == note.author_id).first()
            d["author_email"] = author.email if author else None
            d["author_display_name"] = author.display_name if author else None
            result.append(d)

        session.expunge_all()
        return {"notes": result, "total": len(result)}


@router.post("/{goal_id}/notes", status_code=status.HTTP_201_CREATED)
def create_goal_note(goal_id: int, body: GoalNoteCreateRequest, user: CurrentUser):
    """Add a note to a goal."""
    if not body.body.strip():
        raise HTTPException(status_code=422, detail="Note body cannot be empty.")

    db = get_db()
    with db.session() as session:
        goal = session.query(Goal).filter(Goal.id == goal_id).first()
        if not goal:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found")

        note = GoalNote(goal_id=goal_id, author_id=user.id, body=body.body.strip())
        session.add(note)
        session.flush()

        d = note.to_dict()
        d["author_email"] = user.email
        d["author_display_name"] = user.display_name
        session.expunge_all()
        return d


@router.delete("/{goal_id}/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_goal_note(goal_id: int, note_id: int, user: CurrentUser):
    """Delete a note. Only the author or an admin/manager can delete."""
    db = get_db()
    with db.session() as session:
        note = session.query(GoalNote).filter(
            GoalNote.id == note_id,
            GoalNote.goal_id == goal_id,
        ).first()
        if not note:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

        is_author = note.author_id == user.id
        if not is_author and user.role == UserRole.USER:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the author can delete this note.")

        session.delete(note)
