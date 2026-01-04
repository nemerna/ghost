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
]

