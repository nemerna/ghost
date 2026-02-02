"""Discovery and metadata MCP tools for Jira operations."""

from typing import Any

from ghost.jira_client import JiraClient, get_jira_client
from ghost.tools.schemas import (
    GetTransitionsInput,
    ListComponentsInput,
    ListIssueTypesInput,
    ListStatusesInput,
)


def jira_list_projects(
    jira_client: JiraClient | None = None,
) -> list[dict[str, Any]]:
    """
    List all accessible Jira projects.

    Args:
        jira_client: Optional JiraClient instance for dependency injection.

    Returns:
        List of projects with key, name, lead, and URL.
    """
    client = jira_client or get_jira_client()
    return client.get_projects()


def jira_list_components(
    project: str,
    jira_client: JiraClient | None = None,
) -> list[dict[str, Any]]:
    """
    List components for a Jira project.

    Args:
        project: Project key (e.g., 'PROJ').
        jira_client: Optional JiraClient instance for dependency injection.

    Returns:
        List of components with id, name, description, and lead.
    """
    client = jira_client or get_jira_client()

    # Validate input
    input_data = ListComponentsInput(project=project)

    return client.get_components(input_data.project)


def jira_list_issue_types(
    project: str,
    jira_client: JiraClient | None = None,
) -> list[dict[str, Any]]:
    """
    List available issue types for a Jira project.

    Args:
        project: Project key (e.g., 'PROJ').
        jira_client: Optional JiraClient instance for dependency injection.

    Returns:
        List of issue types with id, name, description, and subtask flag.
    """
    client = jira_client or get_jira_client()

    # Validate input
    input_data = ListIssueTypesInput(project=project)

    return client.get_issue_types(input_data.project)


def jira_list_priorities(
    jira_client: JiraClient | None = None,
) -> list[dict[str, Any]]:
    """
    List all available priorities in Jira.

    Args:
        jira_client: Optional JiraClient instance for dependency injection.

    Returns:
        List of priorities with id, name, description, and icon URL.
    """
    client = jira_client or get_jira_client()
    return client.get_priorities()


def jira_list_statuses(
    project: str,
    jira_client: JiraClient | None = None,
) -> list[dict[str, Any]]:
    """
    List available statuses for a Jira project.

    Args:
        project: Project key (e.g., 'PROJ').
        jira_client: Optional JiraClient instance for dependency injection.

    Returns:
        List of statuses with id, name, description, and category.
    """
    client = jira_client or get_jira_client()

    # Validate input
    input_data = ListStatusesInput(project=project)

    return client.get_statuses(input_data.project)


def jira_get_transitions(
    ticket_key: str,
    jira_client: JiraClient | None = None,
) -> list[dict[str, Any]]:
    """
    Get available workflow transitions for a Jira ticket.

    Args:
        ticket_key: The issue key (e.g., 'PROJ-123').
        jira_client: Optional JiraClient instance for dependency injection.

    Returns:
        List of transitions with id, name, and target status.
    """
    client = jira_client or get_jira_client()

    # Validate input
    input_data = GetTransitionsInput(ticket_key=ticket_key)

    return client.get_transitions(input_data.ticket_key)


def jira_get_current_user(
    jira_client: JiraClient | None = None,
) -> dict[str, Any]:
    """
    Get information about the currently authenticated user.

    Args:
        jira_client: Optional JiraClient instance for dependency injection.

    Returns:
        User information with username, display name, email, active status, and timezone.
    """
    client = jira_client or get_jira_client()
    return client.get_current_user()
