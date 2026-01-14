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


class UpdateCommentInput(BaseModel):
    """Input schema for jira_update_comment tool."""

    ticket_key: str = Field(
        ...,
        description="The issue key (e.g., 'PROJ-123').",
    )
    comment_id: str = Field(
        ...,
        description="The comment ID to update.",
    )
    body: str = Field(
        ...,
        min_length=1,
        description="New comment body (supports Jira wiki markup).",
    )


class DeleteCommentInput(BaseModel):
    """Input schema for jira_delete_comment tool."""

    ticket_key: str = Field(
        ...,
        description="The issue key (e.g., 'PROJ-123').",
    )
    comment_id: str = Field(
        ...,
        description="The comment ID to delete.",
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


# --- Issue Linking & Hierarchy Input Schemas ---


class LinkIssuesInput(BaseModel):
    """Input schema for jira_link_issues tool."""

    from_key: str = Field(
        ...,
        description="The source issue key (e.g., 'PROJ-123').",
    )
    to_key: str = Field(
        ...,
        description="The target issue key (e.g., 'PROJ-456').",
    )
    link_type: str = Field(
        default="relates to",
        description="The type of link (e.g., 'relates to', 'blocks', 'is blocked by', 'is part of', 'duplicates').",
    )


class CreateSubtaskInput(BaseModel):
    """Input schema for jira_create_subtask tool."""

    parent_key: str = Field(
        ...,
        description="The parent issue key (e.g., 'PROJ-123').",
    )
    summary: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Sub-task title/summary.",
    )
    description: Optional[str] = Field(
        default=None,
        description="Sub-task description (supports Jira wiki markup).",
    )
    assignee: Optional[str] = Field(
        default=None,
        description="Assignee username.",
    )
    priority: Optional[str] = Field(
        default=None,
        description="Priority name (e.g., 'High', 'Medium', 'Low').",
    )


class SetEpicInput(BaseModel):
    """Input schema for jira_set_epic tool."""

    issue_key: str = Field(
        ...,
        description="The issue key to update (e.g., 'PROJ-123').",
    )
    epic_key: str = Field(
        ...,
        description="The epic issue key to set as parent (e.g., 'PROJ-100').",
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


# --- Activity Tracking & Reports Input Schemas ---


class LogActivityInput(BaseModel):
    """Input schema for log_jira_activity tool."""

    ticket_key: str = Field(
        ...,
        description="The Jira ticket key (e.g., 'PROJ-123').",
    )
    action_type: str = Field(
        default="other",
        description="Type of action: view, create, update, comment, transition, link, or other.",
    )
    ticket_summary: Optional[str] = Field(
        default=None,
        description="Optional ticket summary for context.",
    )
    action_details: Optional[str] = Field(
        default=None,
        description="Optional JSON string with additional context.",
    )


class GetWeeklyActivityInput(BaseModel):
    """Input schema for get_weekly_activity tool."""

    week_offset: int = Field(
        default=0,
        ge=-52,
        le=0,
        description="Week offset from current week (0 = current, -1 = last week, etc.).",
    )
    project: Optional[str] = Field(
        default=None,
        description="Optional project key to filter by.",
    )


class GenerateWeeklyReportInput(BaseModel):
    """Input schema for generate_weekly_report tool."""

    week_offset: int = Field(
        default=0,
        ge=-52,
        le=0,
        description="Week offset from current week (0 = current, -1 = last week, etc.).",
    )
    include_details: bool = Field(
        default=True,
        description="Whether to include detailed ticket list in the report.",
    )


class SaveWeeklyReportInput(BaseModel):
    """Input schema for save_weekly_report tool."""

    week_offset: int = Field(
        default=0,
        ge=-52,
        le=0,
        description="Week offset from current week (0 = current, -1 = last week, etc.).",
    )
    custom_title: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Optional custom title override.",
    )
    custom_summary: Optional[str] = Field(
        default=None,
        description="Optional custom executive summary override.",
    )


class ListSavedReportsInput(BaseModel):
    """Input schema for list_saved_reports tool."""

    limit: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of reports to return.",
    )


class GetSavedReportInput(BaseModel):
    """Input schema for get_saved_report tool."""

    report_id: int = Field(
        ...,
        description="The report ID to retrieve.",
    )


class DeleteSavedReportInput(BaseModel):
    """Input schema for delete_saved_report tool."""

    report_id: int = Field(
        ...,
        description="The report ID to delete.",
    )


# --- Management Reports Input Schemas ---


class SaveManagementReportInput(BaseModel):
    """Input schema for save_management_report tool."""

    title: str = Field(
        ...,
        max_length=500,
        description="Report title (e.g., 'APPENG Progress - Week 3').",
    )
    one_liner: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Single sentence elevator pitch (max 15 words).",
    )
    executive_summary: str = Field(
        ...,
        description="2-3 sentence high-level summary. Focus on outcomes, not technical details.",
    )
    content: str = Field(
        ...,
        description="Concise Markdown report (<500 words). Use bullet points, include Jira links.",
    )
    project_key: Optional[str] = Field(
        default=None,
        description="Project key (e.g., 'APPENG').",
    )
    report_period: Optional[str] = Field(
        default=None,
        description="Period (e.g., 'Week 3, Jan 2026' or 'Sprint 42').",
    )
    referenced_tickets: Optional[list[str]] = Field(
        default=None,
        description="Jira ticket keys mentioned in report.",
    )


class ListManagementReportsInput(BaseModel):
    """Input schema for list_management_reports tool."""

    project_key: Optional[str] = Field(
        default=None,
        description="Optional filter by project key.",
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of reports to return.",
    )


class GetManagementReportInput(BaseModel):
    """Input schema for get_management_report tool."""

    report_id: int = Field(
        ...,
        description="The management report ID to retrieve.",
    )


class UpdateManagementReportInput(BaseModel):
    """Input schema for update_management_report tool."""

    report_id: int = Field(
        ...,
        description="The management report ID to update.",
    )
    title: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Optional new title.",
    )
    one_liner: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Optional new one-liner elevator pitch.",
    )
    executive_summary: Optional[str] = Field(
        default=None,
        description="Optional new executive summary.",
    )
    content: Optional[str] = Field(
        default=None,
        description="Optional new Markdown content.",
    )
    report_period: Optional[str] = Field(
        default=None,
        description="Optional new period.",
    )
    referenced_tickets: Optional[list[str]] = Field(
        default=None,
        description="Optional new list of referenced ticket keys.",
    )


class DeleteManagementReportInput(BaseModel):
    """Input schema for delete_management_report tool."""

    report_id: int = Field(
        ...,
        description="The management report ID to delete.",
    )

