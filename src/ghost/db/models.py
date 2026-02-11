"""SQLAlchemy models for activity tracking, weekly reports, and user management."""

import enum
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Index, Integer, String, Text
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
    personal_access_tokens = relationship("PersonalAccessToken", back_populates="user", cascade="all, delete-orphan")

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

    # Visibility control - None=inherit from user preferences, True=shared, False=private
    visible_to_manager = Column(Boolean, nullable=True, default=None)

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
            "visible_to_manager": self.visible_to_manager,
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

    # Visibility control - None=inherit from user preferences, True=shared, False=private
    visible_to_manager = Column(Boolean, nullable=True, default=None)

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
            "visible_to_manager": self.visible_to_manager,
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

    # Visibility control - None=inherit from user preferences, True=shared, False=private
    visible_to_manager = Column(Boolean, nullable=True, default=None)

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
            "visible_to_manager": self.visible_to_manager,
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

    # Relationships - includes ALL projects (both top-level and nested)
    projects = relationship(
        "ReportProject",
        back_populates="field",
        cascade="all, delete-orphan",
        order_by="ReportProject.display_order",
    )

    __table_args__ = (Index("idx_field_order", "display_order"),)

    @property
    def top_level_projects(self) -> list["ReportProject"]:
        """Get only top-level projects (parent_id is None)."""
        return [p for p in self.projects if p.parent_id is None]

    def to_dict(self, include_projects: bool = False, include_children: bool = False) -> dict:
        """Convert to dictionary.
        
        Args:
            include_projects: Include project data in output
            include_children: If True, include nested children hierarchy; 
                            if False, include flat list of all projects
        """
        result = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "display_order": self.display_order,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_projects:
            if include_children:
                # Return hierarchical structure with only top-level projects
                # (children are nested within each project)
                result["projects"] = [
                    p.to_dict(include_config=True, include_children=True)
                    for p in sorted(self.top_level_projects, key=lambda x: x.display_order)
                ]
            else:
                # Flat list of all projects (backward compatible)
                result["projects"] = [
                    p.to_dict(include_config=True) for p in self.projects
                ]
        return result

    def __repr__(self) -> str:
        return f"<ReportField(id={self.id}, name={self.name})>"


class ReportProject(Base):
    """Project within a field for report consolidation.
    
    Supports hierarchical nesting via parent_id for N-level deep structures.
    Detection mappings (git repos, Jira components) should only be on leaf projects.
    """

    __tablename__ = "report_projects"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Parent field
    field_id = Column(Integer, ForeignKey("report_fields.id"), nullable=False, index=True)

    # Self-referential parent (null = top-level project under field)
    parent_id = Column(Integer, ForeignKey("report_projects.id"), nullable=True, index=True)

    # Project info
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Ordering within parent (or field if top-level)
    display_order = Column(Integer, nullable=False, default=0)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True, onupdate=datetime.utcnow)

    # Relationships
    field = relationship("ReportField", back_populates="projects")
    
    # Self-referential relationships for hierarchy
    parent = relationship(
        "ReportProject",
        remote_side=[id],
        back_populates="children",
    )
    children = relationship(
        "ReportProject",
        back_populates="parent",
        cascade="all, delete-orphan",
        order_by="ReportProject.display_order",
    )
    
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
        Index("idx_project_parent", "parent_id"),
        # Unique name within same parent (or field if top-level)
        Index("idx_project_name", "field_id", "parent_id", "name", unique=True),
    )

    @property
    def is_leaf(self) -> bool:
        """Check if this project has no children (is a leaf node)."""
        return len(self.children) == 0

    def get_ancestry_path(self) -> list["ReportProject"]:
        """Get the full ancestry path from root to this project (inclusive)."""
        path = [self]
        current = self
        while current.parent is not None:
            path.insert(0, current.parent)
            current = current.parent
        return path

    def get_full_name(self, separator: str = " > ") -> str:
        """Get the full hierarchical name (e.g., 'AI/ML > ExploitIQ > CVE Analysis')."""
        return separator.join(p.name for p in self.get_ancestry_path())

    def to_dict(self, include_config: bool = False, include_children: bool = False) -> dict:
        """Convert to dictionary."""
        result = {
            "id": self.id,
            "field_id": self.field_id,
            "parent_id": self.parent_id,
            "name": self.name,
            "description": self.description,
            "display_order": self.display_order,
            "is_leaf": self.is_leaf,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_config:
            result["git_repos"] = [r.repo_pattern for r in self.git_repos]
            result["jira_components"] = [
                {"jira_project_key": c.jira_project_key, "component_name": c.component_name}
                for c in self.jira_components
            ]
        if include_children:
            result["children"] = [
                c.to_dict(include_config=include_config, include_children=True)
                for c in sorted(self.children, key=lambda x: x.display_order)
            ]
        return result

    def __repr__(self) -> str:
        return f"<ReportProject(id={self.id}, name={self.name}, field_id={self.field_id}, parent_id={self.parent_id})>"


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


# =============================================================================
# Consolidated Report Draft Model (Manager Edits)
# =============================================================================


class PersonalAccessToken(Base):
    """Personal Access Token for MCP authentication.
    
    Users create PATs via the web UI. The raw token is shown once at creation
    and only the SHA-256 hash is stored. Tokens are validated at MCP connection
    time by hashing the presented token and looking up the hash.
    """

    __tablename__ = "personal_access_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Owner
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Token metadata
    name = Column(String(255), nullable=False)  # User-friendly label, e.g. "VS Code MCP"
    token_prefix = Column(String(12), nullable=False)  # First chars for identification (e.g. "gmcp_Ab3x...")
    token_hash = Column(String(64), unique=True, nullable=False, index=True)  # SHA-256 hex digest

    # Lifecycle
    expires_at = Column(DateTime, nullable=True)  # Optional expiry
    last_used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    is_revoked = Column(Boolean, nullable=False, default=False)

    # Relationships
    user = relationship("User", back_populates="personal_access_tokens")

    __table_args__ = (
        Index("idx_pat_user", "user_id", "created_at"),
    )

    def to_dict(self) -> dict:
        """Convert to dictionary (never includes token_hash)."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "token_prefix": self.token_prefix,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "is_revoked": self.is_revoked,
        }

    def __repr__(self) -> str:
        return f"<PersonalAccessToken(id={self.id}, user_id={self.user_id}, name={self.name})>"


class ConsolidatedReportDraft(Base):
    """Manager's draft of a consolidated team report with editable entries.
    
    Stores manager's modifications to consolidated reports separately from
    original team member reports. Entries are stored as JSON with structure
    matching the consolidated view (fields -> projects -> entries).
    """

    __tablename__ = "consolidated_report_drafts"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Team this draft is for
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False, index=True)

    # Manager who created/owns this draft
    manager_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Draft metadata
    title = Column(String(500), nullable=False)
    report_period = Column(String(100), nullable=True)  # e.g., "Week 4, January 2026"

    # Content stored as JSON with structure:
    # {
    #   "format": "consolidated_v1",
    #   "fields": [
    #     {
    #       "id": 1, "name": "Field Name",
    #       "projects": [
    #         {
    #           "id": 10, "name": "Project Name",
    #           "entries": [
    #             {
    #               "text": "Entry content...",
    #               "original_report_id": 123,
    #               "original_username": "user@example.com",
    #               "is_manager_added": false
    #             }
    #           ]
    #         }
    #       ]
    #     }
    #   ],
    #   "uncategorized": [...]
    # }
    content = Column(Text, nullable=False)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True, onupdate=datetime.utcnow)

    # Relationships
    team = relationship("Team")
    manager = relationship("User")

    __table_args__ = (
        Index("idx_consolidated_draft_team", "team_id", "created_at"),
        Index("idx_consolidated_draft_manager", "manager_id", "created_at"),
    )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        import json

        return {
            "id": self.id,
            "team_id": self.team_id,
            "manager_id": self.manager_id,
            "title": self.title,
            "report_period": self.report_period,
            "content": json.loads(self.content) if self.content else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<ConsolidatedReportDraft(id={self.id}, team_id={self.team_id}, title={self.title})>"


# =============================================================================
# Consolidated Report Snapshot Model (History)
# =============================================================================


class SnapshotType(str, enum.Enum):
    """Types of consolidated report snapshots."""

    AUTO = "auto"      # Auto-saved when first viewed
    MANUAL = "manual"  # Manually saved by manager


class ConsolidatedReportSnapshot(Base):
    """Snapshot of a consolidated team report for history tracking.
    
    Auto-saves when a manager first views a consolidated report for a period,
    and manual saves when manager explicitly saves with a label.
    Content is stored as JSON with the full consolidated report structure.
    """

    __tablename__ = "consolidated_report_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Team this snapshot is for
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False, index=True)

    # User who triggered the snapshot (manager or admin)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Report period this snapshot covers (e.g., "Week 4, Jan 2026")
    report_period = Column(String(100), nullable=False)

    # Snapshot type: auto (first view) or manual (explicit save)
    snapshot_type = Column(Enum(SnapshotType), nullable=False, default=SnapshotType.AUTO)

    # Optional label for manual saves (e.g., "Final Version", "Before Edits")
    label = Column(String(255), nullable=True)

    # Content stored as JSON with full consolidated report structure:
    # {
    #   "team_id": 1,
    #   "team_name": "Team Name",
    #   "report_period": "...",
    #   "fields": [...],
    #   "uncategorized": [...],
    #   "total_entries": 10
    # }
    content = Column(Text, nullable=False)

    # Timestamp
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    team = relationship("Team")
    created_by = relationship("User")

    __table_args__ = (
        Index("idx_snapshot_team_period", "team_id", "report_period", "created_at"),
        Index("idx_snapshot_created_by", "created_by_id", "created_at"),
    )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        import json

        return {
            "id": self.id,
            "team_id": self.team_id,
            "created_by_id": self.created_by_id,
            "report_period": self.report_period,
            "snapshot_type": self.snapshot_type.value if self.snapshot_type else None,
            "label": self.label,
            "content": json.loads(self.content) if self.content else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<ConsolidatedReportSnapshot(id={self.id}, team_id={self.team_id}, period={self.report_period}, type={self.snapshot_type})>"
