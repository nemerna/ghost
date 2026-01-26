"""Pydantic schemas for MCP tool inputs and outputs."""

from pydantic import BaseModel, Field

# --- Input Schemas ---


class ListTicketsInput(BaseModel):
    """Input schema for jira_list_tickets tool."""

    assignee: str | None = Field(
        default=None,
        description="Filter by assignee username. Use 'currentUser' for the authenticated user.",
    )
    project: str | None = Field(
        default=None,
        description="Filter by project key (e.g., 'PROJ').",
    )
    component: str | None = Field(
        default=None,
        description="Filter by component name.",
    )
    epic_key: str | None = Field(
        default=None,
        description="Filter by epic issue key (e.g., 'PROJ-100').",
    )
    status: str | None = Field(
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
    description: str | None = Field(
        default=None,
        description="Issue description (supports Jira wiki markup).",
    )
    issue_type: str = Field(
        default="Task",
        description="Issue type (e.g., 'Task', 'Bug', 'Story', 'Epic').",
    )
    assignee: str | None = Field(
        default=None,
        description="Assignee username.",
    )
    components: list[str] | None = Field(
        default=None,
        description="List of component names.",
    )
    epic_key: str | None = Field(
        default=None,
        description="Parent epic issue key.",
    )
    priority: str | None = Field(
        default=None,
        description="Priority name (e.g., 'High', 'Medium', 'Low').",
    )
    labels: list[str] | None = Field(
        default=None,
        description="List of labels.",
    )


class UpdateTicketInput(BaseModel):
    """Input schema for jira_update_ticket tool."""

    ticket_key: str = Field(
        ...,
        description="The issue key (e.g., 'PROJ-123').",
    )
    summary: str | None = Field(
        default=None,
        max_length=255,
        description="New issue title/summary.",
    )
    description: str | None = Field(
        default=None,
        description="New issue description (supports Jira wiki markup).",
    )
    assignee: str | None = Field(
        default=None,
        description="New assignee username. Use empty string to unassign.",
    )
    status: str | None = Field(
        default=None,
        description="Transition to this status (e.g., 'In Progress', 'Done').",
    )
    components: list[str] | None = Field(
        default=None,
        description="New list of component names (replaces existing).",
    )
    priority: str | None = Field(
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
    description: str | None = Field(
        default=None,
        description="Sub-task description (supports Jira wiki markup).",
    )
    assignee: str | None = Field(
        default=None,
        description="Assignee username.",
    )
    priority: str | None = Field(
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
    assignee: str | None
    priority: str | None
    issue_type: str
    created: str
    updated: str


class TicketDetail(TicketSummary):
    """Full details of a ticket."""

    id: str
    url: str
    description: str | None
    reporter: str | None
    components: list[str]
    labels: list[str]
    epic_key: str | None
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
    """Input schema for log_activity tool."""

    ticket_key: str = Field(
        ...,
        description="The ticket key. Jira format: 'PROJ-123'. GitHub format: 'owner/repo#123' or '#123' (with github_repo).",
    )
    action_type: str = Field(
        default="other",
        description="Type of action: view, create, update, comment, transition, link, or other.",
    )
    ticket_summary: str | None = Field(
        default=None,
        description="Optional ticket summary for context.",
    )
    github_repo: str | None = Field(
        default=None,
        description="For GitHub issues: repository in 'owner/repo' format. Required if using short '#123' format.",
    )
    jira_components: list[str] | None = Field(
        default=None,
        description="Optional list of Jira component names for auto-detection of report project.",
    )
    action_details: str | None = Field(
        default=None,
        description="Optional JSON string with additional context.",
    )


class RedetectProjectAssignmentsInput(BaseModel):
    """Input schema for redetect_project_assignments tool."""

    username: str | None = Field(
        default=None,
        description="Optional filter to only redetect for a specific user.",
    )
    limit: int = Field(
        default=1000,
        ge=1,
        le=10000,
        description="Maximum number of activities to process.",
    )


class GetWeeklyActivityInput(BaseModel):
    """Input schema for get_weekly_activity tool."""

    week_offset: int = Field(
        default=0,
        ge=-52,
        le=0,
        description="Week offset from current week (0 = current, -1 = last week, etc.).",
    )
    project: str | None = Field(
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
    custom_title: str | None = Field(
        default=None,
        max_length=500,
        description="Optional custom title override.",
    )
    custom_summary: str | None = Field(
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
        description="Report title (e.g., 'Week 4, January 2026').",
    )
    content: str = Field(
        ...,
        description="Bullet list of work items with embedded links. No summaries or future plans.",
    )
    project_key: str | None = Field(
        default=None,
        description="Project key (e.g., 'APPENG').",
    )
    report_period: str | None = Field(
        default=None,
        description="Period (e.g., 'Week 3, Jan 2026' or 'Sprint 42').",
    )
    referenced_tickets: list[str] | None = Field(
        default=None,
        description="Ticket keys mentioned in report (for indexing).",
    )


class ListManagementReportsInput(BaseModel):
    """Input schema for list_management_reports tool."""

    project_key: str | None = Field(
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
    title: str | None = Field(
        default=None,
        max_length=500,
        description="Optional new title.",
    )
    content: str | None = Field(
        default=None,
        description="Optional new content (bullet list of work items).",
    )
    report_period: str | None = Field(
        default=None,
        description="Optional new period.",
    )
    referenced_tickets: list[str] | None = Field(
        default=None,
        description="Optional new list of referenced ticket keys.",
    )


class DeleteManagementReportInput(BaseModel):
    """Input schema for delete_management_report tool."""

    report_id: int = Field(
        ...,
        description="The management report ID to delete.",
    )


# --- GitHub Pull Request Input Schemas ---


class GitHubListPRsInput(BaseModel):
    """Input schema for github_list_prs tool."""

    owner: str = Field(
        ...,
        description="Repository owner (user or organization).",
    )
    repo: str = Field(
        ...,
        description="Repository name.",
    )
    state: str = Field(
        default="open",
        description="Filter by state: 'open', 'closed', or 'all'.",
    )
    head: str | None = Field(
        default=None,
        description="Filter by head user/org and branch (format: 'user:branch').",
    )
    base: str | None = Field(
        default=None,
        description="Filter by base branch name.",
    )
    sort: str = Field(
        default="created",
        description="Sort by: 'created', 'updated', 'popularity', 'long-running'.",
    )
    direction: str = Field(
        default="desc",
        description="Sort direction: 'asc' or 'desc'.",
    )
    per_page: int = Field(
        default=30,
        ge=1,
        le=100,
        description="Results per page (max 100).",
    )
    page: int = Field(
        default=1,
        ge=1,
        description="Page number.",
    )


class GitHubGetPRInput(BaseModel):
    """Input schema for github_get_pr tool."""

    owner: str = Field(
        ...,
        description="Repository owner (user or organization).",
    )
    repo: str = Field(
        ...,
        description="Repository name.",
    )
    pr_number: int = Field(
        ...,
        description="Pull request number.",
    )


class GitHubGetPRDiffInput(BaseModel):
    """Input schema for github_get_pr_diff tool."""

    owner: str = Field(
        ...,
        description="Repository owner (user or organization).",
    )
    repo: str = Field(
        ...,
        description="Repository name.",
    )
    pr_number: int = Field(
        ...,
        description="Pull request number.",
    )


class GitHubGetPRFilesInput(BaseModel):
    """Input schema for github_get_pr_files tool."""

    owner: str = Field(
        ...,
        description="Repository owner (user or organization).",
    )
    repo: str = Field(
        ...,
        description="Repository name.",
    )
    pr_number: int = Field(
        ...,
        description="Pull request number.",
    )
    per_page: int = Field(
        default=30,
        ge=1,
        le=100,
        description="Results per page (max 100).",
    )
    page: int = Field(
        default=1,
        ge=1,
        description="Page number.",
    )


class GitHubGetPRCommitsInput(BaseModel):
    """Input schema for github_get_pr_commits tool."""

    owner: str = Field(
        ...,
        description="Repository owner (user or organization).",
    )
    repo: str = Field(
        ...,
        description="Repository name.",
    )
    pr_number: int = Field(
        ...,
        description="Pull request number.",
    )
    per_page: int = Field(
        default=30,
        ge=1,
        le=100,
        description="Results per page (max 100).",
    )
    page: int = Field(
        default=1,
        ge=1,
        description="Page number.",
    )


class GitHubGetPRReviewsInput(BaseModel):
    """Input schema for github_get_pr_reviews tool."""

    owner: str = Field(
        ...,
        description="Repository owner (user or organization).",
    )
    repo: str = Field(
        ...,
        description="Repository name.",
    )
    pr_number: int = Field(
        ...,
        description="Pull request number.",
    )
    per_page: int = Field(
        default=30,
        ge=1,
        le=100,
        description="Results per page (max 100).",
    )
    page: int = Field(
        default=1,
        ge=1,
        description="Page number.",
    )


class GitHubGetPRCommentsInput(BaseModel):
    """Input schema for github_get_pr_comments tool."""

    owner: str = Field(
        ...,
        description="Repository owner (user or organization).",
    )
    repo: str = Field(
        ...,
        description="Repository name.",
    )
    pr_number: int = Field(
        ...,
        description="Pull request number.",
    )
    per_page: int = Field(
        default=30,
        ge=1,
        le=100,
        description="Results per page (max 100).",
    )
    page: int = Field(
        default=1,
        ge=1,
        description="Page number.",
    )


class GitHubAddPRCommentInput(BaseModel):
    """Input schema for github_add_pr_comment tool."""

    owner: str = Field(
        ...,
        description="Repository owner (user or organization).",
    )
    repo: str = Field(
        ...,
        description="Repository name.",
    )
    pr_number: int = Field(
        ...,
        description="Pull request number.",
    )
    body: str = Field(
        ...,
        min_length=1,
        description="Comment body (Markdown).",
    )
    in_reply_to: int | None = Field(
        default=None,
        description="Optional review comment ID to reply to. If provided, posts a reply in the review thread.",
    )


class GitHubSearchPRsInput(BaseModel):
    """Input schema for github_search_prs tool."""

    query: str = Field(
        ...,
        description="GitHub search query. Examples: 'author:username', 'repo:owner/repo', 'state:open', 'label:bug'. Use 'is:pr' prefix is added automatically.",
    )
    sort: str = Field(
        default="created",
        description="Sort by: 'created', 'updated', 'comments'.",
    )
    order: str = Field(
        default="desc",
        description="Sort order: 'asc' or 'desc'.",
    )
    per_page: int = Field(
        default=30,
        ge=1,
        le=100,
        description="Results per page (max 100).",
    )
    page: int = Field(
        default=1,
        ge=1,
        description="Page number.",
    )


# --- GitHub Issues Input Schemas ---


class GitHubListIssuesInput(BaseModel):
    """Input schema for github_list_issues tool."""

    owner: str = Field(
        ...,
        description="Repository owner (user or organization).",
    )
    repo: str = Field(
        ...,
        description="Repository name.",
    )
    state: str = Field(
        default="open",
        description="Filter by state: 'open', 'closed', or 'all'.",
    )
    labels: str | None = Field(
        default=None,
        description="Comma-separated list of label names to filter by.",
    )
    assignee: str | None = Field(
        default=None,
        description="Filter by assignee username. Use '*' for any, 'none' for unassigned.",
    )
    creator: str | None = Field(
        default=None,
        description="Filter by creator username.",
    )
    milestone: str | None = Field(
        default=None,
        description="Filter by milestone number, '*' for any, or 'none' for no milestone.",
    )
    sort: str = Field(
        default="created",
        description="Sort by: 'created', 'updated', 'comments'.",
    )
    direction: str = Field(
        default="desc",
        description="Sort direction: 'asc' or 'desc'.",
    )
    since: str | None = Field(
        default=None,
        description="Only issues updated after this ISO 8601 timestamp.",
    )
    per_page: int = Field(
        default=30,
        ge=1,
        le=100,
        description="Results per page (max 100).",
    )
    page: int = Field(
        default=1,
        ge=1,
        description="Page number.",
    )


class GitHubGetIssueInput(BaseModel):
    """Input schema for github_get_issue tool."""

    owner: str = Field(
        ...,
        description="Repository owner (user or organization).",
    )
    repo: str = Field(
        ...,
        description="Repository name.",
    )
    issue_number: int = Field(
        ...,
        description="Issue number.",
    )


class GitHubCreateIssueInput(BaseModel):
    """Input schema for github_create_issue tool."""

    owner: str = Field(
        ...,
        description="Repository owner (user or organization).",
    )
    repo: str = Field(
        ...,
        description="Repository name.",
    )
    title: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Issue title.",
    )
    body: str | None = Field(
        default=None,
        description="Issue body (Markdown).",
    )
    assignees: list[str] | None = Field(
        default=None,
        description="List of usernames to assign.",
    )
    labels: list[str] | None = Field(
        default=None,
        description="List of label names.",
    )
    milestone: int | None = Field(
        default=None,
        description="Milestone number to associate.",
    )


class GitHubUpdateIssueInput(BaseModel):
    """Input schema for github_update_issue tool."""

    owner: str = Field(
        ...,
        description="Repository owner (user or organization).",
    )
    repo: str = Field(
        ...,
        description="Repository name.",
    )
    issue_number: int = Field(
        ...,
        description="Issue number.",
    )
    title: str | None = Field(
        default=None,
        max_length=256,
        description="New issue title.",
    )
    body: str | None = Field(
        default=None,
        description="New issue body (Markdown).",
    )
    state: str | None = Field(
        default=None,
        description="New state: 'open' or 'closed'.",
    )
    assignees: list[str] | None = Field(
        default=None,
        description="New list of assignees (replaces existing).",
    )
    labels: list[str] | None = Field(
        default=None,
        description="New list of labels (replaces existing).",
    )
    milestone: int | None = Field(
        default=None,
        description="New milestone number (use 0 to clear).",
    )


class GitHubCloseIssueInput(BaseModel):
    """Input schema for github_close_issue tool."""

    owner: str = Field(
        ...,
        description="Repository owner (user or organization).",
    )
    repo: str = Field(
        ...,
        description="Repository name.",
    )
    issue_number: int = Field(
        ...,
        description="Issue number.",
    )
    state_reason: str | None = Field(
        default=None,
        description="Reason for closing: 'completed' or 'not_planned'.",
    )


class GitHubReopenIssueInput(BaseModel):
    """Input schema for github_reopen_issue tool."""

    owner: str = Field(
        ...,
        description="Repository owner (user or organization).",
    )
    repo: str = Field(
        ...,
        description="Repository name.",
    )
    issue_number: int = Field(
        ...,
        description="Issue number.",
    )


class GitHubGetIssueCommentsInput(BaseModel):
    """Input schema for github_get_issue_comments tool."""

    owner: str = Field(
        ...,
        description="Repository owner (user or organization).",
    )
    repo: str = Field(
        ...,
        description="Repository name.",
    )
    issue_number: int = Field(
        ...,
        description="Issue number.",
    )
    since: str | None = Field(
        default=None,
        description="Only comments updated after this ISO 8601 timestamp.",
    )
    per_page: int = Field(
        default=30,
        ge=1,
        le=100,
        description="Results per page (max 100).",
    )
    page: int = Field(
        default=1,
        ge=1,
        description="Page number.",
    )


class GitHubAddIssueCommentInput(BaseModel):
    """Input schema for github_add_issue_comment tool."""

    owner: str = Field(
        ...,
        description="Repository owner (user or organization).",
    )
    repo: str = Field(
        ...,
        description="Repository name.",
    )
    issue_number: int = Field(
        ...,
        description="Issue number.",
    )
    body: str = Field(
        ...,
        min_length=1,
        description="Comment body (Markdown).",
    )


class GitHubSearchIssuesInput(BaseModel):
    """Input schema for github_search_issues tool."""

    query: str = Field(
        ...,
        description="GitHub search query. Examples: 'author:username', 'repo:owner/repo', 'state:open', 'label:bug'. 'is:issue' prefix is added automatically.",
    )
    sort: str = Field(
        default="created",
        description="Sort by: 'created', 'updated', 'comments'.",
    )
    order: str = Field(
        default="desc",
        description="Sort order: 'asc' or 'desc'.",
    )
    per_page: int = Field(
        default=30,
        ge=1,
        le=100,
        description="Results per page (max 100).",
    )
    page: int = Field(
        default=1,
        ge=1,
        description="Page number.",
    )
