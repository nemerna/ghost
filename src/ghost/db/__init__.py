"""Database layer for management reports and user management."""

from ghost.db.database import Database, get_db, init_db
from ghost.db.models import (
    ConsolidatedReportDraft,
    ConsolidatedReportSnapshot,
    GitHubTokenConfig,
    Goal,
    GoalEntryLink,
    GoalHorizon,
    GoalNote,
    GoalScope,
    GoalStatus,
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
    "TicketSource",
    "UserRole",
    "SnapshotType",
    "GoalScope",
    "GoalHorizon",
    "GoalStatus",
    # User & Team Models
    "User",
    "Team",
    "TeamMembership",
    "PersonalAccessToken",
    "GitHubTokenConfig",
    # Report Models
    "ManagementReport",
    "ConsolidatedReportDraft",
    "ConsolidatedReportSnapshot",
    # Report Field & Project Configuration Models
    "ReportField",
    "ReportProject",
    "ProjectGitRepo",
    "ProjectJiraComponent",
    # Goal Models
    "Goal",
    "GoalEntryLink",
    "GoalNote",
]
