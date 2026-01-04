"""Comment-related MCP tools for Jira operations."""

from typing import Any, Optional

from jira_mcp.jira_client import JiraClient, get_jira_client
from jira_mcp.tools.schemas import AddCommentInput, GetCommentsInput


def jira_add_comment(
    ticket_key: str,
    body: str,
    jira_client: Optional[JiraClient] = None,
) -> dict[str, Any]:
    """
    Add a comment to a Jira ticket.

    Args:
        ticket_key: The issue key (e.g., 'PROJ-123').
        body: Comment body (supports Jira wiki markup).
        jira_client: Optional JiraClient instance for dependency injection.

    Returns:
        Created comment ID, issue key, body, author, and creation timestamp.
    """
    client = jira_client or get_jira_client()

    # Validate input
    input_data = AddCommentInput(
        ticket_key=ticket_key,
        body=body,
    )

    return client.add_comment(
        issue_key=input_data.ticket_key,
        body=input_data.body,
    )


def jira_get_comments(
    ticket_key: str,
    max_results: int = 20,
    jira_client: Optional[JiraClient] = None,
) -> list[dict[str, Any]]:
    """
    Get comments from a Jira ticket.

    Args:
        ticket_key: The issue key (e.g., 'PROJ-123').
        max_results: Maximum number of comments to return (1-100). Default: 20.
        jira_client: Optional JiraClient instance for dependency injection.

    Returns:
        List of comments with ID, author, body, and timestamps.
    """
    client = jira_client or get_jira_client()

    # Validate input
    input_data = GetCommentsInput(
        ticket_key=ticket_key,
        max_results=max_results,
    )

    return client.get_comments(
        issue_key=input_data.ticket_key,
        max_results=input_data.max_results,
    )

