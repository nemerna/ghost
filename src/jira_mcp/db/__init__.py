"""Database layer for Jira MCP activity tracking, reports, and user management."""

from jira_mcp.db.database import Database, get_db, init_db
from jira_mcp.db.models import (
    ActionType,
    ActivityLog,
    ConsolidatedReportDraft,
    ConsolidatedReportSnapshot,
    ManagementReport,
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
    WeeklyReport,
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
    # Activity & Report Models
    "ActivityLog",
    "WeeklyReport",
    "ManagementReport",
    "ConsolidatedReportDraft",
    "ConsolidatedReportSnapshot",
    # Report Field & Project Configuration Models
    "ReportField",
    "ReportProject",
    "ProjectGitRepo",
    "ProjectJiraComponent",
]
