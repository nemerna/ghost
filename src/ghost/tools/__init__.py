"""MCP Tools for Jira operations."""

from ghost.tools.comments import (
    jira_add_comment,
    jira_get_comments,
)
from ghost.tools.discovery import (
    jira_get_current_user,
    jira_get_transitions,
    jira_list_components,
    jira_list_issue_types,
    jira_list_priorities,
    jira_list_projects,
    jira_list_statuses,
)
from ghost.tools.reports import (
    delete_management_report,
    detect_project_for_activity,
    get_management_report,
    get_weekly_activity,
    list_management_reports,
    log_activity,
    redetect_project_assignments,
    save_management_report,
    update_management_report,
)
from ghost.tools.tickets import (
    jira_create_ticket,
    jira_get_ticket,
    jira_list_tickets,
    jira_update_ticket,
)

__all__ = [
    # Ticket operations
    "jira_list_tickets",
    "jira_get_ticket",
    "jira_create_ticket",
    "jira_update_ticket",
    # Comment operations
    "jira_add_comment",
    "jira_get_comments",
    # Discovery/Metadata operations
    "jira_list_projects",
    "jira_list_components",
    "jira_list_issue_types",
    "jira_list_priorities",
    "jira_list_statuses",
    "jira_get_transitions",
    "jira_get_current_user",
    # Activity tracking
    "log_activity",
    "get_weekly_activity",
    # Management Reports
    "save_management_report",
    "list_management_reports",
    "get_management_report",
    "update_management_report",
    "delete_management_report",
    # Project Detection
    "detect_project_for_activity",
    "redetect_project_assignments",
]
