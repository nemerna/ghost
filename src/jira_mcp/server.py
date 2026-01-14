"""MCP Server for Jira with stdio and SSE transport support."""

import argparse
import asyncio
import json
import logging
import os
import sys
from contextvars import ContextVar
from typing import Any, Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from jira_mcp.jira_client import JiraClient, JiraClientError

from jira_mcp.tools.schemas import (
    ListTicketsInput,
    GetTicketInput,
    CreateTicketInput,
    UpdateTicketInput,
    AddCommentInput,
    GetCommentsInput,
    UpdateCommentInput,
    DeleteCommentInput,
    ListComponentsInput,
    ListIssueTypesInput,
    ListStatusesInput,
    GetTransitionsInput,
    LinkIssuesInput,
    CreateSubtaskInput,
    SetEpicInput,
    # Activity & Reports
    LogActivityInput,
    GetWeeklyActivityInput,
    GenerateWeeklyReportInput,
    SaveWeeklyReportInput,
    ListSavedReportsInput,
    GetSavedReportInput,
    DeleteSavedReportInput,
    # Management Reports
    SaveManagementReportInput,
    ListManagementReportsInput,
    GetManagementReportInput,
    UpdateManagementReportInput,
    DeleteManagementReportInput,
)

# Import activity tracking and report functions
from jira_mcp.tools import reports as report_tools
from jira_mcp.db import init_db

# Configure logging
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger(__name__)

# Create MCP Server
mcp_server = Server("jira-mcp")

# Context variable for per-connection Jira client (used in SSE mode)
_jira_client_ctx: ContextVar[Optional[JiraClient]] = ContextVar("jira_client", default=None)

# Global Jira client for stdio mode
_jira_client_global: Optional[JiraClient] = None


def create_jira_client(
    server_url: Optional[str] = None,
    token: Optional[str] = None,
    verify_ssl: bool = True,
) -> JiraClient:
    """Create a Jira client with the given or environment configuration."""
    # Use provided values or fall back to environment variables
    server_url = server_url or os.environ.get("JIRA_SERVER_URL")
    token = token or os.environ.get("JIRA_PERSONAL_ACCESS_TOKEN")
    
    if verify_ssl is True:
        # Check environment variable
        env_verify = os.environ.get("JIRA_VERIFY_SSL", "true").lower()
        verify_ssl = env_verify in ("true", "1", "yes")
    
    if not server_url:
        raise ValueError(
            "Jira server URL is required. "
            "Set X-Jira-Server-URL header or JIRA_SERVER_URL environment variable."
        )
    if not token:
        raise ValueError(
            "Jira token is required. "
            "Set X-Jira-Token header or JIRA_PERSONAL_ACCESS_TOKEN environment variable."
        )
    
    return JiraClient(
        server_url=server_url,
        token=token,
        verify_ssl=verify_ssl,
    )


def get_jira_client() -> JiraClient:
    """Get Jira client from context (SSE) or global (stdio)."""
    # First try context variable (set per SSE connection)
    client = _jira_client_ctx.get()
    if client is not None:
        return client
    
    # Fall back to global client (stdio mode)
    global _jira_client_global
    if _jira_client_global is None:
        _jira_client_global = create_jira_client()
    return _jira_client_global


# --- MCP Tool Definitions ---

TOOLS: list[Tool] = [
    Tool(
        name="jira_list_tickets",
        description="List Jira tickets with optional filters. Returns ticket summaries including key, summary, status, assignee, and priority.",
        inputSchema={
            "type": "object",
            "properties": {
                "assignee": {
                    "type": "string",
                    "description": "Filter by assignee username. Use 'currentUser' for the authenticated user.",
                },
                "project": {
                    "type": "string",
                    "description": "Filter by project key (e.g., 'PROJ').",
                },
                "component": {
                    "type": "string",
                    "description": "Filter by component name.",
                },
                "epic_key": {
                    "type": "string",
                    "description": "Filter by epic issue key (e.g., 'PROJ-100').",
                },
                "status": {
                    "type": "string",
                    "description": "Filter by issue status (e.g., 'Open', 'In Progress', 'Done').",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return (1-100). Default: 50.",
                    "default": 50,
                    "minimum": 1,
                    "maximum": 100,
                },
            },
        },
    ),
    Tool(
        name="jira_get_ticket",
        description="Get full details of a specific Jira ticket including description, components, labels, comments count, and epic link.",
        inputSchema={
            "type": "object",
            "properties": {
                "ticket_key": {
                    "type": "string",
                    "description": "The issue key (e.g., 'PROJ-123').",
                },
            },
            "required": ["ticket_key"],
        },
    ),
    Tool(
        name="jira_create_ticket",
        description="Create a new Jira ticket with specified fields. Returns the created ticket key and URL.",
        inputSchema={
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Project key (e.g., 'PROJ').",
                },
                "summary": {
                    "type": "string",
                    "description": "Issue title/summary.",
                },
                "description": {
                    "type": "string",
                    "description": "Issue description (supports Jira wiki markup).",
                },
                "issue_type": {
                    "type": "string",
                    "description": "Issue type (e.g., 'Task', 'Bug', 'Story', 'Epic'). Default: 'Task'.",
                    "default": "Task",
                },
                "assignee": {
                    "type": "string",
                    "description": "Assignee username.",
                },
                "components": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of component names.",
                },
                "epic_key": {
                    "type": "string",
                    "description": "Parent epic issue key.",
                },
                "priority": {
                    "type": "string",
                    "description": "Priority name (e.g., 'High', 'Medium', 'Low').",
                },
                "labels": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of labels.",
                },
            },
            "required": ["project", "summary"],
        },
    ),
    Tool(
        name="jira_update_ticket",
        description="Update an existing Jira ticket's fields including title, description, assignee, status, components, and priority.",
        inputSchema={
            "type": "object",
            "properties": {
                "ticket_key": {
                    "type": "string",
                    "description": "The issue key (e.g., 'PROJ-123').",
                },
                "summary": {
                    "type": "string",
                    "description": "New issue title/summary.",
                },
                "description": {
                    "type": "string",
                    "description": "New issue description (supports Jira wiki markup).",
                },
                "assignee": {
                    "type": "string",
                    "description": "New assignee username. Use empty string to unassign.",
                },
                "status": {
                    "type": "string",
                    "description": "Transition to this status (e.g., 'In Progress', 'Done').",
                },
                "components": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "New list of component names (replaces existing).",
                },
                "priority": {
                    "type": "string",
                    "description": "New priority name.",
                },
            },
            "required": ["ticket_key"],
        },
    ),
    Tool(
        name="jira_add_comment",
        description="Add a comment to a Jira ticket. Supports Jira wiki markup in the comment body.",
        inputSchema={
            "type": "object",
            "properties": {
                "ticket_key": {
                    "type": "string",
                    "description": "The issue key (e.g., 'PROJ-123').",
                },
                "body": {
                    "type": "string",
                    "description": "Comment body (supports Jira wiki markup).",
                },
            },
            "required": ["ticket_key", "body"],
        },
    ),
    Tool(
        name="jira_get_comments",
        description="Get comments from a Jira ticket. Returns comment ID, author, body, and timestamps.",
        inputSchema={
            "type": "object",
            "properties": {
                "ticket_key": {
                    "type": "string",
                    "description": "The issue key (e.g., 'PROJ-123').",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of comments to return (1-100). Default: 20.",
                    "default": 20,
                    "minimum": 1,
                    "maximum": 100,
                },
            },
            "required": ["ticket_key"],
        },
    ),
    Tool(
        name="jira_update_comment",
        description="Update an existing comment on a Jira ticket. Only comments authored by the current user can be updated.",
        inputSchema={
            "type": "object",
            "properties": {
                "ticket_key": {
                    "type": "string",
                    "description": "The issue key (e.g., 'PROJ-123').",
                },
                "comment_id": {
                    "type": "string",
                    "description": "The comment ID to update (get this from jira_get_comments).",
                },
                "body": {
                    "type": "string",
                    "description": "New comment body (supports Jira wiki markup).",
                },
            },
            "required": ["ticket_key", "comment_id", "body"],
        },
    ),
    Tool(
        name="jira_delete_comment",
        description="Delete a comment from a Jira ticket. Only comments authored by the current user can be deleted.",
        inputSchema={
            "type": "object",
            "properties": {
                "ticket_key": {
                    "type": "string",
                    "description": "The issue key (e.g., 'PROJ-123').",
                },
                "comment_id": {
                    "type": "string",
                    "description": "The comment ID to delete (get this from jira_get_comments).",
                },
            },
            "required": ["ticket_key", "comment_id"],
        },
    ),
    # --- Discovery/Metadata Tools ---
    Tool(
        name="jira_list_projects",
        description="List all accessible Jira projects. Returns project key, name, lead, and URL for each project.",
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
    Tool(
        name="jira_list_components",
        description="List components available in a Jira project. Useful for knowing valid component names when creating or filtering tickets.",
        inputSchema={
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Project key (e.g., 'PROJ').",
                },
            },
            "required": ["project"],
        },
    ),
    Tool(
        name="jira_list_issue_types",
        description="List issue types available in a Jira project. Returns types like Task, Bug, Story, Epic, etc.",
        inputSchema={
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Project key (e.g., 'PROJ').",
                },
            },
            "required": ["project"],
        },
    ),
    Tool(
        name="jira_list_priorities",
        description="List all available priority levels in Jira. Returns priority names like High, Medium, Low, etc.",
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
    Tool(
        name="jira_list_statuses",
        description="List available statuses for a Jira project. Returns status names and their categories (To Do, In Progress, Done).",
        inputSchema={
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Project key (e.g., 'PROJ').",
                },
            },
            "required": ["project"],
        },
    ),
    Tool(
        name="jira_get_transitions",
        description="Get available workflow transitions for a specific ticket. Shows what status changes are possible from the current state.",
        inputSchema={
            "type": "object",
            "properties": {
                "ticket_key": {
                    "type": "string",
                    "description": "The issue key (e.g., 'PROJ-123').",
                },
            },
            "required": ["ticket_key"],
        },
    ),
    Tool(
        name="jira_get_current_user",
        description="Get information about the currently authenticated user. Returns username, display name, email, and timezone.",
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
    # --- Issue Linking & Hierarchy Tools ---
    Tool(
        name="jira_link_issues",
        description="Create a link between two Jira issues. Common link types include 'relates to', 'blocks', 'is blocked by', 'is part of', 'duplicates', 'clones'.",
        inputSchema={
            "type": "object",
            "properties": {
                "from_key": {
                    "type": "string",
                    "description": "The source issue key (e.g., 'PROJ-123').",
                },
                "to_key": {
                    "type": "string",
                    "description": "The target issue key (e.g., 'PROJ-456').",
                },
                "link_type": {
                    "type": "string",
                    "description": "The type of link (e.g., 'relates to', 'blocks', 'is blocked by', 'is part of', 'duplicates'). Default: 'relates to'.",
                    "default": "relates to",
                },
            },
            "required": ["from_key", "to_key"],
        },
    ),
    Tool(
        name="jira_create_subtask",
        description="Create a sub-task under a parent Jira issue. The sub-task inherits the project from the parent.",
        inputSchema={
            "type": "object",
            "properties": {
                "parent_key": {
                    "type": "string",
                    "description": "The parent issue key (e.g., 'PROJ-123').",
                },
                "summary": {
                    "type": "string",
                    "description": "Sub-task title/summary.",
                },
                "description": {
                    "type": "string",
                    "description": "Sub-task description (supports Jira wiki markup).",
                },
                "assignee": {
                    "type": "string",
                    "description": "Assignee username.",
                },
                "priority": {
                    "type": "string",
                    "description": "Priority name (e.g., 'High', 'Medium', 'Low').",
                },
            },
            "required": ["parent_key", "summary"],
        },
    ),
    Tool(
        name="jira_set_epic",
        description="Set or change the epic for a Jira issue. Associates the issue with the specified epic.",
        inputSchema={
            "type": "object",
            "properties": {
                "issue_key": {
                    "type": "string",
                    "description": "The issue key to update (e.g., 'PROJ-123').",
                },
                "epic_key": {
                    "type": "string",
                    "description": "The epic issue key to set as parent (e.g., 'PROJ-100').",
                },
            },
            "required": ["issue_key", "epic_key"],
        },
    ),
    # --- Activity Tracking & Weekly Reports ---
    Tool(
        name="log_jira_activity",
        description="Log a Jira ticket activity for weekly report tracking. Call this when working on tickets to track your work.",
        inputSchema={
            "type": "object",
            "properties": {
                "ticket_key": {
                    "type": "string",
                    "description": "The Jira ticket key (e.g., 'PROJ-123').",
                },
                "action_type": {
                    "type": "string",
                    "enum": ["view", "create", "update", "comment", "transition", "link", "other"],
                    "description": "Type of action performed.",
                    "default": "other",
                },
                "ticket_summary": {
                    "type": "string",
                    "description": "Optional ticket summary for context.",
                },
                "action_details": {
                    "type": "string",
                    "description": "Optional JSON string with additional context.",
                },
            },
            "required": ["ticket_key"],
        },
    ),
    Tool(
        name="get_weekly_activity",
        description="Get activity summary for a specific week. Shows tickets worked on and actions performed.",
        inputSchema={
            "type": "object",
            "properties": {
                "week_offset": {
                    "type": "integer",
                    "description": "Week offset from current week (0 = current, -1 = last week). Range: -52 to 0.",
                    "default": 0,
                    "minimum": -52,
                    "maximum": 0,
                },
                "project": {
                    "type": "string",
                    "description": "Optional project key to filter by.",
                },
            },
        },
    ),
    Tool(
        name="generate_weekly_report",
        description="Generate an executive weekly report for management. Creates a formatted Markdown report with metrics and ticket details.",
        inputSchema={
            "type": "object",
            "properties": {
                "week_offset": {
                    "type": "integer",
                    "description": "Week offset from current week (0 = current, -1 = last week). Range: -52 to 0.",
                    "default": 0,
                    "minimum": -52,
                    "maximum": 0,
                },
                "include_details": {
                    "type": "boolean",
                    "description": "Whether to include detailed ticket list in the report.",
                    "default": True,
                },
            },
        },
    ),
    Tool(
        name="save_weekly_report",
        description="Generate and save a weekly report to the database for future reference.",
        inputSchema={
            "type": "object",
            "properties": {
                "week_offset": {
                    "type": "integer",
                    "description": "Week offset from current week (0 = current, -1 = last week). Range: -52 to 0.",
                    "default": 0,
                    "minimum": -52,
                    "maximum": 0,
                },
                "custom_title": {
                    "type": "string",
                    "description": "Optional custom title override.",
                },
                "custom_summary": {
                    "type": "string",
                    "description": "Optional custom executive summary override.",
                },
            },
        },
    ),
    Tool(
        name="list_saved_reports",
        description="List previously saved weekly reports.",
        inputSchema={
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of reports to return (1-50).",
                    "default": 10,
                    "minimum": 1,
                    "maximum": 50,
                },
            },
        },
    ),
    Tool(
        name="get_saved_report",
        description="Get a saved weekly report by its ID. Returns full report content.",
        inputSchema={
            "type": "object",
            "properties": {
                "report_id": {
                    "type": "integer",
                    "description": "The report ID to retrieve.",
                },
            },
            "required": ["report_id"],
        },
    ),
    Tool(
        name="delete_saved_report",
        description="Delete a saved weekly report.",
        inputSchema={
            "type": "object",
            "properties": {
                "report_id": {
                    "type": "integer",
                    "description": "The report ID to delete.",
                },
            },
            "required": ["report_id"],
        },
    ),
    # --- Management Reports (AI-generated for stakeholders) ---
    Tool(
        name="save_management_report",
        description="""Save an AI-generated management report for high-level stakeholders.

IMPORTANT: Reports should be CONCISE and management-friendly:
- one_liner: Single sentence (max 15 words) - the "elevator pitch"
- executive_summary: 2-3 sentences, high-level outcomes only
- content: Short Markdown (aim for <500 words), use bullet points, include Jira links

Focus on: What was delivered, business impact, blockers, next steps.
Avoid: Technical details, implementation specifics, code-level information.""",
        inputSchema={
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Report title (e.g., 'APPENG Progress - Week 3').",
                },
                "one_liner": {
                    "type": "string",
                    "description": "Single sentence elevator pitch (max 15 words). E.g., 'Delivered OAuth integration, 3 bugs fixed, on track for Q1.'",
                },
                "executive_summary": {
                    "type": "string",
                    "description": "2-3 sentence summary. Focus on outcomes and business impact, not technical details.",
                },
                "content": {
                    "type": "string",
                    "description": "Concise Markdown report (<500 words). Use bullet points. Include Jira links. Sections: Delivered, In Progress, Blockers, Next Week.",
                },
                "project_key": {
                    "type": "string",
                    "description": "Project key (e.g., 'APPENG').",
                },
                "report_period": {
                    "type": "string",
                    "description": "Period (e.g., 'Week 3, Jan 2026' or 'Sprint 42').",
                },
                "referenced_tickets": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Jira ticket keys mentioned in report.",
                },
            },
            "required": ["title", "executive_summary", "content"],
        },
    ),
    Tool(
        name="list_management_reports",
        description="List saved management reports. Can filter by project.",
        inputSchema={
            "type": "object",
            "properties": {
                "project_key": {
                    "type": "string",
                    "description": "Optional filter by project key.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of reports to return (1-50).",
                    "default": 10,
                    "minimum": 1,
                    "maximum": 50,
                },
            },
        },
    ),
    Tool(
        name="get_management_report",
        description="Get a saved management report by ID. Returns full content.",
        inputSchema={
            "type": "object",
            "properties": {
                "report_id": {
                    "type": "integer",
                    "description": "The management report ID to retrieve.",
                },
            },
            "required": ["report_id"],
        },
    ),
    Tool(
        name="update_management_report",
        description="Update an existing management report with new content.",
        inputSchema={
            "type": "object",
            "properties": {
                "report_id": {
                    "type": "integer",
                    "description": "The management report ID to update.",
                },
                "title": {
                    "type": "string",
                    "description": "Optional new title.",
                },
                "one_liner": {
                    "type": "string",
                    "description": "Optional new one-liner elevator pitch.",
                },
                "executive_summary": {
                    "type": "string",
                    "description": "Optional new executive summary.",
                },
                "content": {
                    "type": "string",
                    "description": "Optional new Markdown content.",
                },
                "report_period": {
                    "type": "string",
                    "description": "Optional new period.",
                },
                "referenced_tickets": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional new list of referenced ticket keys.",
                },
            },
            "required": ["report_id"],
        },
    ),
    Tool(
        name="delete_management_report",
        description="Delete a management report.",
        inputSchema={
            "type": "object",
            "properties": {
                "report_id": {
                    "type": "integer",
                    "description": "The management report ID to delete.",
                },
            },
            "required": ["report_id"],
        },
    ),
]


@mcp_server.list_tools()
async def list_tools() -> list[Tool]:
    """List available MCP tools."""
    return TOOLS


@mcp_server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls from MCP clients."""
    try:
        jira_client = get_jira_client()
        result = await _execute_tool(name, arguments, jira_client)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    except JiraClientError as e:
        error_response = {
            "error": True,
            "message": e.message,
            "status_code": e.status_code,
        }
        return [TextContent(type="text", text=json.dumps(error_response, indent=2))]
    except Exception as e:
        logger.exception(f"Error executing tool {name}")
        error_response = {
            "error": True,
            "message": str(e),
        }
        return [TextContent(type="text", text=json.dumps(error_response, indent=2))]


async def _execute_tool(
    name: str, arguments: dict[str, Any], jira_client: JiraClient
) -> dict[str, Any] | list[dict[str, Any]]:
    """Execute a specific tool and return the result."""

    if name == "jira_list_tickets":
        input_data = ListTicketsInput(**arguments)
        jql = jira_client.build_jql(
            assignee=input_data.assignee,
            project=input_data.project,
            component=input_data.component,
            epic_key=input_data.epic_key,
            status=input_data.status,
        )
        return jira_client.search_issues(jql, max_results=input_data.max_results)

    elif name == "jira_get_ticket":
        input_data = GetTicketInput(**arguments)
        return jira_client.get_issue(input_data.ticket_key)

    elif name == "jira_create_ticket":
        input_data = CreateTicketInput(**arguments)
        return jira_client.create_issue(
            project=input_data.project,
            summary=input_data.summary,
            description=input_data.description,
            issue_type=input_data.issue_type,
            assignee=input_data.assignee,
            components=input_data.components,
            epic_key=input_data.epic_key,
            priority=input_data.priority,
            labels=input_data.labels,
        )

    elif name == "jira_update_ticket":
        input_data = UpdateTicketInput(**arguments)
        return jira_client.update_issue(
            issue_key=input_data.ticket_key,
            summary=input_data.summary,
            description=input_data.description,
            assignee=input_data.assignee,
            status=input_data.status,
            components=input_data.components,
            priority=input_data.priority,
        )

    elif name == "jira_add_comment":
        input_data = AddCommentInput(**arguments)
        return jira_client.add_comment(
            issue_key=input_data.ticket_key,
            body=input_data.body,
        )

    elif name == "jira_get_comments":
        input_data = GetCommentsInput(**arguments)
        return jira_client.get_comments(
            issue_key=input_data.ticket_key,
            max_results=input_data.max_results,
        )

    elif name == "jira_update_comment":
        input_data = UpdateCommentInput(**arguments)
        return jira_client.update_comment(
            issue_key=input_data.ticket_key,
            comment_id=input_data.comment_id,
            body=input_data.body,
        )

    elif name == "jira_delete_comment":
        input_data = DeleteCommentInput(**arguments)
        return jira_client.delete_comment(
            issue_key=input_data.ticket_key,
            comment_id=input_data.comment_id,
        )

    # --- Discovery/Metadata Tools ---

    elif name == "jira_list_projects":
        return jira_client.get_projects()

    elif name == "jira_list_components":
        input_data = ListComponentsInput(**arguments)
        return jira_client.get_components(input_data.project)

    elif name == "jira_list_issue_types":
        input_data = ListIssueTypesInput(**arguments)
        return jira_client.get_issue_types(input_data.project)

    elif name == "jira_list_priorities":
        return jira_client.get_priorities()

    elif name == "jira_list_statuses":
        input_data = ListStatusesInput(**arguments)
        return jira_client.get_statuses(input_data.project)

    elif name == "jira_get_transitions":
        input_data = GetTransitionsInput(**arguments)
        return jira_client.get_transitions(input_data.ticket_key)

    elif name == "jira_get_current_user":
        return jira_client.get_current_user()

    # --- Issue Linking & Hierarchy Tools ---

    elif name == "jira_link_issues":
        input_data = LinkIssuesInput(**arguments)
        return jira_client.link_issues(
            from_key=input_data.from_key,
            to_key=input_data.to_key,
            link_type=input_data.link_type,
        )

    elif name == "jira_create_subtask":
        input_data = CreateSubtaskInput(**arguments)
        return jira_client.create_subtask(
            parent_key=input_data.parent_key,
            summary=input_data.summary,
            description=input_data.description,
            assignee=input_data.assignee,
            priority=input_data.priority,
        )

    elif name == "jira_set_epic":
        input_data = SetEpicInput(**arguments)
        return jira_client.set_epic(
            issue_key=input_data.issue_key,
            epic_key=input_data.epic_key,
        )

    # --- Activity Tracking & Weekly Reports ---

    elif name == "log_jira_activity":
        input_data = LogActivityInput(**arguments)
        # Get username from Jira client
        user_info = jira_client.get_current_user()
        username = user_info.get("username", "unknown")
        
        action_details = None
        if input_data.action_details:
            try:
                import json
                action_details = json.loads(input_data.action_details)
            except json.JSONDecodeError:
                action_details = {"raw": input_data.action_details}
        
        return report_tools.log_activity(
            username=username,
            ticket_key=input_data.ticket_key,
            action_type=input_data.action_type,
            ticket_summary=input_data.ticket_summary,
            action_details=action_details,
        )

    elif name == "get_weekly_activity":
        input_data = GetWeeklyActivityInput(**arguments)
        # Get username from Jira client
        user_info = jira_client.get_current_user()
        username = user_info.get("username", "unknown")
        
        return report_tools.get_weekly_activity(
            username=username,
            week_offset=input_data.week_offset,
            project=input_data.project,
        )

    elif name == "generate_weekly_report":
        input_data = GenerateWeeklyReportInput(**arguments)
        # Get username from Jira client
        user_info = jira_client.get_current_user()
        username = user_info.get("username", "unknown")
        
        return report_tools.generate_weekly_report(
            username=username,
            week_offset=input_data.week_offset,
            include_details=input_data.include_details,
        )

    elif name == "save_weekly_report":
        input_data = SaveWeeklyReportInput(**arguments)
        # Get username from Jira client
        user_info = jira_client.get_current_user()
        username = user_info.get("username", "unknown")
        
        return report_tools.save_weekly_report(
            username=username,
            week_offset=input_data.week_offset,
            custom_title=input_data.custom_title,
            custom_summary=input_data.custom_summary,
        )

    elif name == "list_saved_reports":
        input_data = ListSavedReportsInput(**arguments)
        # Get username from Jira client
        user_info = jira_client.get_current_user()
        username = user_info.get("username", "unknown")
        
        return report_tools.list_saved_reports(
            username=username,
            limit=input_data.limit,
        )

    elif name == "get_saved_report":
        input_data = GetSavedReportInput(**arguments)
        return report_tools.get_saved_report(
            report_id=input_data.report_id,
        )

    elif name == "delete_saved_report":
        input_data = DeleteSavedReportInput(**arguments)
        return report_tools.delete_saved_report(
            report_id=input_data.report_id,
        )

    # --- Management Reports (AI-generated) ---

    elif name == "save_management_report":
        input_data = SaveManagementReportInput(**arguments)
        # Get username from Jira client
        user_info = jira_client.get_current_user()
        username = user_info.get("username", "unknown")
        
        return report_tools.save_management_report(
            username=username,
            title=input_data.title,
            one_liner=input_data.one_liner,
            executive_summary=input_data.executive_summary,
            content=input_data.content,
            project_key=input_data.project_key,
            report_period=input_data.report_period,
            referenced_tickets=input_data.referenced_tickets,
        )

    elif name == "list_management_reports":
        input_data = ListManagementReportsInput(**arguments)
        # Get username from Jira client
        user_info = jira_client.get_current_user()
        username = user_info.get("username", "unknown")
        
        return report_tools.list_management_reports(
            username=username,
            project_key=input_data.project_key,
            limit=input_data.limit,
        )

    elif name == "get_management_report":
        input_data = GetManagementReportInput(**arguments)
        return report_tools.get_management_report(
            report_id=input_data.report_id,
        )

    elif name == "update_management_report":
        input_data = UpdateManagementReportInput(**arguments)
        return report_tools.update_management_report(
            report_id=input_data.report_id,
            title=input_data.title,
            one_liner=input_data.one_liner,
            executive_summary=input_data.executive_summary,
            content=input_data.content,
            report_period=input_data.report_period,
            referenced_tickets=input_data.referenced_tickets,
        )

    elif name == "delete_management_report":
        input_data = DeleteManagementReportInput(**arguments)
        return report_tools.delete_management_report(
            report_id=input_data.report_id,
        )

    else:
        raise ValueError(f"Unknown tool: {name}")


# --- Transport Implementations ---


async def run_stdio() -> None:
    """Run the MCP server with stdio transport (for Cursor/Claude Desktop)."""
    logger.info("Starting Jira MCP server with stdio transport")
    
    async with stdio_server() as (read_stream, write_stream):
        await mcp_server.run(
            read_stream,
            write_stream,
            mcp_server.create_initialization_options(),
        )


async def run_sse(host: str, port: int) -> None:
    """Run the MCP server with SSE transport (HTTP server mode)."""
    import uvicorn
    from mcp.server.sse import SseServerTransport
    from starlette.applications import Starlette
    from starlette.requests import Request
    from starlette.responses import JSONResponse, Response
    from starlette.routing import Mount, Route
    from starlette.types import Receive, Scope, Send

    logger.info(f"Starting Jira MCP server with SSE transport on {host}:{port}")

    # SSE Transport
    sse_transport = SseServerTransport("/messages/")

    async def health_check(request: Request) -> JSONResponse:
        """Health check endpoint."""
        return JSONResponse({"status": "healthy"})

    async def handle_sse_raw(scope: Scope, receive: Receive, send: Send) -> None:
        """Handle SSE connection as raw ASGI app."""
        # Extract headers from scope
        headers = dict(scope.get("headers", []))
        
        # Get Jira configuration from headers (case-insensitive)
        server_url = None
        token = None
        verify_ssl = True
        
        for key, value in headers.items():
            key_lower = key.decode("utf-8").lower() if isinstance(key, bytes) else key.lower()
            value_str = value.decode("utf-8") if isinstance(value, bytes) else value
            
            if key_lower == "x-jira-server-url":
                server_url = value_str
            elif key_lower == "x-jira-token":
                token = value_str
            elif key_lower == "x-jira-verify-ssl":
                verify_ssl = value_str.lower() in ("true", "1", "yes")
        
        # Create client and set in context
        try:
            client = create_jira_client(
                server_url=server_url,
                token=token,
                verify_ssl=verify_ssl,
            )
            _jira_client_ctx.set(client)
            logger.info(f"SSE connection established with Jira server: {client.server_url}")
        except ValueError as e:
            logger.warning(f"Jira client configuration: {e}")
            # Will fail when tool is called if not configured
        
        async with sse_transport.connect_sse(scope, receive, send) as streams:
            await mcp_server.run(
                streams[0],
                streams[1],
                mcp_server.create_initialization_options(),
            )

    async def handle_sse(request: Request) -> Response:
        """Handle SSE connection - wrapper for Starlette Route."""
        await handle_sse_raw(request.scope, request.receive, request._send)
        return Response()

    # Create Starlette app with routes
    app = Starlette(
        debug=False,
        routes=[
            Route("/health", endpoint=health_check, methods=["GET"]),
            Route("/sse", endpoint=handle_sse, methods=["GET"]),
            Mount("/messages/", app=sse_transport.handle_post_message),
        ],
    )

    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="info",
    )
    server = uvicorn.Server(config)
    await server.serve()


def main() -> None:
    """Run the MCP server."""
    # Initialize database on startup
    init_db()
    logger.info("Database initialized")
    
    parser = argparse.ArgumentParser(
        description="Jira MCP Server - Model Context Protocol server for Jira",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with stdio transport (default, for Cursor/Claude Desktop)
  jira-mcp

  # Run with SSE transport (HTTP server mode)
  jira-mcp --transport sse --host 0.0.0.0 --port 8080

Configuration:
  For stdio transport: Set environment variables or pass via MCP client config
  For SSE transport: Set via HTTP headers or environment variables

  Headers (SSE mode):
    X-Jira-Server-URL    Jira server URL
    X-Jira-Token         Personal Access Token  
    X-Jira-Verify-SSL    Verify SSL (true/false)

  Environment Variables:
    JIRA_SERVER_URL              Jira server URL
    JIRA_PERSONAL_ACCESS_TOKEN   Personal Access Token
    JIRA_VERIFY_SSL              Verify SSL certificates (default: true)
        """,
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="Transport type: 'stdio' for Cursor/Claude Desktop, 'sse' for HTTP server (default: stdio)",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host address for SSE transport (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port for SSE transport (default: 8080)",
    )

    args = parser.parse_args()

    if args.transport == "stdio":
        asyncio.run(run_stdio())
    else:
        asyncio.run(run_sse(args.host, args.port))


if __name__ == "__main__":
    main()
