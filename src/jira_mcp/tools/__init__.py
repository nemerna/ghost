"""MCP Tools for Jira operations."""

from jira_mcp.tools.tickets import (
    jira_list_tickets,
    jira_get_ticket,
    jira_create_ticket,
    jira_update_ticket,
)
from jira_mcp.tools.comments import (
    jira_add_comment,
    jira_get_comments,
)
from jira_mcp.tools.discovery import (
    jira_list_projects,
    jira_list_components,
    jira_list_issue_types,
    jira_list_priorities,
    jira_list_statuses,
    jira_get_transitions,
    jira_get_current_user,
)
from jira_mcp.tools.reports import (
    log_activity,
    get_weekly_activity,
    generate_weekly_report,
    save_weekly_report,
    list_saved_reports,
    get_saved_report,
    delete_saved_report,
    # Management Reports
    save_management_report,
    list_management_reports,
    get_management_report,
    update_management_report,
    delete_management_report,
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
    # Activity tracking & Reports
    "log_activity",
    "get_weekly_activity",
    "generate_weekly_report",
    "save_weekly_report",
    "list_saved_reports",
    "get_saved_report",
    "delete_saved_report",
    # Management Reports
    "save_management_report",
    "list_management_reports",
    "get_management_report",
    "update_management_report",
    "delete_management_report",
]
