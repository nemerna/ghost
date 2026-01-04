"""Pydantic schemas for MCP tool inputs and outputs."""

from typing import Optional

from pydantic import BaseModel, Field


# --- Input Schemas ---


class ListTicketsInput(BaseModel):
    """Input schema for jira_list_tickets tool."""

    assignee: Optional[str] = Field(
        default=None,
        description="Filter by assignee username. Use 'currentUser' for the authenticated user.",
    )
    project: Optional[str] = Field(
        default=None,
        description="Filter by project key (e.g., 'PROJ').",
    )
    component: Optional[str] = Field(
        default=None,
        description="Filter by component name.",
    )
    epic_key: Optional[str] = Field(
        default=None,
        description="Filter by epic issue key (e.g., 'PROJ-100').",
    )
    status: Optional[str] = Field(
        default=None,
        description="Filter by issue status (e.g., 'Open', 'In Progress', 'Done').",
    )
    max_results: int = Field(
        default=50,
        ge=1,
        le=100,
        description="Maximum number of results to return (1-100).",
    )


class GetTicketInput(BaseModel):
    """Input schema for jira_get_ticket tool."""

    ticket_key: str = Field(
        ...,
        description="The issue key (e.g., 'PROJ-123').",
    )


class CreateTicketInput(BaseModel):
    """Input schema for jira_create_ticket tool."""

    project: str = Field(
        ...,
        description="Project key (e.g., 'PROJ').",
    )
    summary: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Issue title/summary.",
    )
    description: Optional[str] = Field(
        default=None,
        description="Issue description (supports Jira wiki markup).",
    )
    issue_type: str = Field(
        default="Task",
        description="Issue type (e.g., 'Task', 'Bug', 'Story', 'Epic').",
    )
    assignee: Optional[str] = Field(
        default=None,
        description="Assignee username.",
    )
    components: Optional[list[str]] = Field(
        default=None,
        description="List of component names.",
    )
    epic_key: Optional[str] = Field(
        default=None,
        description="Parent epic issue key.",
    )
    priority: Optional[str] = Field(
        default=None,
        description="Priority name (e.g., 'High', 'Medium', 'Low').",
    )
    labels: Optional[list[str]] = Field(
        default=None,
        description="List of labels.",
    )


class UpdateTicketInput(BaseModel):
    """Input schema for jira_update_ticket tool."""

    ticket_key: str = Field(
        ...,
        description="The issue key (e.g., 'PROJ-123').",
    )
    summary: Optional[str] = Field(
        default=None,
        max_length=255,
        description="New issue title/summary.",
    )
    description: Optional[str] = Field(
        default=None,
        description="New issue description (supports Jira wiki markup).",
    )
    assignee: Optional[str] = Field(
        default=None,
        description="New assignee username. Use empty string to unassign.",
    )
    status: Optional[str] = Field(
        default=None,
        description="Transition to this status (e.g., 'In Progress', 'Done').",
    )
    components: Optional[list[str]] = Field(
        default=None,
        description="New list of component names (replaces existing).",
    )
    priority: Optional[str] = Field(
        default=None,
        description="New priority name.",
    )


class AddCommentInput(BaseModel):
    """Input schema for jira_add_comment tool."""

    ticket_key: str = Field(
        ...,
        description="The issue key (e.g., 'PROJ-123').",
    )
    body: str = Field(
        ...,
        min_length=1,
        description="Comment body (supports Jira wiki markup).",
    )


class GetCommentsInput(BaseModel):
    """Input schema for jira_get_comments tool."""

    ticket_key: str = Field(
        ...,
        description="The issue key (e.g., 'PROJ-123').",
    )
    max_results: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of comments to return (1-100).",
    )


# --- Discovery Input Schemas ---


class ListComponentsInput(BaseModel):
    """Input schema for jira_list_components tool."""

    project: str = Field(
        ...,
        description="Project key (e.g., 'PROJ').",
    )


class ListIssueTypesInput(BaseModel):
    """Input schema for jira_list_issue_types tool."""

    project: str = Field(
        ...,
        description="Project key (e.g., 'PROJ').",
    )


class ListStatusesInput(BaseModel):
    """Input schema for jira_list_statuses tool."""

    project: str = Field(
        ...,
        description="Project key (e.g., 'PROJ').",
    )


class GetTransitionsInput(BaseModel):
    """Input schema for jira_get_transitions tool."""

    ticket_key: str = Field(
        ...,
        description="The issue key (e.g., 'PROJ-123').",
    )


# --- Output Schemas ---


class TicketSummary(BaseModel):
    """Summary information about a ticket."""

    key: str
    summary: str
    status: str
    assignee: Optional[str]
    priority: Optional[str]
    issue_type: str
    created: str
    updated: str


class TicketDetail(TicketSummary):
    """Full details of a ticket."""

    id: str
    url: str
    description: Optional[str]
    reporter: Optional[str]
    components: list[str]
    labels: list[str]
    epic_key: Optional[str]
    comments_count: int


class CreatedTicket(BaseModel):
    """Response after creating a ticket."""

    key: str
    id: str
    url: str
    summary: str


class UpdatedTicket(BaseModel):
    """Response after updating a ticket."""

    key: str
    updated: bool
    url: str


class Comment(BaseModel):
    """A comment on a ticket."""

    id: str
    author: str
    body: str
    created: str
    updated: str


class CreatedComment(BaseModel):
    """Response after creating a comment."""

    id: str
    issue_key: str
    body: str
    author: str
    created: str

