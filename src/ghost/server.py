"""MCP Server for GitHub and Reports with Streamable HTTP transport."""

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
from mcp.types import (
    GetPromptResult,
    Prompt,
    Resource,
    ResourceContents,
    TextContent,
    TextResourceContents,
    Tool,
)

from ghost.config import get_management_report_instructions
from ghost.db import GitHubTokenConfig, PersonalAccessToken, User, get_db, init_db
from ghost.github_client import GitHubClient, GitHubClientError, GitHubTokenManager
from ghost.prompts import get_prompt as resolve_prompt
from ghost.prompts import list_prompts as get_all_prompts

# Import activity tracking and report functions
from ghost.tools import reports as report_tools
from ghost.tools.schemas import (
    DeleteManagementReportInput,
    GetManagementReportInput,
    GetWeeklyActivityInput,
    # GitHub Pull Requests
    GitHubAddPRCommentInput,
    GitHubCompareBranchesInput,
    GitHubCreatePRInput,
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
    ListManagementReportsInput,
    # Activity & Reports
    LogActivityInput,
    # Management Reports
    SaveManagementReportInput,
    UpdateManagementReportInput,
)

# Configure logging
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger(__name__)

# Create MCP Servers for GitHub and Reports
github_mcp_server = Server("github-mcp")
reports_mcp_server = Server("reports-mcp")

# Context variables for per-request clients (set by auth wrappers before each request)
_github_token_manager_ctx: ContextVar[GitHubTokenManager | None] = ContextVar("github_token_manager", default=None)
_username_ctx: ContextVar[str | None] = ContextVar("username", default=None)


def create_github_token_manager(
    token: str | None = None,
    tokens_json: str | None = None,
    api_url: str | None = None,
) -> GitHubTokenManager:
    """Create a GitHubTokenManager from headers.

    Prefers X-GitHub-Tokens (multi-token JSON) over X-GitHub-Token (single token).

    Args:
        token: Single token from X-GitHub-Token header (backward compat)
        tokens_json: JSON string from X-GitHub-Tokens header (multi-token)
        api_url: Default GitHub API base URL

    Returns:
        Configured GitHubTokenManager
    """
    if tokens_json:
        return GitHubTokenManager.from_header(tokens_json, api_url)
    if token:
        return GitHubTokenManager.from_single_token(token, api_url)
    raise ValueError(
        "GitHub token is required. Set X-GitHub-Token or X-GitHub-Tokens header."
    )


def get_github_token_manager() -> GitHubTokenManager:
    """Get GitHubTokenManager from context."""
    manager = _github_token_manager_ctx.get()
    if manager is None:
        raise ValueError(
            "GitHub tokens not configured. "
            "Ensure X-GitHub-Token or X-GitHub-Tokens header is set."
        )
    return manager


def _extract_named_token_headers(headers: dict[str, str]) -> dict[str, str]:
    """Extract named GitHub token headers (X-GitHub-Token-{name}).

    Scans all headers for the pattern x-github-token-{name} (lowercase),
    excluding the base x-github-token and x-github-tokens headers.

    Returns:
        Dict mapping config name to token value,
        e.g., {"personal": "ghp_abc", "work": "ghp_xyz"}
    """
    prefix = "x-github-token-"
    skip = {"x-github-token", "x-github-tokens"}
    named_tokens = {}
    for key, value in headers.items():
        if key in skip:
            continue
        if key.startswith(prefix) and value:
            name = key[len(prefix):]
            if name:
                named_tokens[name] = value
    return named_tokens


def get_username() -> str:
    """Get username from context for reports endpoint."""
    username = _username_ctx.get()
    if username is None:
        raise ValueError("Username not configured. Ensure X-Username header is set.")
    return username


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
    # --- GitHub PR Create & Compare ---
    Tool(
        name="github_create_pr",
        description="Create a new pull request. Returns the created PR with its number, URL, and full details.",
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
                    "description": "Pull request title.",
                },
                "head": {
                    "type": "string",
                    "description": "The name of the branch where your changes are implemented. For cross-repository PRs use 'username:branch'.",
                },
                "base": {
                    "type": "string",
                    "description": "The name of the branch you want the changes pulled into. Default: 'main'.",
                    "default": "main",
                },
                "body": {
                    "type": "string",
                    "description": "Pull request body/description (Markdown).",
                },
                "draft": {
                    "type": "boolean",
                    "description": "Whether to create the pull request as a draft. Default: false.",
                    "default": False,
                },
                "maintainer_can_modify": {
                    "type": "boolean",
                    "description": "Whether maintainers can modify the pull request. Default: true.",
                    "default": True,
                },
            },
            "required": ["owner", "repo", "title", "head"],
        },
    ),
    Tool(
        name="github_compare_branches",
        description="Compare two branches, tags, or commits. Returns the comparison status (ahead/behind/diverged), list of commits, and files changed. Useful for understanding what changes exist between two refs before creating a PR.",
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
                "base": {
                    "type": "string",
                    "description": "Base branch, tag, or commit SHA.",
                },
                "head": {
                    "type": "string",
                    "description": "Head branch, tag, or commit SHA.",
                },
            },
            "required": ["owner", "repo", "base", "head"],
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
    # --- Token Info ---
    Tool(
        name="github_list_tokens",
        description="List configured GitHub token patterns (without exposing actual tokens). "
        "Shows which repository patterns are mapped to which tokens, useful for "
        "troubleshooting access issues when multiple PATs are configured.",
        inputSchema={
            "type": "object",
            "properties": {},
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
    # --- Activity Tracking ---
    Tool(
        name="log_activity",
        description="Log a work activity for tracking. Supports both Jira tickets (PROJ-123) and GitHub issues (owner/repo#123). Call this when working on tickets to track your work. For Jira tickets, provide jira_components for project detection.",
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
                    "description": "Optional internal metadata. Not displayed to users. Defaults to 'other'.",
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
                "ticket_url": {
                    "type": "string",
                    "description": "Canonical browse URL for the ticket (e.g. from jira_get_issue 'url' field or GitHub issue URL). Stored for reports and UI links.",
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
        description="Get activity summary for a time period. Use 'days' to specify how many days back to look (e.g. 7 for last week).",
        inputSchema={
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "Number of days to look back (e.g. 7 for last week, 14 for last two weeks). Preferred over week_offset.",
                    "minimum": 1,
                    "maximum": 365,
                },
                "week_offset": {
                    "type": "integer",
                    "description": "(Legacy) Week offset from current week (0 = current, -1 = last week). Use 'days' instead.",
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
        token_manager = get_github_token_manager()
        result = await _execute_github_tool(name, arguments, token_manager)
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
        result = await _execute_reports_tool(name, arguments, username)
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
# Reports MCP Prompts (workflow slash-commands)
# =============================================================================


@reports_mcp_server.list_prompts()
async def list_reports_prompts() -> list[Prompt]:
    """List available workflow prompts (show up as /commands in Cursor)."""
    return get_all_prompts()


@reports_mcp_server.get_prompt()
async def get_reports_prompt(name: str, arguments: dict[str, str] | None = None) -> GetPromptResult:
    """Return the content for a specific workflow prompt."""
    return resolve_prompt(name, arguments)


# =============================================================================
# Tool Execution
# =============================================================================


async def _execute_github_tool(
    name: str, arguments: dict[str, Any], token_manager: GitHubTokenManager
) -> dict[str, Any] | list[dict[str, Any]] | str:
    """Execute a GitHub tool and return the result.

    Resolves the correct GitHubClient from the token manager based on the
    owner/repo in the tool arguments. Falls back to the default client for
    tools that don't target a specific repository (search, current_user).
    """
    # Tools that don't target a specific repo use the default client
    non_repo_tools = {"github_search_prs", "github_search_issues", "github_get_current_user",
                      "github_list_tokens"}

    if name in non_repo_tools:
        github_client = token_manager.get_default_client()
    else:
        # Resolve the correct client based on owner/repo from arguments
        owner = arguments.get("owner")
        repo = arguments.get("repo")
        if not owner or not repo:
            raise ValueError(f"Tool '{name}' requires 'owner' and 'repo' arguments")
        github_client = token_manager.get_client(owner, repo)

    if name == "github_list_tokens":
        return token_manager.get_token_info()

    elif name == "github_list_prs":
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

    # --- GitHub PR Create & Compare ---

    elif name == "github_create_pr":
        input_data = GitHubCreatePRInput(**arguments)
        return github_client.create_pull_request(
            owner=input_data.owner,
            repo=input_data.repo,
            title=input_data.title,
            head=input_data.head,
            base=input_data.base,
            body=input_data.body,
            draft=input_data.draft,
            maintainer_can_modify=input_data.maintainer_can_modify,
        )

    elif name == "github_compare_branches":
        input_data = GitHubCompareBranchesInput(**arguments)
        return github_client.compare_branches(
            owner=input_data.owner,
            repo=input_data.repo,
            base=input_data.base,
            head=input_data.head,
        )

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
    name: str, arguments: dict[str, Any], username: str
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
            jira_components=input_data.jira_components,
            ticket_url=input_data.ticket_url,
            action_details=action_details,
        )

    elif name == "get_weekly_activity":
        input_data = GetWeeklyActivityInput(**arguments)
        return report_tools.get_weekly_activity(
            username=username,
            week_offset=input_data.week_offset,
            days=input_data.days,
            project=input_data.project,
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
        )

    elif name == "list_report_fields":
        return report_tools.list_report_fields()

    elif name == "get_activity_details":
        ticket_key = arguments.get("ticket_key")
        return report_tools.get_activity_details(username=username, ticket_key=ticket_key)

    else:
        raise ValueError(f"Unknown Reports tool: {name}")


# =============================================================================
# Streamable HTTP Transport
# =============================================================================


async def run_streamable_http(host: str, port: int) -> None:
    """Run the MCP server with Streamable HTTP transport."""
    import uvicorn
    from contextlib import AsyncExitStack, asynccontextmanager
    from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
    from starlette.applications import Starlette
    from starlette.requests import Request
    from starlette.responses import JSONResponse
    from starlette.routing import Mount, Route
    from starlette.types import Receive, Scope, Send

    logger.info(f"Starting MCP server with Streamable HTTP transport on {host}:{port}")
    logger.info(
        "Endpoints: /mcp/github (GitHub tools), /mcp/reports (Activity & Reports)"
    )

    # Stateless session managers — each request is independent with its own context
    github_session_mgr = StreamableHTTPSessionManager(app=github_mcp_server, stateless=True)
    reports_session_mgr = StreamableHTTPSessionManager(app=reports_mcp_server, stateless=True)

    async def health_check(request: Request) -> JSONResponse:
        """Health check endpoint."""
        return JSONResponse(
            {
                "status": "healthy",
                "transport": "streamable-http",
                "endpoints": {
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

        raw_token = auth_header[7:].strip()
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

                if pat.expires_at and pat.expires_at <= datetime.utcnow():
                    logger.warning(f"PAT authentication failed: token expired (id={pat.id})")
                    return None

                user = session.query(User).filter(User.id == pat.user_id).first()
                if not user:
                    logger.warning(f"PAT authentication failed: user not found (user_id={pat.user_id})")
                    return None

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

    # ── Per-request auth wrappers (ASGI apps) ──────────────────────────────
    # Each wrapper extracts headers, sets up context variables for the user's
    # credentials, then delegates to the session manager. Because Streamable
    # HTTP stateless mode spawns a new async task per request that inherits
    # the current context, tool handlers see the correct per-user values.

    async def github_handler(scope: Scope, receive: Receive, send: Send) -> None:
        """Extract GitHub tokens from headers and dispatch to session manager.

        Token resolution priority:
        1. Named headers (X-GitHub-Token-{name}) with DB-stored patterns (requires Bearer PAT auth)
        2. JSON header (X-GitHub-Tokens) with inline patterns
        3. Single header (X-GitHub-Token) matching all repos
        """
        headers = extract_headers(scope)
        api_url = headers.get("x-github-api-url")
        manager = None

        user_email = authenticate_via_pat(headers)
        if user_email:
            named_tokens = _extract_named_token_headers(headers)
            if named_tokens:
                try:
                    db = get_db()
                    with db.session() as session:
                        user = session.query(User).filter(User.email == user_email).first()
                        if user:
                            configs = (
                                session.query(GitHubTokenConfig)
                                .filter(GitHubTokenConfig.user_id == user.id)
                                .order_by(GitHubTokenConfig.display_order)
                                .all()
                            )
                            if configs:
                                config_dicts = [c.to_dict() for c in configs]
                                manager = GitHubTokenManager.from_named_headers(
                                    named_tokens=named_tokens,
                                    configs=config_dicts,
                                    api_url=api_url,
                                )
                                logger.info(
                                    f"GitHub request: user={user_email}, "
                                    f"{len(named_tokens)} named token(s) matched against "
                                    f"{len(configs)} DB config(s)"
                                )
                except Exception as e:
                    logger.warning(f"GitHub named token resolution failed: {e}")

        if manager is None:
            tokens_json = headers.get("x-github-tokens")
            if tokens_json:
                try:
                    manager = GitHubTokenManager.from_header(tokens_json, api_url)
                    token_count = len(manager.get_token_info())
                    logger.info(f"GitHub request: {token_count} token(s) via JSON header")
                except ValueError as e:
                    logger.warning(f"GitHub JSON token header error: {e}")

        if manager is None:
            token = headers.get("x-github-token")
            if token:
                try:
                    manager = GitHubTokenManager.from_single_token(token, api_url)
                    logger.debug("GitHub request: single token configured")
                except ValueError as e:
                    logger.warning(f"GitHub single token error: {e}")

        if manager is None:
            logger.warning("GitHub request: no tokens configured")
        else:
            _github_token_manager_ctx.set(manager)

        await github_session_mgr.handle_request(scope, receive, send)

    async def reports_handler(scope: Scope, receive: Receive, send: Send) -> None:
        """Authenticate and set up context for Reports requests."""
        headers = extract_headers(scope)

        username = authenticate_via_pat(headers)

        if not username:
            username = (
                headers.get("x-forwarded-email")
                or headers.get("x-forwarded-user")
                or headers.get("x-username")
            )

        if not username:
            logger.warning("Reports request rejected: no valid authentication")
            await send_unauthorized(
                send, "Authentication required. Provide a Bearer token or valid proxy headers."
            )
            return

        _username_ctx.set(username)
        logger.debug(f"Reports request: user={username}")

        await reports_session_mgr.handle_request(scope, receive, send)

    # ── Lifespan: start/stop all session managers ──────────────────────────

    @asynccontextmanager
    async def lifespan(app: Starlette):  # noqa: ARG001
        async with AsyncExitStack() as stack:
            await stack.enter_async_context(github_session_mgr.run())
            await stack.enter_async_context(reports_session_mgr.run())
            logger.info("All Streamable HTTP session managers started")
            yield
        logger.info("All Streamable HTTP session managers stopped")

    # ── Starlette app ─────────────────────────────────────────────────────
    # Each Mount delegates to an auth wrapper → session manager pipeline.
    # Clients POST (and optionally GET/DELETE) directly to the mount path.
    _mcp_mount_paths = frozenset({"/mcp/github", "/mcp/reports"})

    starlette_app = Starlette(
        debug=False,
        routes=[
            Route("/health", endpoint=health_check, methods=["GET"]),
            Route("/mcp/health", endpoint=health_check, methods=["GET"]),
            Mount("/mcp/github", app=github_handler),
            Mount("/mcp/reports", app=reports_handler),
        ],
        lifespan=lifespan,
    )

    # Starlette's Mount issues a 307 redirect from /mcp/github to /mcp/github/
    # which breaks MCP clients (POST becomes GET, auth headers are lost).
    # This wrapper adds the trailing slash internally so Mount handles it
    # directly without a redirect.
    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope.get("path") in _mcp_mount_paths:
            scope = dict(scope)
            scope["path"] += "/"
        await starlette_app(scope, receive, send)

    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="info",
    )
    uvi_server = uvicorn.Server(config)
    await uvi_server.serve()


def main() -> None:
    """Run the MCP server."""
    init_db()
    logger.info("Database initialized")

    parser = argparse.ArgumentParser(
        description="Ghost MCP Server - GitHub integration and activity reporting",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Transport: Streamable HTTP (stateless)

Endpoints (all via POST to the mount path):
  /mcp/github    GitHub tools (PRs, reviews, comments)
  /mcp/reports   Activity logging & reporting tools

GitHub Headers (single token - simple):
  X-GitHub-Token       Personal Access Token (required if multi-token not used)
  X-GitHub-API-URL     API URL for Enterprise (optional)

GitHub Headers (multi-token via UI - recommended):
  Authorization        Bearer <reports PAT> to identify user and load DB-stored patterns
  X-GitHub-Token-NAME  Named GitHub PATs (e.g., X-GitHub-Token-personal, X-GitHub-Token-work)
                       Configure patterns in Settings > GitHub Token Configuration in the web UI

GitHub Headers (multi-token via JSON - alternative):
  X-GitHub-Tokens      JSON array of token-to-pattern mappings (overrides X-GitHub-Token)
                       Format: [{{"token":"ghp_...","patterns":["org/*"]}},{{"token":"ghp_...","patterns":["*"]}}]
  X-GitHub-API-URL     Default API URL for Enterprise (optional, can be overridden per token entry)

Reports Headers:
  Authorization        Bearer <PAT> (preferred) or proxy headers below
  X-Forwarded-Email    User email from OAuth proxy
  X-Username           Username for activity tracking

Note: Jira integration is handled via external Atlassian MCP. Configure it separately
      in your AI agent's MCP settings.

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
    asyncio.run(run_streamable_http(args.host, args.port))


if __name__ == "__main__":
    main()
