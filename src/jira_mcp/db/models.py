"""SQLAlchemy models for activity tracking, weekly reports, and user management."""

import enum
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Base class for all models."""

    pass


# =============================================================================
# Enums
# =============================================================================


class UserRole(str, enum.Enum):
    """User roles for access control."""

    USER = "user"
    MANAGER = "manager"
    ADMIN = "admin"


class ActionType(str, enum.Enum):
    """Types of actions that can be logged."""

    VIEW = "view"
    CREATE = "create"
    UPDATE = "update"
    COMMENT = "comment"
    TRANSITION = "transition"
    LINK = "link"
    OTHER = "other"


class TicketSource(str, enum.Enum):
    """Source of the ticket (Jira or GitHub Issues)."""

    JIRA = "jira"
    GITHUB = "github"


# =============================================================================
# User & Team Models
# =============================================================================


class User(Base):
    """User model - authentication handled by OpenShift OAuth Proxy."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Identity (from OAuth proxy headers)
    email = Column(String(255), unique=True, nullable=False, index=True)
    display_name = Column(String(255), nullable=True)

    # Authorization
    role = Column(Enum(UserRole), nullable=False, default=UserRole.USER)

    # User preferences (JSON string)
    preferences = Column(Text, nullable=True)

    # Timestamps
    first_seen = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_seen = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    managed_teams = relationship("Team", back_populates="manager", foreign_keys="Team.manager_id")
    team_memberships = relationship("TeamMembership", back_populates="user", cascade="all, delete-orphan")

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        import json

        return {
            "id": self.id,
            "email": self.email,
            "display_name": self.display_name,
            "role": self.role.value if self.role else None,
            "preferences": json.loads(self.preferences) if self.preferences else {},
            "first_seen": self.first_seen.isoformat() if self.first_seen else None,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
        }

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, role={self.role})>"


class Team(Base):
    """Team model for organizing users."""

    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Team info
    name = Column(String(255), nullable=False, unique=True)
    description = Column(Text, nullable=True)

    # Manager (FK to User)
    manager_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True, onupdate=datetime.utcnow)

    # Relationships
    manager = relationship("User", back_populates="managed_teams", foreign_keys=[manager_id])
    memberships = relationship("TeamMembership", back_populates="team", cascade="all, delete-orphan")

    def to_dict(self, include_members: bool = False) -> dict:
        """Convert to dictionary."""
        result = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "manager_id": self.manager_id,
            "manager": self.manager.to_dict() if self.manager else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_members:
            result["members"] = [m.user.to_dict() for m in self.memberships if m.user]
        return result

    def __repr__(self) -> str:
        return f"<Team(id={self.id}, name={self.name})>"


class TeamMembership(Base):
    """Association table for User-Team many-to-many relationship."""

    __tablename__ = "team_memberships"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Foreign keys
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False, index=True)

    # Timestamps
    joined_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="team_memberships")
    team = relationship("Team", back_populates="memberships")

    # Unique constraint - user can only be in a team once
    __table_args__ = (
        Index("idx_user_team", "user_id", "team_id", unique=True),
    )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "team_id": self.team_id,
            "joined_at": self.joined_at.isoformat() if self.joined_at else None,
            "user": self.user.to_dict() if self.user else None,
            "team": {"id": self.team.id, "name": self.team.name} if self.team else None,
        }

    def __repr__(self) -> str:
        return f"<TeamMembership(user_id={self.user_id}, team_id={self.team_id})>"


# =============================================================================
# Activity & Report Models
# =============================================================================


class ActivityLog(Base):
    """Log of Jira/GitHub ticket interactions for activity tracking."""

    __tablename__ = "activity_log"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # User info - username for backwards compatibility, user_id for new entries
    username = Column(String(255), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    # Ticket info
    ticket_key = Column(String(100), nullable=False, index=True)  # PROJ-123 or owner/repo#123
    ticket_summary = Column(String(500), nullable=True)
    project_key = Column(String(50), nullable=True, index=True)  # For Jira: project key

    # Ticket source (Jira or GitHub)
    ticket_source = Column(
        Enum(TicketSource), nullable=False, default=TicketSource.JIRA, index=True
    )
    github_repo = Column(String(255), nullable=True, index=True)  # For GitHub: owner/repo

    # Jira components (comma-separated for auto-detection)
    jira_components = Column(String(500), nullable=True)  # e.g., "component1,component2"

    # Auto-detected project for report consolidation
    detected_project_id = Column(
        Integer, ForeignKey("report_projects.id"), nullable=True, index=True
    )

    # Action info
    action_type = Column(Enum(ActionType), nullable=False, default=ActionType.OTHER)
    action_details = Column(Text, nullable=True)  # JSON string with additional context

    # Timestamps
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    # Relationships
    detected_project = relationship("ReportProject", back_populates="activities")

    # Indexes for weekly report queries
    __table_args__ = (
        Index("idx_user_timestamp", "username", "timestamp"),
        Index("idx_user_project_timestamp", "username", "project_key", "timestamp"),
        Index("idx_user_source_timestamp", "username", "ticket_source", "timestamp"),
        Index("idx_detected_project", "detected_project_id", "timestamp"),
    )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "username": self.username,
            "ticket_key": self.ticket_key,
            "ticket_summary": self.ticket_summary,
            "project_key": self.project_key,
            "ticket_source": self.ticket_source.value if self.ticket_source else "jira",
            "github_repo": self.github_repo,
            "jira_components": self.jira_components.split(",") if self.jira_components else [],
            "detected_project_id": self.detected_project_id,
            "action_type": self.action_type.value if self.action_type else None,
            "action_details": self.action_details,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


class WeeklyReport(Base):
    """Stored weekly reports for users."""

    __tablename__ = "weekly_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # User info
    username = Column(String(255), nullable=False, index=True)

    # Report period
    week_start = Column(DateTime, nullable=False, index=True)
    week_end = Column(DateTime, nullable=False)

    # Report content
    title = Column(String(500), nullable=False)
    summary = Column(Text, nullable=False)  # Executive summary
    content = Column(Text, nullable=False)  # Full report content (Markdown)

    # Metadata
    tickets_count = Column(Integer, nullable=False, default=0)
    projects = Column(String(500), nullable=True)  # Comma-separated project keys

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True, onupdate=datetime.utcnow)

    __table_args__ = (Index("idx_user_week", "username", "week_start"),)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "username": self.username,
            "week_start": self.week_start.isoformat() if self.week_start else None,
            "week_end": self.week_end.isoformat() if self.week_end else None,
            "title": self.title,
            "summary": self.summary,
            "content": self.content,
            "tickets_count": self.tickets_count,
            "projects": self.projects.split(",") if self.projects else [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ManagementReport(Base):
    """Management-level project progress reports (AI-generated content)."""

    __tablename__ = "management_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Author info
    username = Column(String(255), nullable=False, index=True)

    # Report metadata
    title = Column(String(500), nullable=False)
    project_key = Column(String(50), nullable=True, index=True)  # Optional project focus
    report_period = Column(
        String(100), nullable=True
    )  # e.g., "Week 3, January 2026" or "Sprint 42"

    # Report content - simple bullet list of work items with embedded links
    content = Column(Text, nullable=False)

    # Referenced tickets (comma-separated keys for indexing)
    referenced_tickets = Column(Text, nullable=True)  # e.g., "APPENG-4112,APPENG-4256"

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, nullable=True, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_mgmt_user_created", "username", "created_at"),
        Index("idx_mgmt_project", "project_key", "created_at"),
    )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "username": self.username,
            "title": self.title,
            "project_key": self.project_key,
            "report_period": self.report_period,
            "content": self.content,
            "referenced_tickets": (
                self.referenced_tickets.split(",") if self.referenced_tickets else []
            ),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# =============================================================================
# Report Field & Project Configuration Models
# =============================================================================


class ReportField(Base):
    """Top-level field for grouping projects in report consolidation."""

    __tablename__ = "report_fields"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Field info
    name = Column(String(255), nullable=False, unique=True)
    description = Column(Text, nullable=True)

    # Ordering
    display_order = Column(Integer, nullable=False, default=0)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True, onupdate=datetime.utcnow)

    # Relationships
    projects = relationship(
        "ReportProject",
        back_populates="field",
        cascade="all, delete-orphan",
        order_by="ReportProject.display_order",
    )

    __table_args__ = (Index("idx_field_order", "display_order"),)

    def to_dict(self, include_projects: bool = False) -> dict:
        """Convert to dictionary."""
        result = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "display_order": self.display_order,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_projects:
            result["projects"] = [p.to_dict(include_config=True) for p in self.projects]
        return result

    def __repr__(self) -> str:
        return f"<ReportField(id={self.id}, name={self.name})>"


class ReportProject(Base):
    """Project within a field for report consolidation."""

    __tablename__ = "report_projects"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Parent field
    field_id = Column(Integer, ForeignKey("report_fields.id"), nullable=False, index=True)

    # Project info
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Ordering within field
    display_order = Column(Integer, nullable=False, default=0)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True, onupdate=datetime.utcnow)

    # Relationships
    field = relationship("ReportField", back_populates="projects")
    git_repos = relationship(
        "ProjectGitRepo",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    jira_components = relationship(
        "ProjectJiraComponent",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    activities = relationship("ActivityLog", back_populates="detected_project")

    __table_args__ = (
        Index("idx_project_field_order", "field_id", "display_order"),
        Index("idx_project_name", "field_id", "name", unique=True),
    )

    def to_dict(self, include_config: bool = False) -> dict:
        """Convert to dictionary."""
        result = {
            "id": self.id,
            "field_id": self.field_id,
            "name": self.name,
            "description": self.description,
            "display_order": self.display_order,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_config:
            result["git_repos"] = [r.repo_pattern for r in self.git_repos]
            result["jira_components"] = [
                {"jira_project_key": c.jira_project_key, "component_name": c.component_name}
                for c in self.jira_components
            ]
        return result

    def __repr__(self) -> str:
        return f"<ReportProject(id={self.id}, name={self.name}, field_id={self.field_id})>"


class ProjectGitRepo(Base):
    """Git repository pattern mapped to a project for auto-detection."""

    __tablename__ = "project_git_repos"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Parent project
    project_id = Column(Integer, ForeignKey("report_projects.id"), nullable=False, index=True)

    # Repo pattern (e.g., "org/repo" or "org/*" for wildcards)
    repo_pattern = Column(String(255), nullable=False)

    # Relationships
    project = relationship("ReportProject", back_populates="git_repos")

    __table_args__ = (
        Index("idx_git_repo_pattern", "repo_pattern"),
        Index("idx_git_repo_project", "project_id", "repo_pattern", unique=True),
    )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "project_id": self.project_id,
            "repo_pattern": self.repo_pattern,
        }

    def __repr__(self) -> str:
        return f"<ProjectGitRepo(id={self.id}, pattern={self.repo_pattern})>"


class ProjectJiraComponent(Base):
    """Jira component mapped to a project for auto-detection."""

    __tablename__ = "project_jira_components"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Parent project
    project_id = Column(Integer, ForeignKey("report_projects.id"), nullable=False, index=True)

    # Jira project and component
    jira_project_key = Column(String(50), nullable=False)  # e.g., "APPENG"
    component_name = Column(String(255), nullable=False)  # e.g., "API"

    # Relationships
    project = relationship("ReportProject", back_populates="jira_components")

    __table_args__ = (
        Index("idx_jira_component_lookup", "jira_project_key", "component_name"),
        Index(
            "idx_jira_component_project",
            "project_id",
            "jira_project_key",
            "component_name",
            unique=True,
        ),
    )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "project_id": self.project_id,
            "jira_project_key": self.jira_project_key,
            "component_name": self.component_name,
        }

    def __repr__(self) -> str:
        return f"<ProjectJiraComponent(id={self.id}, project={self.jira_project_key}, component={self.component_name})>"
