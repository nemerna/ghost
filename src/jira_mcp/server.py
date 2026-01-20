"""MCP Server for Jira and GitHub with separate SSE endpoints."""

import argparse
import asyncio
import json
import logging
import os
import sys
from contextvars import ContextVar
from typing import Any, Optional

from mcp.server import Server
from mcp.types import Tool, TextContent

from jira_mcp.jira_client import JiraClient, JiraClientError
from jira_mcp.github_client import GitHubClient, GitHubClientError

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
    # GitHub Pull Requests
    GitHubListPRsInput,
    GitHubGetPRInput,
    GitHubGetPRDiffInput,
    GitHubGetPRFilesInput,
    GitHubGetPRCommitsInput,
    GitHubGetPRReviewsInput,
    GitHubGetPRCommentsInput,
    GitHubAddPRCommentInput,
    GitHubSearchPRsInput,
)

# Import activity tracking and report functions
from jira_mcp.tools import reports as report_tools
from jira_mcp.db import init_db

# Configure logging
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger(__name__)

# Create separate MCP Servers for Jira and GitHub
jira_mcp_server = Server("jira-mcp")
github_mcp_server = Server("github-mcp")

# Context variables for per-connection clients (SSE mode)
_jira_client_ctx: ContextVar[Optional[JiraClient]] = ContextVar("jira_client", default=None)
_github_client_ctx: ContextVar[Optional[GitHubClient]] = ContextVar("github_client", default=None)


def create_jira_client(
    server_url: Optional[str] = None,
    token: Optional[str] = None,
    verify_ssl: bool = True,
) -> JiraClient:
    """Create a Jira client with the given configuration."""
    if not server_url:
        raise ValueError("Jira server URL is required. Set X-Jira-Server-URL header.")
    if not token:
        raise ValueError("Jira token is required. Set X-Jira-Token header.")
    
    return JiraClient(
        server_url=server_url,
        token=token,
        verify_ssl=verify_ssl,
    )


def get_jira_client() -> JiraClient:
    """Get Jira client from context."""
    client = _jira_client_ctx.get()
    if client is None:
        raise ValueError("Jira client not configured. Ensure X-Jira-Server-URL and X-Jira-Token headers are set.")
    return client


def create_github_client(
    token: Optional[str] = None,
    api_url: Optional[str] = None,
) -> GitHubClient:
    """Create a GitHub client with the given configuration."""
    if not token:
        raise ValueError("GitHub token is required. Set X-GitHub-Token header.")
    
    return GitHubClient(
        token=token,
        api_url=api_url,
    )


def get_github_client() -> GitHubClient:
    """Get GitHub client from context."""
    client = _github_client_ctx.get()
    if client is None:
        raise ValueError("GitHub client not configured. Ensure X-GitHub-Token header is set.")
    return client


# =============================================================================
# Jira Tools
# =============================================================================

JIRA_TOOLS: list[Tool] = [
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


# =============================================================================
# GitHub Tools
# =============================================================================

GITHUB_TOOLS: list[Tool] = [
    Tool(
        name="github_list_prs",
        description="List pull requests for a GitHub repository. Returns PR summaries including number, title, state, author, and branches.",
        inputSchema={
            "type": "object",
            "properties": {
                "owner": {
                    "type": "string",
                    "description": "Repository owner (user or organization).",
                },
                "repo": {
                    "type": "string",
                    "description": "Repository name.",
                },
                "state": {
                    "type": "string",
                    "description": "Filter by state: 'open', 'closed', or 'all'. Default: 'open'.",
                    "default": "open",
                    "enum": ["open", "closed", "all"],
                },
                "head": {
                    "type": "string",
                    "description": "Filter by head user/org and branch (format: 'user:branch').",
                },
                "base": {
                    "type": "string",
                    "description": "Filter by base branch name.",
                },
                "sort": {
                    "type": "string",
                    "description": "Sort by: 'created', 'updated', 'popularity', 'long-running'. Default: 'created'.",
                    "default": "created",
                    "enum": ["created", "updated", "popularity", "long-running"],
                },
                "direction": {
                    "type": "string",
                    "description": "Sort direction: 'asc' or 'desc'. Default: 'desc'.",
                    "default": "desc",
                    "enum": ["asc", "desc"],
                },
                "per_page": {
                    "type": "integer",
                    "description": "Results per page (1-100). Default: 30.",
                    "default": 30,
                    "minimum": 1,
                    "maximum": 100,
                },
                "page": {
                    "type": "integer",
                    "description": "Page number. Default: 1.",
                    "default": 1,
                    "minimum": 1,
                },
            },
            "required": ["owner", "repo"],
        },
    ),
    Tool(
        name="github_get_pr",
        description="Get full details of a specific pull request including body, merge status, stats (additions/deletions), labels, assignees, and reviewers.",
        inputSchema={
            "type": "object",
            "properties": {
                "owner": {
                    "type": "string",
                    "description": "Repository owner (user or organization).",
                },
                "repo": {
                    "type": "string",
                    "description": "Repository name.",
                },
                "pr_number": {
                    "type": "integer",
                    "description": "Pull request number.",
                },
            },
            "required": ["owner", "repo", "pr_number"],
        },
    ),
    Tool(
        name="github_get_pr_diff",
        description="Get the unified diff of a pull request. Returns the full diff as text showing all changes.",
        inputSchema={
            "type": "object",
            "properties": {
                "owner": {
                    "type": "string",
                    "description": "Repository owner (user or organization).",
                },
                "repo": {
                    "type": "string",
                    "description": "Repository name.",
                },
                "pr_number": {
                    "type": "integer",
                    "description": "Pull request number.",
                },
            },
            "required": ["owner", "repo", "pr_number"],
        },
    ),
    Tool(
        name="github_get_pr_files",
        description="Get list of files changed in a pull request with status (added/modified/removed), additions, deletions, and patch content.",
        inputSchema={
            "type": "object",
            "properties": {
                "owner": {
                    "type": "string",
                    "description": "Repository owner (user or organization).",
                },
                "repo": {
                    "type": "string",
                    "description": "Repository name.",
                },
                "pr_number": {
                    "type": "integer",
                    "description": "Pull request number.",
                },
                "per_page": {
                    "type": "integer",
                    "description": "Results per page (1-100). Default: 30.",
                    "default": 30,
                    "minimum": 1,
                    "maximum": 100,
                },
                "page": {
                    "type": "integer",
                    "description": "Page number. Default: 1.",
                    "default": 1,
                    "minimum": 1,
                },
            },
            "required": ["owner", "repo", "pr_number"],
        },
    ),
    Tool(
        name="github_get_pr_commits",
        description="Get list of commits in a pull request with SHA, message, author, and date.",
        inputSchema={
            "type": "object",
            "properties": {
                "owner": {
                    "type": "string",
                    "description": "Repository owner (user or organization).",
                },
                "repo": {
                    "type": "string",
                    "description": "Repository name.",
                },
                "pr_number": {
                    "type": "integer",
                    "description": "Pull request number.",
                },
                "per_page": {
                    "type": "integer",
                    "description": "Results per page (1-100). Default: 30.",
                    "default": 30,
                    "minimum": 1,
                    "maximum": 100,
                },
                "page": {
                    "type": "integer",
                    "description": "Page number. Default: 1.",
                    "default": 1,
                    "minimum": 1,
                },
            },
            "required": ["owner", "repo", "pr_number"],
        },
    ),
    Tool(
        name="github_get_pr_reviews",
        description="Get reviews on a pull request with state (APPROVED, CHANGES_REQUESTED, COMMENTED), reviewer, and body.",
        inputSchema={
            "type": "object",
            "properties": {
                "owner": {
                    "type": "string",
                    "description": "Repository owner (user or organization).",
                },
                "repo": {
                    "type": "string",
                    "description": "Repository name.",
                },
                "pr_number": {
                    "type": "integer",
                    "description": "Pull request number.",
                },
                "per_page": {
                    "type": "integer",
                    "description": "Results per page (1-100). Default: 30.",
                    "default": 30,
                    "minimum": 1,
                    "maximum": 100,
                },
                "page": {
                    "type": "integer",
                    "description": "Page number. Default: 1.",
                    "default": 1,
                    "minimum": 1,
                },
            },
            "required": ["owner", "repo", "pr_number"],
        },
    ),
    Tool(
        name="github_get_pr_comments",
        description="Get all comments on a pull request. Returns both issue comments (general PR discussion) and review comments (inline code comments).",
        inputSchema={
            "type": "object",
            "properties": {
                "owner": {
                    "type": "string",
                    "description": "Repository owner (user or organization).",
                },
                "repo": {
                    "type": "string",
                    "description": "Repository name.",
                },
                "pr_number": {
                    "type": "integer",
                    "description": "Pull request number.",
                },
                "per_page": {
                    "type": "integer",
                    "description": "Results per page (1-100). Default: 30.",
                    "default": 30,
                    "minimum": 1,
                    "maximum": 100,
                },
                "page": {
                    "type": "integer",
                    "description": "Page number. Default: 1.",
                    "default": 1,
                    "minimum": 1,
                },
            },
            "required": ["owner", "repo", "pr_number"],
        },
    ),
    Tool(
        name="github_add_pr_comment",
        description="Add a comment to a pull request or reply to an existing review thread. Provide in_reply_to to post a reply to a review comment.",
        inputSchema={
            "type": "object",
            "properties": {
                "owner": {
                    "type": "string",
                    "description": "Repository owner (user or organization).",
                },
                "repo": {
                    "type": "string",
                    "description": "Repository name.",
                },
                "pr_number": {
                    "type": "integer",
                    "description": "Pull request number.",
                },
                "body": {
                    "type": "string",
                    "description": "Comment body (Markdown).",
                },
                "in_reply_to": {
                    "type": "integer",
                    "description": "Optional review comment ID to reply to. If provided, posts a reply in the review thread.",
                },
            },
            "required": ["owner", "repo", "pr_number", "body"],
        },
    ),
    Tool(
        name="github_search_prs",
        description="Search for pull requests across GitHub repositories. Use GitHub search qualifiers like 'author:username', 'repo:owner/repo', 'state:open', 'label:bug', 'is:merged'.",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "GitHub search query. Examples: 'author:octocat', 'repo:facebook/react state:open', 'org:microsoft label:bug'. 'is:pr' is added automatically.",
                },
                "sort": {
                    "type": "string",
                    "description": "Sort by: 'created', 'updated', 'comments'. Default: 'created'.",
                    "default": "created",
                    "enum": ["created", "updated", "comments"],
                },
                "order": {
                    "type": "string",
                    "description": "Sort order: 'asc' or 'desc'. Default: 'desc'.",
                    "default": "desc",
                    "enum": ["asc", "desc"],
                },
                "per_page": {
                    "type": "integer",
                    "description": "Results per page (1-100). Default: 30.",
                    "default": 30,
                    "minimum": 1,
                    "maximum": 100,
                },
                "page": {
                    "type": "integer",
                    "description": "Page number. Default: 1.",
                    "default": 1,
                    "minimum": 1,
                },
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="github_get_current_user",
        description="Get information about the currently authenticated GitHub user. Returns login, name, email, and profile URL.",
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
]


# =============================================================================
# Jira MCP Server Handlers
# =============================================================================

@jira_mcp_server.list_tools()
async def list_jira_tools() -> list[Tool]:
    """List available Jira MCP tools."""
    return JIRA_TOOLS


@jira_mcp_server.call_tool()
async def call_jira_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle Jira tool calls from MCP clients."""
    try:
        jira_client = get_jira_client()
        result = await _execute_jira_tool(name, arguments, jira_client)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    except JiraClientError as e:
        error_response = {
            "error": True,
            "message": e.message,
            "status_code": e.status_code,
        }
        return [TextContent(type="text", text=json.dumps(error_response, indent=2))]
    except Exception as e:
        logger.exception(f"Error executing Jira tool {name}")
        error_response = {
            "error": True,
            "message": str(e),
        }
        return [TextContent(type="text", text=json.dumps(error_response, indent=2))]


# =============================================================================
# GitHub MCP Server Handlers
# =============================================================================

@github_mcp_server.list_tools()
async def list_github_tools() -> list[Tool]:
    """List available GitHub MCP tools."""
    return GITHUB_TOOLS


@github_mcp_server.call_tool()
async def call_github_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle GitHub tool calls from MCP clients."""
    try:
        github_client = get_github_client()
        result = await _execute_github_tool(name, arguments, github_client)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    except GitHubClientError as e:
        error_response = {
            "error": True,
            "message": e.message,
            "status_code": e.status_code,
        }
        return [TextContent(type="text", text=json.dumps(error_response, indent=2))]
    except Exception as e:
        logger.exception(f"Error executing GitHub tool {name}")
        error_response = {
            "error": True,
            "message": str(e),
        }
        return [TextContent(type="text", text=json.dumps(error_response, indent=2))]


# =============================================================================
# Tool Execution
# =============================================================================

async def _execute_jira_tool(
    name: str, arguments: dict[str, Any], jira_client: JiraClient
) -> dict[str, Any] | list[dict[str, Any]]:
    """Execute a Jira tool and return the result."""

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
        user_info = jira_client.get_current_user()
        username = user_info.get("username", "unknown")
        
        action_details = None
        if input_data.action_details:
            try:
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
        user_info = jira_client.get_current_user()
        username = user_info.get("username", "unknown")
        
        return report_tools.get_weekly_activity(
            username=username,
            week_offset=input_data.week_offset,
            project=input_data.project,
        )

    elif name == "generate_weekly_report":
        input_data = GenerateWeeklyReportInput(**arguments)
        user_info = jira_client.get_current_user()
        username = user_info.get("username", "unknown")
        
        return report_tools.generate_weekly_report(
            username=username,
            week_offset=input_data.week_offset,
            include_details=input_data.include_details,
        )

    elif name == "save_weekly_report":
        input_data = SaveWeeklyReportInput(**arguments)
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
        raise ValueError(f"Unknown Jira tool: {name}")


async def _execute_github_tool(
    name: str, arguments: dict[str, Any], github_client: GitHubClient
) -> dict[str, Any] | list[dict[str, Any]] | str:
    """Execute a GitHub tool and return the result."""

    if name == "github_list_prs":
        input_data = GitHubListPRsInput(**arguments)
        return github_client.list_pull_requests(
            owner=input_data.owner,
            repo=input_data.repo,
            state=input_data.state,
            head=input_data.head,
            base=input_data.base,
            sort=input_data.sort,
            direction=input_data.direction,
            per_page=input_data.per_page,
            page=input_data.page,
        )

    elif name == "github_get_pr":
        input_data = GitHubGetPRInput(**arguments)
        return github_client.get_pull_request(
            owner=input_data.owner,
            repo=input_data.repo,
            pr_number=input_data.pr_number,
        )

    elif name == "github_get_pr_diff":
        input_data = GitHubGetPRDiffInput(**arguments)
        return github_client.get_pull_request_diff(
            owner=input_data.owner,
            repo=input_data.repo,
            pr_number=input_data.pr_number,
        )

    elif name == "github_get_pr_files":
        input_data = GitHubGetPRFilesInput(**arguments)
        return github_client.get_pull_request_files(
            owner=input_data.owner,
            repo=input_data.repo,
            pr_number=input_data.pr_number,
            per_page=input_data.per_page,
            page=input_data.page,
        )

    elif name == "github_get_pr_commits":
        input_data = GitHubGetPRCommitsInput(**arguments)
        return github_client.get_pull_request_commits(
            owner=input_data.owner,
            repo=input_data.repo,
            pr_number=input_data.pr_number,
            per_page=input_data.per_page,
            page=input_data.page,
        )

    elif name == "github_get_pr_reviews":
        input_data = GitHubGetPRReviewsInput(**arguments)
        return github_client.get_pull_request_reviews(
            owner=input_data.owner,
            repo=input_data.repo,
            pr_number=input_data.pr_number,
            per_page=input_data.per_page,
            page=input_data.page,
        )

    elif name == "github_get_pr_comments":
        input_data = GitHubGetPRCommentsInput(**arguments)
        return github_client.get_pull_request_comments(
            owner=input_data.owner,
            repo=input_data.repo,
            pr_number=input_data.pr_number,
            per_page=input_data.per_page,
            page=input_data.page,
        )

    elif name == "github_add_pr_comment":
        input_data = GitHubAddPRCommentInput(**arguments)
        if input_data.in_reply_to is not None:
            return github_client.reply_pull_request_comment(
                owner=input_data.owner,
                repo=input_data.repo,
                pr_number=input_data.pr_number,
                comment_id=input_data.in_reply_to,
                body=input_data.body,
            )
        return github_client.add_pull_request_comment(
            owner=input_data.owner,
            repo=input_data.repo,
            pr_number=input_data.pr_number,
            body=input_data.body,
        )

    elif name == "github_search_prs":
        input_data = GitHubSearchPRsInput(**arguments)
        return github_client.search_pull_requests(
            query=input_data.query,
            sort=input_data.sort,
            order=input_data.order,
            per_page=input_data.per_page,
            page=input_data.page,
        )

    elif name == "github_get_current_user":
        return github_client.get_current_user()

    else:
        raise ValueError(f"Unknown GitHub tool: {name}")


# =============================================================================
# SSE Transport
# =============================================================================

async def run_sse(host: str, port: int) -> None:
    """Run the MCP server with SSE transport (HTTP server mode)."""
    import uvicorn
    from mcp.server.sse import SseServerTransport
    from starlette.applications import Starlette
    from starlette.requests import Request
    from starlette.responses import JSONResponse, Response
    from starlette.routing import Mount, Route
    from starlette.types import Receive, Scope, Send

    logger.info(f"Starting MCP server with SSE transport on {host}:{port}")
    logger.info("Endpoints: /jira (Jira tools), /github (GitHub tools)")

    # Separate SSE transports for each server
    jira_sse_transport = SseServerTransport("/jira/messages/")
    github_sse_transport = SseServerTransport("/github/messages/")

    async def health_check(request: Request) -> JSONResponse:
        """Health check endpoint."""
        return JSONResponse({
            "status": "healthy",
            "endpoints": {
                "jira": "/jira",
                "github": "/github",
            }
        })

    def extract_headers(scope: Scope) -> dict[str, str]:
        """Extract headers from ASGI scope as string dict."""
        headers = {}
        for key, value in scope.get("headers", []):
            key_str = key.decode("utf-8").lower() if isinstance(key, bytes) else key.lower()
            value_str = value.decode("utf-8") if isinstance(value, bytes) else value
            headers[key_str] = value_str
        return headers

    async def handle_jira_sse_raw(scope: Scope, receive: Receive, send: Send) -> None:
        """Handle Jira SSE connection."""
        headers = extract_headers(scope)
        
        # Extract Jira configuration from headers
        server_url = headers.get("x-jira-server-url")
        token = headers.get("x-jira-token")
        verify_ssl_str = headers.get("x-jira-verify-ssl", "true")
        verify_ssl = verify_ssl_str.lower() in ("true", "1", "yes")
        
        # Create and set Jira client
        try:
            client = create_jira_client(
                server_url=server_url,
                token=token,
                verify_ssl=verify_ssl,
            )
            _jira_client_ctx.set(client)
            logger.info(f"Jira SSE connection: {client.server_url}")
        except ValueError as e:
            logger.warning(f"Jira client config error: {e}")
        
        async with jira_sse_transport.connect_sse(scope, receive, send) as streams:
            await jira_mcp_server.run(
                streams[0],
                streams[1],
                jira_mcp_server.create_initialization_options(),
            )

    async def handle_github_sse_raw(scope: Scope, receive: Receive, send: Send) -> None:
        """Handle GitHub SSE connection."""
        headers = extract_headers(scope)
        
        # Extract GitHub configuration from headers
        token = headers.get("x-github-token")
        api_url = headers.get("x-github-api-url")
        
        # Create and set GitHub client
        try:
            client = create_github_client(
                token=token,
                api_url=api_url,
            )
            _github_client_ctx.set(client)
            logger.info(f"GitHub SSE connection: {client.api_url}")
        except ValueError as e:
            logger.warning(f"GitHub client config error: {e}")
        
        async with github_sse_transport.connect_sse(scope, receive, send) as streams:
            await github_mcp_server.run(
                streams[0],
                streams[1],
                github_mcp_server.create_initialization_options(),
            )

    async def handle_jira_sse(request: Request) -> Response:
        """Handle Jira SSE connection - Starlette wrapper."""
        await handle_jira_sse_raw(request.scope, request.receive, request._send)
        return Response()

    async def handle_github_sse(request: Request) -> Response:
        """Handle GitHub SSE connection - Starlette wrapper."""
        await handle_github_sse_raw(request.scope, request.receive, request._send)
        return Response()

    # Create Starlette app with separate routes for Jira and GitHub
    app = Starlette(
        debug=False,
        routes=[
            Route("/health", endpoint=health_check, methods=["GET"]),
            # Jira endpoints
            Route("/jira", endpoint=handle_jira_sse, methods=["GET"]),
            Mount("/jira/messages/", app=jira_sse_transport.handle_post_message),
            # GitHub endpoints
            Route("/github", endpoint=handle_github_sse, methods=["GET"]),
            Mount("/github/messages/", app=github_sse_transport.handle_post_message),
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
        description="Jira/GitHub MCP Server - Model Context Protocol server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Endpoints:
  /jira     Jira tools (tickets, comments, reports)
  /github   GitHub tools (PRs, reviews, comments)

Jira Headers:
  X-Jira-Server-URL    Jira server URL (required)
  X-Jira-Token         Personal Access Token (required)
  X-Jira-Verify-SSL    Verify SSL (default: true)

GitHub Headers:
  X-GitHub-Token       Personal Access Token (required)
  X-GitHub-API-URL     API URL for Enterprise (optional)

Example:
  jira-mcp --host 0.0.0.0 --port 8080
        """,
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host address (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port (default: 8080)",
    )

    args = parser.parse_args()
    asyncio.run(run_sse(args.host, args.port))


if __name__ == "__main__":
    main()
