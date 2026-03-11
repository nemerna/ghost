"""Database layer for Jira MCP activity tracking, reports, and user management."""

from ghost.db.database import Database, get_db, init_db
from ghost.db.models import (
    ActionType,
    ActivityLog,
    ConsolidatedReportDraft,
    ConsolidatedReportSnapshot,
    GitHubTokenConfig,
    ManagementReport,
    PersonalAccessToken,
    ProjectGitRepo,
    ProjectJiraComponent,
    ReportField,
    ReportProject,
    SnapshotType,
    Team,
    TeamMembership,
    TicketSource,
    User,
    UserRole,
)

__all__ = [
    # Database
    "get_db",
    "init_db",
    "Database",
    # Enums
    "ActionType",
    "TicketSource",
    "UserRole",
    "SnapshotType",
    # User & Team Models
    "User",
    "Team",
    "TeamMembership",
    "PersonalAccessToken",
    "GitHubTokenConfig",
    # Activity & Report Models
    "ActivityLog",
    "ManagementReport",
    "ConsolidatedReportDraft",
    "ConsolidatedReportSnapshot",
    # Report Field & Project Configuration Models
    "ReportField",
    "ReportProject",
    "ProjectGitRepo",
    "ProjectJiraComponent",
]
