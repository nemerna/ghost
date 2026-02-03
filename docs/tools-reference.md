# Tools Reference

Complete reference for all MCP tools available through Ghost.

## Jira Tools (`/mcp/jira`)

### Ticket Operations

| Tool | Description |
|------|-------------|
| `jira_list_tickets` | Search tickets by assignee, project, component, epic, status |
| `jira_get_ticket` | Get full ticket details |
| `jira_create_ticket` | Create a new ticket |
| `jira_update_ticket` | Update fields or transition status |

### Comment Operations

| Tool | Description |
|------|-------------|
| `jira_add_comment` | Add a comment to a ticket |
| `jira_get_comments` | List comments on a ticket |
| `jira_update_comment` | Edit an existing comment |
| `jira_delete_comment` | Delete a comment |

### Hierarchy Operations

| Tool | Description |
|------|-------------|
| `jira_link_issues` | Link two issues together |
| `jira_create_subtask` | Create a subtask under a parent issue |
| `jira_set_epic` | Assign an issue to an epic |

### Metadata Operations

| Tool | Description |
|------|-------------|
| `jira_list_projects` | List accessible projects |
| `jira_list_components` | List components for a project |
| `jira_list_issue_types` | List issue types for a project |
| `jira_list_priorities` | List priority levels |
| `jira_list_statuses` | List statuses for a project |
| `jira_get_transitions` | Get available transitions for a ticket |
| `jira_get_current_user` | Get authenticated user info |

## GitHub Tools (`/mcp/github`)

### Pull Request Operations

| Tool | Description |
|------|-------------|
| `github_list_prs` | List PRs for a repository |
| `github_get_pr` | Get PR details |
| `github_get_pr_diff` | Get unified diff |
| `github_get_pr_files` | List changed files with patches |
| `github_get_pr_commits` | List commits in PR |
| `github_search_prs` | Search PRs across repositories |

### PR Review Operations

| Tool | Description |
|------|-------------|
| `github_get_pr_reviews` | Get reviews on a PR |
| `github_get_pr_comments` | Get issue and review comments |
| `github_add_pr_comment` | Add a comment to a PR |
| `github_create_pr_review` | Submit a review: approve, request changes, or comment (with optional inline comments) |
| `github_add_pr_review_comment` | Add an inline comment on a specific file and line in the diff |
| `github_request_reviewers` | Request users or teams to review a PR |
| `github_remove_requested_reviewers` | Remove pending reviewer requests from a PR |
| `github_dismiss_pr_review` | Dismiss a submitted review (requires write access) |

### Issue Operations

| Tool | Description |
|------|-------------|
| `github_list_issues` | List issues for a repository |
| `github_get_issue` | Get full issue details |
| `github_create_issue` | Create a new issue |
| `github_update_issue` | Update an existing issue |
| `github_close_issue` | Close an issue with optional reason |
| `github_reopen_issue` | Reopen a closed issue |
| `github_get_issue_comments` | Get comments on an issue |
| `github_add_issue_comment` | Add a comment to an issue |
| `github_search_issues` | Search issues across repositories |

### User Operations

| Tool | Description |
|------|-------------|
| `github_get_current_user` | Get authenticated GitHub user |

## Reports Tools (`/mcp/reports`)

### Activity Tracking

| Tool | Description |
|------|-------------|
| `log_activity` | Record work on a Jira ticket (`PROJ-123`) or GitHub issue (`owner/repo#123`) |
| `get_weekly_activity` | Summarize activity for a week |
| `get_activity_details` | Get detailed info about a specific activity (useful for debugging detection) |
| `redetect_project_assignments` | Re-run project detection on existing activities (auto-fetches Jira components) |

### Weekly Reports

| Tool | Description |
|------|-------------|
| `generate_weekly_report` | Generate Markdown report from logged activity |
| `save_weekly_report` | Persist report to database |
| `list_saved_reports` | List saved reports |
| `get_saved_report` | Retrieve a report by ID |
| `delete_saved_report` | Delete a report |

### Management Reports

| Tool | Description |
|------|-------------|
| `get_report_instructions` | Get management report generation instructions |
| `save_management_report` | Store AI-generated stakeholder report with structured entries |
| `list_management_reports` | List reports, optionally by project |
| `get_management_report` | Retrieve full report content with entries |
| `update_management_report` | Edit an existing report |
| `delete_management_report` | Delete a report |

### Configuration

| Tool | Description |
|------|-------------|
| `list_report_fields` | List configured report fields and projects with Jira/GitHub mappings |

## Management Report Entry Format

Management reports use structured entries with per-item visibility control:

```json
{
  "title": "Week 4, January 2026",
  "entries": [
    { "text": "[Completed](PR-URL) the [feature](ISSUE-URL)", "ticket_key": "PROJ-123" },
    { "text": "[Fixed](PR-URL) the [bug](ISSUE-URL)", "ticket_key": "PROJ-456", "private": true }
  ],
  "referenced_tickets": ["PROJ-123", "PROJ-456"]
}
```

| Field | Description |
|-------|-------------|
| `entries` | Array of work items with `text`, optional `ticket_key`, and optional `private` flag |
| `ticket_key` | When provided, visibility is auto-inherited from the activity's visibility setting |
| `private` | If `true`, entry is hidden from managers in team views |

## Example Prompts

### Jira Examples

- "List my in-progress Jira tickets and summarize blockers."
- "Create a bug ticket in PROJECT for the login issue."
- "Update PROJ-123 to In Progress and add a comment about starting work."

### GitHub Examples

- "Show open PRs for org/repo and summarize review feedback."
- "Create a GitHub issue to track this bug."
- "Review PR #123 on org/repo and approve it with a comment."
- "Request @alice and @bob to review PR #456."
- "Add a comment on line 42 of src/main.py in PR #789 about the error handling."

### Reports Examples

- "Log that I worked on PROJ-123 today."
- "Log activity on github.com/org/repo#456."
- "Generate my weekly report and save it."
- "Write a management report for PROJ using this week's activity."

## See Also

- [Getting Started](getting-started.md) - Initial setup
- [Configuration](configuration.md) - Header configuration for each endpoint
- [Architecture](architecture.md) - How the tools connect to external services
