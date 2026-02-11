"""MCP Server for Jira and GitHub with separate SSE endpoints."""

import argparse
import asyncio
import hashlib
import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime
from typing import Any

from mcp.server import Server
from mcp.types import Resource, ResourceContents, TextContent, TextResourceContents, Tool

from ghost.config import get_management_report_instructions
from ghost.db import PersonalAccessToken, User, get_db, init_db
from ghost.github_client import GitHubClient, GitHubClientError
from ghost.jira_client import JiraClient, JiraClientError

# Import activity tracking and report functions
from ghost.tools import reports as report_tools
from ghost.tools.schemas import (
    AddCommentInput,
    CreateSubtaskInput,
    CreateTicketInput,
    DeleteCommentInput,
    DeleteManagementReportInput,
    DeleteSavedReportInput,
    GenerateWeeklyReportInput,
    GetCommentsInput,
    GetManagementReportInput,
    GetSavedReportInput,
    GetTicketInput,
    GetTransitionsInput,
    GetWeeklyActivityInput,
    # GitHub Pull Requests
    GitHubAddPRCommentInput,
    GitHubGetPRCommentsInput,
    GitHubGetPRCommitsInput,
    GitHubGetPRDiffInput,
    GitHubGetPRFilesInput,
    GitHubGetPRInput,
    GitHubGetPRReviewsInput,
    GitHubListPRsInput,
    GitHubSearchPRsInput,
    # GitHub PR Reviews
    GitHubAddPRReviewCommentInput,
    GitHubCreatePRReviewInput,
    GitHubDismissPRReviewInput,
    GitHubRemoveRequestedReviewersInput,
    GitHubRequestReviewersInput,
    # GitHub Issues
    GitHubAddIssueCommentInput,
    GitHubCloseIssueInput,
    GitHubCreateIssueInput,
    GitHubGetIssueCommentsInput,
    GitHubGetIssueInput,
    GitHubListIssuesInput,
    GitHubReopenIssueInput,
    GitHubSearchIssuesInput,
    GitHubUpdateIssueInput,
    # Jira
    LinkIssuesInput,
    ListComponentsInput,
    ListIssueTypesInput,
    ListManagementReportsInput,
    ListSavedReportsInput,
    ListStatusesInput,
    ListTicketsInput,
    # Activity & Reports
    LogActivityInput,
    # Management Reports
    SaveManagementReportInput,
    SaveWeeklyReportInput,
    SetEpicInput,
    UpdateCommentInput,
    UpdateManagementReportInput,
    UpdateTicketInput,
)

# Configure logging
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger(__name__)

# Create separate MCP Servers for Jira, GitHub, and Reports
ghost_server = Server("ghost")
github_mcp_server = Server("github-mcp")
reports_mcp_server = Server("reports-mcp")

# Context variables for per-connection clients (SSE mode)
_jira_client_ctx: ContextVar[JiraClient | None] = ContextVar("jira_client", default=None)
_github_client_ctx: ContextVar[GitHubClient | None] = ContextVar("github_client", default=None)
_username_ctx: ContextVar[str | None] = ContextVar("username", default=None)
_reports_jira_client_ctx: ContextVar[JiraClient | None] = ContextVar("reports_jira_client", default=None)


def create_jira_client(
    server_url: str | None = None,
    token: str | None = None,
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
        raise ValueError(
            "Jira client not configured. Ensure X-Jira-Server-URL and X-Jira-Token headers are set."
        )
    return client


def create_github_client(
    token: str | None = None,
    api_url: str | None = None,
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


def get_username() -> str:
    """Get username from context for reports endpoint."""
    username = _username_ctx.get()
    if username is None:
        raise ValueError("Username not configured. Ensure X-Username header is set.")
    return username


def get_reports_jira_client() -> JiraClient | None:
    """Get optional Jira client from reports context for auto-fetching ticket details."""
    return _reports_jira_client_ctx.get()


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
    # --- GitHub PR Review Tools ---
    Tool(
        name="github_create_pr_review",
        description="Create a review on a pull request. Use 'APPROVE' to approve, 'REQUEST_CHANGES' to request changes (body required), or 'COMMENT' to leave a review comment without approval/rejection. Can include inline comments on specific files and lines.",
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
                "event": {
                    "type": "string",
                    "description": "Review action: 'APPROVE', 'REQUEST_CHANGES', or 'COMMENT'.",
                    "enum": ["APPROVE", "REQUEST_CHANGES", "COMMENT"],
                },
                "body": {
                    "type": "string",
                    "description": "Review body/summary (Markdown). Required for REQUEST_CHANGES.",
                },
                "comments": {
                    "type": "array",
                    "description": "Optional inline comments to include. Each comment needs: path, line, body. Optional: side ('LEFT'/'RIGHT'), start_line.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Relative path to the file.",
                            },
                            "line": {
                                "type": "integer",
                                "description": "Line number in the diff.",
                            },
                            "body": {
                                "type": "string",
                                "description": "Comment body (Markdown).",
                            },
                            "side": {
                                "type": "string",
                                "description": "Side of diff: 'LEFT' (deletions) or 'RIGHT' (additions). Default: 'RIGHT'.",
                                "enum": ["LEFT", "RIGHT"],
                                "default": "RIGHT",
                            },
                            "start_line": {
                                "type": "integer",
                                "description": "For multi-line comments, the first line.",
                            },
                        },
                        "required": ["path", "line", "body"],
                    },
                },
                "commit_id": {
                    "type": "string",
                    "description": "Optional SHA of commit to review. Defaults to PR head.",
                },
            },
            "required": ["owner", "repo", "pr_number", "event"],
        },
    ),
    Tool(
        name="github_add_pr_review_comment",
        description="Add an inline review comment on a specific file and line in a PR diff. Requires the commit SHA from the PR head (use github_get_pr to get it).",
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
                "commit_id": {
                    "type": "string",
                    "description": "SHA of the commit to comment on (use head.sha from github_get_pr).",
                },
                "path": {
                    "type": "string",
                    "description": "Relative path to the file being commented on.",
                },
                "line": {
                    "type": "integer",
                    "description": "Line number in the diff to comment on.",
                },
                "side": {
                    "type": "string",
                    "description": "Which side of the diff: 'LEFT' (deletions) or 'RIGHT' (additions). Default: 'RIGHT'.",
                    "enum": ["LEFT", "RIGHT"],
                    "default": "RIGHT",
                },
                "start_line": {
                    "type": "integer",
                    "description": "For multi-line comments, the first line of the range.",
                },
                "start_side": {
                    "type": "string",
                    "description": "For multi-line comments, the side of the start line.",
                    "enum": ["LEFT", "RIGHT"],
                },
            },
            "required": ["owner", "repo", "pr_number", "body", "commit_id", "path", "line"],
        },
    ),
    Tool(
        name="github_request_reviewers",
        description="Request specific users or teams to review a pull request. At least one of reviewers or team_reviewers must be provided.",
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
                "reviewers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of usernames to request as reviewers.",
                },
                "team_reviewers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of team slugs to request as reviewers.",
                },
            },
            "required": ["owner", "repo", "pr_number"],
        },
    ),
    Tool(
        name="github_remove_requested_reviewers",
        description="Remove pending reviewer requests from a pull request. Does not affect reviews already submitted.",
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
                "reviewers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of usernames to remove from reviewers.",
                },
                "team_reviewers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of team slugs to remove from reviewers.",
                },
            },
            "required": ["owner", "repo", "pr_number"],
        },
    ),
    Tool(
        name="github_dismiss_pr_review",
        description="Dismiss a submitted pull request review. Requires write access to the repository. Use github_get_pr_reviews to find the review_id.",
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
                "review_id": {
                    "type": "integer",
                    "description": "The review ID to dismiss (get from github_get_pr_reviews).",
                },
                "message": {
                    "type": "string",
                    "description": "Reason for dismissing the review.",
                },
            },
            "required": ["owner", "repo", "pr_number", "review_id", "message"],
        },
    ),
    # --- GitHub Issues Tools ---
    Tool(
        name="github_list_issues",
        description="List issues for a GitHub repository. Returns issue summaries including number, title, state, assignees, and labels. Excludes pull requests.",
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
                "labels": {
                    "type": "string",
                    "description": "Comma-separated list of label names to filter by.",
                },
                "assignee": {
                    "type": "string",
                    "description": "Filter by assignee username. Use '*' for any, 'none' for unassigned.",
                },
                "creator": {
                    "type": "string",
                    "description": "Filter by creator username.",
                },
                "milestone": {
                    "type": "string",
                    "description": "Filter by milestone number, '*' for any, or 'none' for no milestone.",
                },
                "sort": {
                    "type": "string",
                    "description": "Sort by: 'created', 'updated', 'comments'. Default: 'created'.",
                    "default": "created",
                    "enum": ["created", "updated", "comments"],
                },
                "direction": {
                    "type": "string",
                    "description": "Sort direction: 'asc' or 'desc'. Default: 'desc'.",
                    "default": "desc",
                    "enum": ["asc", "desc"],
                },
                "since": {
                    "type": "string",
                    "description": "Only issues updated after this ISO 8601 timestamp.",
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
        name="github_get_issue",
        description="Get full details of a specific GitHub issue including body, milestone, reactions, and state reason.",
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
                "issue_number": {
                    "type": "integer",
                    "description": "Issue number.",
                },
            },
            "required": ["owner", "repo", "issue_number"],
        },
    ),
    Tool(
        name="github_create_issue",
        description="Create a new GitHub issue. Returns the created issue with its number and URL. Use this to document work that was done without a ticket.",
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
                "title": {
                    "type": "string",
                    "description": "Issue title.",
                },
                "body": {
                    "type": "string",
                    "description": "Issue body (Markdown).",
                },
                "assignees": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of usernames to assign.",
                },
                "labels": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of label names.",
                },
                "milestone": {
                    "type": "integer",
                    "description": "Milestone number to associate.",
                },
            },
            "required": ["owner", "repo", "title"],
        },
    ),
    Tool(
        name="github_update_issue",
        description="Update an existing GitHub issue. Can change title, body, state, assignees, labels, and milestone.",
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
                "issue_number": {
                    "type": "integer",
                    "description": "Issue number.",
                },
                "title": {
                    "type": "string",
                    "description": "New issue title.",
                },
                "body": {
                    "type": "string",
                    "description": "New issue body (Markdown).",
                },
                "state": {
                    "type": "string",
                    "description": "New state: 'open' or 'closed'.",
                    "enum": ["open", "closed"],
                },
                "assignees": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "New list of assignees (replaces existing).",
                },
                "labels": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "New list of labels (replaces existing).",
                },
                "milestone": {
                    "type": "integer",
                    "description": "New milestone number (use 0 to clear).",
                },
            },
            "required": ["owner", "repo", "issue_number"],
        },
    ),
    Tool(
        name="github_close_issue",
        description="Close a GitHub issue with optional reason.",
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
                "issue_number": {
                    "type": "integer",
                    "description": "Issue number.",
                },
                "state_reason": {
                    "type": "string",
                    "description": "Reason for closing: 'completed' or 'not_planned'.",
                    "enum": ["completed", "not_planned"],
                },
            },
            "required": ["owner", "repo", "issue_number"],
        },
    ),
    Tool(
        name="github_reopen_issue",
        description="Reopen a closed GitHub issue.",
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
                "issue_number": {
                    "type": "integer",
                    "description": "Issue number.",
                },
            },
            "required": ["owner", "repo", "issue_number"],
        },
    ),
    Tool(
        name="github_get_issue_comments",
        description="Get comments on a GitHub issue.",
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
                "issue_number": {
                    "type": "integer",
                    "description": "Issue number.",
                },
                "since": {
                    "type": "string",
                    "description": "Only comments updated after this ISO 8601 timestamp.",
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
            "required": ["owner", "repo", "issue_number"],
        },
    ),
    Tool(
        name="github_add_issue_comment",
        description="Add a comment to a GitHub issue.",
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
                "issue_number": {
                    "type": "integer",
                    "description": "Issue number.",
                },
                "body": {
                    "type": "string",
                    "description": "Comment body (Markdown).",
                },
            },
            "required": ["owner", "repo", "issue_number", "body"],
        },
    ),
    Tool(
        name="github_search_issues",
        description="Search for issues across GitHub repositories. Use GitHub search qualifiers like 'author:username', 'repo:owner/repo', 'state:open', 'label:bug'. Returns issue_key in 'owner/repo#number' format for activity logging.",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "GitHub search query. Examples: 'author:octocat', 'repo:facebook/react state:open', 'org:microsoft label:bug'. 'is:issue' is added automatically.",
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
]


# =============================================================================
# Reports Tools (Activity Tracking & Reporting)
# =============================================================================

REPORTS_TOOLS: list[Tool] = [
    # --- Instructions & Configuration ---
    Tool(
        name="get_report_instructions",
        description="Get the instructions and guidelines for generating management reports. Call this BEFORE creating a management report to understand the expected format, style, content structure, and templates.",
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
    # --- Activity Tracking & Weekly Reports ---
    Tool(
        name="log_activity",
        description="Log a work activity for weekly report tracking. Supports both Jira tickets (PROJ-123) and GitHub issues (owner/repo#123). Call this when working on tickets to track your work. For Jira tickets, provide jira_components for project detection.",
        inputSchema={
            "type": "object",
            "properties": {
                "ticket_key": {
                    "type": "string",
                    "description": "The ticket key. Jira: 'PROJ-123'. GitHub: 'owner/repo#123' or '#123' (with github_repo).",
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
                "github_repo": {
                    "type": "string",
                    "description": "For GitHub issues: repository in 'owner/repo' format. Required if using short '#123' format.",
                },
                "jira_components": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "For Jira tickets: list of component names for project detection (e.g., ['FSI-Lab']).",
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
        description="""Save a management report. Read instructions at 'reports://instructions/management-report' first.

Supports two formats:
1. Legacy: Plain text content (bullet list)
2. Structured entries: Array of entries with per-item visibility control

When using structured entries, include ticket_key to auto-inherit visibility from activities.
Items from activities marked as private will be automatically hidden from managers.""",
        inputSchema={
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Report title (e.g., 'Week 4, January 2026').",
                },
                "content": {
                    "type": "string",
                    "description": "(Legacy) Bullet list of work items with embedded links. Use 'entries' instead for per-item visibility.",
                },
                "entries": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "text": {
                                "type": "string",
                                "description": "The entry text (work item description with links).",
                            },
                            "private": {
                                "type": "boolean",
                                "description": "If true, this entry is hidden from managers. Default: false.",
                            },
                            "ticket_key": {
                                "type": "string",
                                "description": "Optional ticket key to auto-detect visibility from activity settings.",
                            },
                        },
                        "required": ["text"],
                    },
                    "description": "Structured entries with per-item visibility. If ticket_key is provided, visibility is auto-inherited from activity.",
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
                    "description": "Ticket keys mentioned in report (for indexing).",
                },
            },
            "required": ["title"],
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
        description="Update an existing management report. Supports both legacy content and structured entries with per-item visibility.",
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
                "content": {
                    "type": "string",
                    "description": "(Legacy) Optional new content (bullet list of work items). Use 'entries' for per-item visibility.",
                },
                "entries": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "text": {
                                "type": "string",
                                "description": "The entry text (work item description with links).",
                            },
                            "private": {
                                "type": "boolean",
                                "description": "If true, this entry is hidden from managers. Default: false.",
                            },
                            "ticket_key": {
                                "type": "string",
                                "description": "Optional ticket key to auto-detect visibility from activity settings.",
                            },
                        },
                        "required": ["text"],
                    },
                    "description": "Structured entries with per-item visibility control.",
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
    # --- Project Detection ---
    Tool(
        name="redetect_project_assignments",
        description="Re-run project detection on existing activities. Useful after configuring project mappings (Jira components or GitHub repos) to update historical activities. Auto-fetches Jira components if missing.",
        inputSchema={
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of activities to process. Default: 100.",
                    "default": 100,
                    "minimum": 1,
                    "maximum": 1000,
                },
            },
        },
    ),
    Tool(
        name="list_report_fields",
        description="List all report fields and their projects with configured Jira components and GitHub repos. Use this to see the current project detection configuration.",
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
    Tool(
        name="get_activity_details",
        description="Get detailed information about a specific activity by ticket key. Useful for debugging project detection.",
        inputSchema={
            "type": "object",
            "properties": {
                "ticket_key": {
                    "type": "string",
                    "description": "The ticket key to look up (e.g., 'APPENG-4347').",
                },
            },
            "required": ["ticket_key"],
        },
    ),
]


# =============================================================================
# Jira MCP Server Handlers
# =============================================================================


@ghost_server.list_tools()
async def list_jira_tools() -> list[Tool]:
    """List available Jira MCP tools."""
    return JIRA_TOOLS


@ghost_server.call_tool()
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
# Reports MCP Server Handlers
# =============================================================================


@reports_mcp_server.list_tools()
async def list_reports_tools() -> list[Tool]:
    """List available Reports MCP tools."""
    return REPORTS_TOOLS


@reports_mcp_server.call_tool()
async def call_reports_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle Reports tool calls from MCP clients."""
    try:
        username = get_username()
        jira_client = get_reports_jira_client()  # Get Jira client from context (works here)
        result = await _execute_reports_tool(name, arguments, username, jira_client)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    except Exception as e:
        logger.exception(f"Error executing Reports tool {name}")
        error_response = {
            "error": True,
            "message": str(e),
        }
        return [TextContent(type="text", text=json.dumps(error_response, indent=2))]


# =============================================================================
# Reports MCP Resources (Instructions & Templates)
# =============================================================================


@reports_mcp_server.list_resources()
async def list_reports_resources() -> list[Resource]:
    """List available resources for the Reports server."""
    return [
        Resource(
            uri="reports://instructions/management-report",
            name="Management Report Instructions",
            description="Instructions and guidelines for generating management reports. Read this before creating a management report to understand the expected format, style, and content requirements.",
            mimeType="text/markdown",
        ),
    ]


@reports_mcp_server.read_resource()
async def read_reports_resource(uri: str) -> ResourceContents:
    """Read a resource by URI."""
    if uri == "reports://instructions/management-report":
        instructions = get_management_report_instructions()
        return [
            TextResourceContents(
                uri=uri,
                mimeType="text/markdown",
                text=instructions,
            )
        ]

    raise ValueError(f"Unknown resource URI: {uri}")


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

    # --- GitHub PR Review Tools ---

    elif name == "github_create_pr_review":
        input_data = GitHubCreatePRReviewInput(**arguments)
        # Convert Pydantic comment models to dicts for the client
        comments = None
        if input_data.comments:
            comments = [
                {
                    "path": c.path,
                    "line": c.line,
                    "body": c.body,
                    "side": c.side,
                    **({"start_line": c.start_line} if c.start_line else {}),
                }
                for c in input_data.comments
            ]
        return github_client.create_pull_request_review(
            owner=input_data.owner,
            repo=input_data.repo,
            pr_number=input_data.pr_number,
            event=input_data.event,
            body=input_data.body,
            comments=comments,
            commit_id=input_data.commit_id,
        )

    elif name == "github_add_pr_review_comment":
        input_data = GitHubAddPRReviewCommentInput(**arguments)
        return github_client.add_pull_request_review_comment(
            owner=input_data.owner,
            repo=input_data.repo,
            pr_number=input_data.pr_number,
            body=input_data.body,
            commit_id=input_data.commit_id,
            path=input_data.path,
            line=input_data.line,
            side=input_data.side,
            start_line=input_data.start_line,
            start_side=input_data.start_side,
        )

    elif name == "github_request_reviewers":
        input_data = GitHubRequestReviewersInput(**arguments)
        return github_client.request_reviewers(
            owner=input_data.owner,
            repo=input_data.repo,
            pr_number=input_data.pr_number,
            reviewers=input_data.reviewers,
            team_reviewers=input_data.team_reviewers,
        )

    elif name == "github_remove_requested_reviewers":
        input_data = GitHubRemoveRequestedReviewersInput(**arguments)
        return github_client.remove_requested_reviewers(
            owner=input_data.owner,
            repo=input_data.repo,
            pr_number=input_data.pr_number,
            reviewers=input_data.reviewers,
            team_reviewers=input_data.team_reviewers,
        )

    elif name == "github_dismiss_pr_review":
        input_data = GitHubDismissPRReviewInput(**arguments)
        return github_client.dismiss_pull_request_review(
            owner=input_data.owner,
            repo=input_data.repo,
            pr_number=input_data.pr_number,
            review_id=input_data.review_id,
            message=input_data.message,
        )

    # --- GitHub Issues Tools ---

    elif name == "github_list_issues":
        input_data = GitHubListIssuesInput(**arguments)
        return github_client.list_issues(
            owner=input_data.owner,
            repo=input_data.repo,
            state=input_data.state,
            labels=input_data.labels,
            assignee=input_data.assignee,
            creator=input_data.creator,
            milestone=input_data.milestone,
            sort=input_data.sort,
            direction=input_data.direction,
            since=input_data.since,
            per_page=input_data.per_page,
            page=input_data.page,
        )

    elif name == "github_get_issue":
        input_data = GitHubGetIssueInput(**arguments)
        return github_client.get_issue(
            owner=input_data.owner,
            repo=input_data.repo,
            issue_number=input_data.issue_number,
        )

    elif name == "github_create_issue":
        input_data = GitHubCreateIssueInput(**arguments)
        return github_client.create_issue(
            owner=input_data.owner,
            repo=input_data.repo,
            title=input_data.title,
            body=input_data.body,
            assignees=input_data.assignees,
            labels=input_data.labels,
            milestone=input_data.milestone,
        )

    elif name == "github_update_issue":
        input_data = GitHubUpdateIssueInput(**arguments)
        return github_client.update_issue(
            owner=input_data.owner,
            repo=input_data.repo,
            issue_number=input_data.issue_number,
            title=input_data.title,
            body=input_data.body,
            state=input_data.state,
            assignees=input_data.assignees,
            labels=input_data.labels,
            milestone=input_data.milestone,
        )

    elif name == "github_close_issue":
        input_data = GitHubCloseIssueInput(**arguments)
        return github_client.close_issue(
            owner=input_data.owner,
            repo=input_data.repo,
            issue_number=input_data.issue_number,
            state_reason=input_data.state_reason,
        )

    elif name == "github_reopen_issue":
        input_data = GitHubReopenIssueInput(**arguments)
        return github_client.reopen_issue(
            owner=input_data.owner,
            repo=input_data.repo,
            issue_number=input_data.issue_number,
        )

    elif name == "github_get_issue_comments":
        input_data = GitHubGetIssueCommentsInput(**arguments)
        return github_client.get_issue_comments(
            owner=input_data.owner,
            repo=input_data.repo,
            issue_number=input_data.issue_number,
            since=input_data.since,
            per_page=input_data.per_page,
            page=input_data.page,
        )

    elif name == "github_add_issue_comment":
        input_data = GitHubAddIssueCommentInput(**arguments)
        return github_client.add_issue_comment(
            owner=input_data.owner,
            repo=input_data.repo,
            issue_number=input_data.issue_number,
            body=input_data.body,
        )

    elif name == "github_search_issues":
        input_data = GitHubSearchIssuesInput(**arguments)
        return github_client.search_issues(
            query=input_data.query,
            sort=input_data.sort,
            order=input_data.order,
            per_page=input_data.per_page,
            page=input_data.page,
        )

    else:
        raise ValueError(f"Unknown GitHub tool: {name}")


async def _execute_reports_tool(
    name: str, arguments: dict[str, Any], username: str, jira_client: JiraClient | None = None
) -> dict[str, Any] | list[dict[str, Any]]:
    """Execute a Reports tool and return the result."""

    # --- Instructions & Configuration ---

    if name == "get_report_instructions":
        instructions = get_management_report_instructions()
        return {
            "instructions": instructions,
            "note": "Follow these guidelines when generating management reports using the save_management_report tool.",
        }

    # --- Activity Tracking & Weekly Reports ---

    elif name == "log_activity":
        input_data = LogActivityInput(**arguments)

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
            github_repo=input_data.github_repo,
            action_details=action_details,
            jira_client=jira_client,
        )

    elif name == "get_weekly_activity":
        input_data = GetWeeklyActivityInput(**arguments)
        return report_tools.get_weekly_activity(
            username=username,
            week_offset=input_data.week_offset,
            project=input_data.project,
        )

    elif name == "generate_weekly_report":
        input_data = GenerateWeeklyReportInput(**arguments)
        return report_tools.generate_weekly_report(
            username=username,
            week_offset=input_data.week_offset,
            include_details=input_data.include_details,
        )

    elif name == "save_weekly_report":
        input_data = SaveWeeklyReportInput(**arguments)
        return report_tools.save_weekly_report(
            username=username,
            week_offset=input_data.week_offset,
            custom_title=input_data.custom_title,
            custom_summary=input_data.custom_summary,
        )

    elif name == "list_saved_reports":
        input_data = ListSavedReportsInput(**arguments)
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
        # Convert Pydantic entries to dicts for the tool function
        entries = None
        if input_data.entries is not None:
            entries = [
                {"text": e.text, "private": e.private, "ticket_key": e.ticket_key}
                for e in input_data.entries
            ]
        return report_tools.save_management_report(
            username=username,
            title=input_data.title,
            content=input_data.content,
            entries=entries,
            project_key=input_data.project_key,
            report_period=input_data.report_period,
            referenced_tickets=input_data.referenced_tickets,
        )

    elif name == "list_management_reports":
        input_data = ListManagementReportsInput(**arguments)
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
        # Convert Pydantic entries to dicts for the tool function
        entries = None
        if input_data.entries is not None:
            entries = [
                {"text": e.text, "private": e.private, "ticket_key": e.ticket_key}
                for e in input_data.entries
            ]
        return report_tools.update_management_report(
            report_id=input_data.report_id,
            title=input_data.title,
            content=input_data.content,
            entries=entries,
            report_period=input_data.report_period,
            referenced_tickets=input_data.referenced_tickets,
        )

    elif name == "delete_management_report":
        input_data = DeleteManagementReportInput(**arguments)
        return report_tools.delete_management_report(
            report_id=input_data.report_id,
        )

    elif name == "redetect_project_assignments":
        limit = arguments.get("limit", 100)
        return report_tools.redetect_project_assignments(
            username=username,
            limit=limit,
            jira_client=jira_client,
        )

    elif name == "list_report_fields":
        return report_tools.list_report_fields()

    elif name == "get_activity_details":
        ticket_key = arguments.get("ticket_key")
        return report_tools.get_activity_details(username=username, ticket_key=ticket_key)

    else:
        raise ValueError(f"Unknown Reports tool: {name}")


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
    logger.info(
        "Endpoints: /mcp/jira (Jira tools), /mcp/github (GitHub tools), /mcp/reports (Activity & Reports)"
    )

    # Separate SSE transports for each server (using /mcp/ prefix for nginx proxy)
    jira_sse_transport = SseServerTransport("/mcp/jira/messages/")
    github_sse_transport = SseServerTransport("/mcp/github/messages/")
    reports_sse_transport = SseServerTransport("/mcp/reports/messages/")

    async def health_check(request: Request) -> JSONResponse:
        """Health check endpoint."""
        return JSONResponse(
            {
                "status": "healthy",
                "endpoints": {
                    "jira": "/mcp/jira",
                    "github": "/mcp/github",
                    "reports": "/mcp/reports",
                },
            }
        )

    def extract_headers(scope: Scope) -> dict[str, str]:
        """Extract headers from ASGI scope as string dict."""
        headers = {}
        for key, value in scope.get("headers", []):
            key_str = key.decode("utf-8").lower() if isinstance(key, bytes) else key.lower()
            value_str = value.decode("utf-8") if isinstance(value, bytes) else value
            headers[key_str] = value_str
        return headers

    def authenticate_via_pat(headers: dict[str, str]) -> str | None:
        """Authenticate a request using a Personal Access Token.

        Checks the Authorization header for a Bearer token, hashes it,
        looks it up in the database, and returns the user's email if valid.

        Returns:
            The user's email if authentication succeeds, None otherwise.
        """
        auth_header = headers.get("authorization", "")
        if not auth_header.lower().startswith("bearer "):
            return None

        raw_token = auth_header[7:].strip()  # Strip "Bearer " prefix
        if not raw_token:
            return None

        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

        try:
            db = get_db()
            with db.session() as session:
                pat = (
                    session.query(PersonalAccessToken)
                    .filter(
                        PersonalAccessToken.token_hash == token_hash,
                        PersonalAccessToken.is_revoked == False,  # noqa: E712
                    )
                    .first()
                )

                if not pat:
                    logger.warning("PAT authentication failed: token not found or revoked")
                    return None

                # Check expiry
                if pat.expires_at and pat.expires_at <= datetime.utcnow():
                    logger.warning(f"PAT authentication failed: token expired (id={pat.id})")
                    return None

                # Get user email
                user = session.query(User).filter(User.id == pat.user_id).first()
                if not user:
                    logger.warning(f"PAT authentication failed: user not found (user_id={pat.user_id})")
                    return None

                # Update last_used_at
                pat.last_used_at = datetime.utcnow()
                session.flush()

                logger.info(f"PAT authentication successful: user={user.email} (pat_id={pat.id})")
                return user.email
        except Exception as e:
            logger.error(f"PAT authentication error: {e}")
            return None

    async def send_unauthorized(send: Send, detail: str = "Authentication required") -> None:
        """Send a 401 Unauthorized HTTP response via ASGI."""
        import json as _json
        body = _json.dumps({"error": detail}).encode("utf-8")
        await send({
            "type": "http.response.start",
            "status": 401,
            "headers": [
                [b"content-type", b"application/json"],
                [b"content-length", str(len(body)).encode("utf-8")],
            ],
        })
        await send({
            "type": "http.response.body",
            "body": body,
        })

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
            await ghost_server.run(
                streams[0],
                streams[1],
                ghost_server.create_initialization_options(),
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

    async def handle_reports_sse_raw(scope: Scope, receive: Receive, send: Send) -> None:
        """Handle Reports SSE connection."""
        headers = extract_headers(scope)

        # Authenticate the request
        # Priority 1: Personal Access Token (Bearer token)
        username = authenticate_via_pat(headers)

        # Priority 2: OAuth proxy headers (X-Forwarded-Email > X-Forwarded-User > X-Username)
        if not username:
            username = (
                headers.get("x-forwarded-email") or 
                headers.get("x-forwarded-user") or 
                headers.get("x-username")
            )

        # Reject unauthenticated connections
        if not username:
            logger.warning("Reports SSE connection rejected: no valid authentication")
            await send_unauthorized(send, "Authentication required. Provide a Bearer token or valid proxy headers.")
            return

        _username_ctx.set(username)
        logger.info(f"Reports SSE connection: user={username}")

        # Extract optional Jira configuration from headers for auto-fetching ticket details
        jira_server_url = headers.get("x-jira-server-url")
        jira_token = headers.get("x-jira-token")
        jira_verify_ssl_str = headers.get("x-jira-verify-ssl", "true")
        jira_verify_ssl = jira_verify_ssl_str.lower() in ("true", "1", "yes")

        if jira_server_url and jira_token:
            try:
                jira_client = JiraClient(
                    server_url=jira_server_url,
                    token=jira_token,
                    verify_ssl=jira_verify_ssl,
                )
                _reports_jira_client_ctx.set(jira_client)
                logger.info(f"Reports SSE connection: Jira client configured for {jira_server_url}")
            except Exception as e:
                logger.warning(f"Reports SSE connection: Failed to create Jira client: {e}")

        async with reports_sse_transport.connect_sse(scope, receive, send) as streams:
            await reports_mcp_server.run(
                streams[0],
                streams[1],
                reports_mcp_server.create_initialization_options(),
            )

    async def handle_jira_sse(request: Request) -> Response:
        """Handle Jira SSE connection - Starlette wrapper."""
        await handle_jira_sse_raw(request.scope, request.receive, request._send)
        return Response()

    async def handle_github_sse(request: Request) -> Response:
        """Handle GitHub SSE connection - Starlette wrapper."""
        await handle_github_sse_raw(request.scope, request.receive, request._send)
        return Response()

    async def handle_reports_sse(request: Request) -> Response:
        """Handle Reports SSE connection - Starlette wrapper."""
        await handle_reports_sse_raw(request.scope, request.receive, request._send)
        return Response()

    async def authenticated_reports_messages(scope: Scope, receive: Receive, send: Send) -> None:
        """Wrap reports messages POST with PAT / proxy header auth check."""
        headers = extract_headers(scope)

        # Check PAT first, then proxy headers
        username = authenticate_via_pat(headers)
        if not username:
            username = (
                headers.get("x-forwarded-email") or
                headers.get("x-forwarded-user") or
                headers.get("x-username")
            )

        if not username:
            await send_unauthorized(send, "Authentication required for Reports MCP messages.")
            return

        # Delegate to the real handler
        await reports_sse_transport.handle_post_message(scope, receive, send)

    # Create Starlette app with separate routes for Jira, GitHub, and Reports
    # All MCP routes use /mcp/ prefix to work with nginx proxy
    app = Starlette(
        debug=False,
        routes=[
            Route("/health", endpoint=health_check, methods=["GET"]),
            # Also support /mcp/health for consistency
            Route("/mcp/health", endpoint=health_check, methods=["GET"]),
            # Jira endpoints
            Route("/mcp/jira", endpoint=handle_jira_sse, methods=["GET"]),
            Mount("/mcp/jira/messages/", app=jira_sse_transport.handle_post_message),
            # GitHub endpoints
            Route("/mcp/github", endpoint=handle_github_sse, methods=["GET"]),
            Mount("/mcp/github/messages/", app=github_sse_transport.handle_post_message),
            # Reports endpoints (protected with PAT / proxy auth)
            Route("/mcp/reports", endpoint=handle_reports_sse, methods=["GET"]),
            Mount("/mcp/reports/messages/", app=authenticated_reports_messages),
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
        description="Jira/GitHub/Reports MCP Server - Model Context Protocol server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Endpoints:
  /jira     Jira tools (tickets, comments, metadata)
  /github   GitHub tools (PRs, reviews, comments)
  /reports  Activity logging & reporting tools

Jira Headers:
  X-Jira-Server-URL    Jira server URL (required)
  X-Jira-Token         Personal Access Token (required)
  X-Jira-Verify-SSL    Verify SSL (default: true)

GitHub Headers:
  X-GitHub-Token       Personal Access Token (required)
  X-GitHub-API-URL     API URL for Enterprise (optional)

Reports Headers:
  X-Username           Username for activity tracking (required)

Example:
  ghost --host 0.0.0.0 --port 8080
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
