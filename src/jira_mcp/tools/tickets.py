"""Ticket-related MCP tools for Jira operations."""

from typing import Any, Optional

from jira_mcp.jira_client import JiraClient, get_jira_client
from jira_mcp.tools.schemas import (
    ListTicketsInput,
    GetTicketInput,
    CreateTicketInput,
    UpdateTicketInput,
)


def jira_list_tickets(
    assignee: Optional[str] = None,
    project: Optional[str] = None,
    component: Optional[str] = None,
    epic_key: Optional[str] = None,
    status: Optional[str] = None,
    max_results: int = 50,
    jira_client: Optional[JiraClient] = None,
) -> list[dict[str, Any]]:
    """
    List Jira tickets with optional filters.

    Args:
        assignee: Filter by assignee username. Use 'currentUser' for authenticated user.
        project: Filter by project key (e.g., 'PROJ').
        component: Filter by component name.
        epic_key: Filter by epic issue key (e.g., 'PROJ-100').
        status: Filter by issue status (e.g., 'Open', 'In Progress', 'Done').
        max_results: Maximum number of results to return (1-100). Default: 50.
        jira_client: Optional JiraClient instance for dependency injection.

    Returns:
        List of ticket summaries with key, summary, status, assignee, priority.
    """
    client = jira_client or get_jira_client()

    # Validate input
    input_data = ListTicketsInput(
        assignee=assignee,
        project=project,
        component=component,
        epic_key=epic_key,
        status=status,
        max_results=max_results,
    )

    jql = client.build_jql(
        assignee=input_data.assignee,
        project=input_data.project,
        component=input_data.component,
        epic_key=input_data.epic_key,
        status=input_data.status,
    )

    return client.search_issues(jql, max_results=input_data.max_results)


def jira_get_ticket(
    ticket_key: str,
    jira_client: Optional[JiraClient] = None,
) -> dict[str, Any]:
    """
    Get full details of a specific Jira ticket.

    Args:
        ticket_key: The issue key (e.g., 'PROJ-123').
        jira_client: Optional JiraClient instance for dependency injection.

    Returns:
        Full ticket details including description, components, labels,
        comments count, and epic link.
    """
    client = jira_client or get_jira_client()

    # Validate input
    input_data = GetTicketInput(ticket_key=ticket_key)

    return client.get_issue(input_data.ticket_key)


def jira_create_ticket(
    project: str,
    summary: str,
    description: Optional[str] = None,
    issue_type: str = "Task",
    assignee: Optional[str] = None,
    components: Optional[list[str]] = None,
    epic_key: Optional[str] = None,
    priority: Optional[str] = None,
    labels: Optional[list[str]] = None,
    jira_client: Optional[JiraClient] = None,
) -> dict[str, Any]:
    """
    Create a new Jira ticket with specified fields.

    Args:
        project: Project key (e.g., 'PROJ').
        summary: Issue title/summary.
        description: Issue description (supports Jira wiki markup).
        issue_type: Issue type (e.g., 'Task', 'Bug', 'Story', 'Epic'). Default: 'Task'.
        assignee: Assignee username.
        components: List of component names.
        epic_key: Parent epic issue key.
        priority: Priority name (e.g., 'High', 'Medium', 'Low').
        labels: List of labels.
        jira_client: Optional JiraClient instance for dependency injection.

    Returns:
        Created ticket key, id, URL, and summary.
    """
    client = jira_client or get_jira_client()

    # Validate input
    input_data = CreateTicketInput(
        project=project,
        summary=summary,
        description=description,
        issue_type=issue_type,
        assignee=assignee,
        components=components,
        epic_key=epic_key,
        priority=priority,
        labels=labels,
    )

    return client.create_issue(
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


def jira_update_ticket(
    ticket_key: str,
    summary: Optional[str] = None,
    description: Optional[str] = None,
    assignee: Optional[str] = None,
    status: Optional[str] = None,
    components: Optional[list[str]] = None,
    priority: Optional[str] = None,
    jira_client: Optional[JiraClient] = None,
) -> dict[str, Any]:
    """
    Update an existing Jira ticket's fields.

    Args:
        ticket_key: The issue key (e.g., 'PROJ-123').
        summary: New issue title/summary.
        description: New issue description (supports Jira wiki markup).
        assignee: New assignee username. Use empty string to unassign.
        status: Transition to this status (e.g., 'In Progress', 'Done').
        components: New list of component names (replaces existing).
        priority: New priority name.
        jira_client: Optional JiraClient instance for dependency injection.

    Returns:
        Updated ticket key, confirmation, and URL.
    """
    client = jira_client or get_jira_client()

    # Validate input
    input_data = UpdateTicketInput(
        ticket_key=ticket_key,
        summary=summary,
        description=description,
        assignee=assignee,
        status=status,
        components=components,
        priority=priority,
    )

    return client.update_issue(
        issue_key=input_data.ticket_key,
        summary=input_data.summary,
        description=input_data.description,
        assignee=input_data.assignee,
        status=input_data.status,
        components=input_data.components,
        priority=input_data.priority,
    )

