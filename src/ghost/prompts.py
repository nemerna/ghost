"""MCP Prompts for Ghost workflows.

These prompts are exposed via the Reports MCP server and appear as
slash-commands (/commands) in clients like Cursor.
"""

from mcp.types import GetPromptResult, Prompt, PromptArgument, PromptMessage, TextContent

PROMPTS: list[Prompt] = [
    Prompt(
        name="gather-activities",
        title="Gather Activities",
        description=(
            "Discover all work done during a week by checking Jira and GitHub, "
            "then compare against what's already logged."
        ),
        arguments=[
            PromptArgument(
                name="week_offset",
                description="How many weeks back to look (0 = current week, 1 = last week, etc.)",
                required=False,
            ),
        ],
    ),
    Prompt(
        name="log-activities",
        title="Log Activities",
        description=(
            "Log untracked work activities into the system. "
            "Presents items first and waits for confirmation before logging."
        ),
        arguments=[
            PromptArgument(
                name="week_offset",
                description="Which week to log activities for (0 = current week, 1 = last week)",
                required=False,
            ),
        ],
    ),
    Prompt(
        name="create-management-report",
        title="Create Management Report",
        description=(
            "Create a management report from logged activities with proper link formatting."
        ),
        arguments=[
            PromptArgument(
                name="week_offset",
                description="Which week to create the report for (0 = current week, 1 = last week)",
                required=False,
            ),
        ],
    ),
    Prompt(
        name="unghost",
        title="Unghost (Track Untracked Work)",
        description=(
            "Create a tracking ticket (Jira or GitHub Issue) for work that was already "
            "submitted without proper tracking, then add a progress comment linking the actual work."
        ),
    ),
]

_PROMPT_BY_NAME: dict[str, Prompt] = {p.name: p for p in PROMPTS}

# ---------------------------------------------------------------------------
# Prompt content
# ---------------------------------------------------------------------------

_GATHER_ACTIVITIES = """\
Discover all work I did during {period} by checking Jira and GitHub. \
Compare against what's already logged.

**ALWAYS use MCP server tools** for all Jira, GitHub, and work-reports operations. \
Never use CLI tools (`gh`, `jira-cli`), direct API calls, `curl`, or custom HTTP clients. \
If an MCP tool is unavailable or fails with a connection error, **STOP immediately** — \
do not fall back to alternatives. Inform the user that the MCP server appears to be down \
and suggest checking the server status.

## Step 0: Verify MCP Availability

Before doing anything else, verify that the MCP server is reachable:

1. Call `github_get_current_user` as a connectivity check
2. If the tool is **not available**, returns a **connection error**, or **times out**: \
**STOP immediately**. Tell the user:
   > "The MCP server appears to be unavailable. Please check that the Ghost server is \
running and that your MCP configuration is correct."
3. **Do NOT attempt to use CLI tools, direct API calls, or any alternative.** \
This workflow requires MCP tools — there is no fallback.

## Steps

1. **Identify me** on both platforms (run in parallel):
   - `jira_get_current_user`
   - `github_get_current_user`

2. **Check what's already logged**:
   - `get_weekly_activity(week_offset={week_offset})`
   - Note the `unique_tickets` list — these are already tracked

3. **Search Jira** for my tickets using `jira_list_tickets`:
   - `jira_list_tickets(assignee="currentUser", status="In Progress")`
   - `jira_list_tickets(assignee="currentUser", status="Done")`
   - `jira_list_tickets(assignee="currentUser", status="Review")`
   - Filter results by the `updated` field to only include tickets updated within the target week
   - Compare against already-logged tickets to find gaps

4. **Search GitHub** for my activity:
   - `github_search_prs(query="author:USERNAME updated:>=YYYY-MM-DD")` — PRs in the period
   - `github_search_issues(query="author:USERNAME updated:>=YYYY-MM-DD")` — issues in the period
   - `list_report_fields` — check configured repos to know where to look
   - Compare against already-logged tickets to find gaps

5. **Present findings**:
   - **Already tracked**: activities in the system
   - **Not yet logged**: work found in Jira/GitHub that hasn't been logged
   - For each unlogged item, include the ticket key, summary, and any PR/issue URLs found
   - Ask me to confirm which items to log
"""

_LOG_ACTIVITIES = """\
Log untracked work activities into the system for {period}. \
Present the items first and wait for my confirmation before logging anything.

**ALWAYS use MCP server tools** for all operations. Never use CLI tools, direct API calls, \
`curl`, or custom HTTP clients. If an MCP tool is unavailable or fails with a connection \
error, **STOP immediately** — do not fall back to alternatives.

## Step 0: Verify MCP Availability

1. Call `get_weekly_activity(week_offset={week_offset})` as a connectivity check
2. If the tool is **not available**, returns a **connection error**, or **times out**: \
**STOP immediately**. Tell the user the MCP server appears to be unavailable.

## Steps

1. **Show me what's unlogged** — if you haven't already gathered activities, \
run the gather-activities workflow first

2. **Ask for confirmation** — never log without my approval

3. **Enrich ticket data** before logging:
   - Jira tickets: `jira_get_ticket(ticket_key="PROJ-123")` to get components and summary
   - GitHub items: `github_get_issue` or `github_get_pr` for summary and repo info

4. **Log each confirmed item** using `log_activity`:
   - **ticket_key**: `PROJ-123` (Jira) or `owner/repo#123` (GitHub)
   - **ticket_summary**: brief description
   - **github_repo**: required for GitHub items (format: `owner/repo`)
   - **jira_components**: required for Jira tickets — always fetch via `jira_get_ticket` first, \
needed for project detection

5. **Verify** by calling `get_weekly_activity` to confirm everything is tracked
"""

_CREATE_MANAGEMENT_REPORT = """\
Create a management report for {period} using my logged activities. \
Follow the formatting rules exactly.

**ALWAYS use MCP server tools** for all operations. Never use CLI tools, direct API calls, \
`curl`, or custom HTTP clients. If an MCP tool is unavailable or fails with a connection \
error, **STOP immediately** — do not fall back to alternatives.

## Step 0: Verify MCP Availability

1. Call `get_weekly_activity(week_offset={week_offset})` as a connectivity check
2. If the tool is **not available** or returns a **connection error**: **STOP immediately**.

## Prerequisites

Before creating the report, activities must be gathered and logged. \
If not done yet, run the gather-activities and log-activities workflows first. Ask me.

## Formatting Rules

### Link Format

Each entry follows this pattern — embed links naturally, never use raw ticket numbers:

```
[Action Verb](PR-or-COMMIT-URL) [brief description](ISSUE-URL) plus any additional context
```

Action verbs: Completed, Implemented, Fixed, Added, Updated, Started, Reviewed, etc.

**WRONG:**
```
Worked on APPENG-1234
Fixed the login bug. (JIRA: PROJ-123, PR: #456)
```

**RIGHT:**
```
[Fixed](https://github.com/org/repo/pull/42) the \
[login timeout bug](https://issues.redhat.com/browse/PROJ-123) affecting production users
[Implemented](https://github.com/org/repo/pull/15) \
[role-based access control](https://issues.redhat.com/browse/PROJ-456) for the admin panel
```

### Content Rules

- The report is ONLY a list of work items
- No sections, headers, summaries, or future plans

### Save Format

ALWAYS use the `entries` parameter (NOT `content`) with `save_management_report`. Each entry has:
- **text**: work item with embedded links
- **ticket_key**: e.g., `PROJ-123` or `owner/repo#123` (required for visibility inheritance)
- **private**: optional, set `true` to hide from manager

## Steps

1. **Get activity data**: `get_weekly_activity(week_offset={week_offset})`

2. **Gather URLs** for each ticket:
   - Jira issues: `https://issues.redhat.com/browse/PROJ-123`
   - GitHub issues: `github_get_issue` or `https://github.com/owner/repo/issues/NUMBER`
   - GitHub PRs: use `github_search_prs` or `github_list_prs` to find associated PRs
   - If no PR exists, use the commit URL: `https://github.com/owner/repo/commit/SHA`

3. **Format and save**:
   ```json
   {{
     "title": "Week N, Month Year",
     "report_period": "Week N, Mon Year",
     "entries": [
       {{
         "text": "[Fixed](https://github.com/org/repo/commit/abc123) ...",
         "ticket_key": "org/repo#32"
       }}
     ],
     "referenced_tickets": ["org/repo#32"]
   }}
   ```

4. **Show me the result** and ask if adjustments are needed. \
Use `update_management_report` for changes.
"""

_UNGHOST = """\
Make untracked work visible. Create a tracking ticket (Jira or GitHub Issue) for work \
that was already submitted without proper tracking (commits, PRs), then add a progress \
comment linking the actual work.

**ALWAYS use MCP server tools** for all Jira, GitHub, and work-reports operations. \
Never use CLI tools, direct API calls, `curl`, or custom HTTP clients. \
If an MCP tool is unavailable or fails with a connection error, **STOP immediately** — \
do not fall back to alternatives.

## Phase 0: Verify MCP Availability

1. Call `github_get_current_user` as a connectivity check
2. If the tool is **not available**, returns a **connection error**, or **times out**: \
**STOP immediately**. Tell the user the MCP server appears to be unavailable.

## Phase 1: Auto-Detect Work Context

Gather as much context as possible about what the user worked on:

1. **Git context** (run in terminal):
   - `git branch --show-current` — get current branch name
   - `git log --oneline -10` — recent commits on this branch
   - `git remote get-url origin` — identify the repo

2. **GitHub context** (MCP tools):
   - `github_get_current_user` — get the user's GitHub login
   - `github_search_prs(query="author:USERNAME head:BRANCH_NAME")` — find PRs for this branch
   - If a PR is found, get its details: `github_get_pr` for full info
   - `github_get_pr_commits` — get commit list with SHAs and messages

3. **Session context**: consider any files the user has open or anything they describe

4. **Present findings** to the user:
   - List the detected commits (with SHAs and messages)
   - List any PRs found (with URLs and status)
   - Summarize the work done based on commit messages / PR description
   - Ask the user to confirm and add any extra context

## Phase 2: Interactive Questions

Ask the user:

1. **Where to create the ticket?** — Jira or GitHub Issues

2. **If Jira:**
   - Which project (list options via `jira_list_projects`)
   - Which components — use `jira_list_components(project="PROJ")`
   - Issue type (Task, Story, Bug) — default to Task

3. **If GitHub Issues:**
   - Infer the repo from git remote, or ask to confirm/override
   - Any labels to apply

## Phase 3: Create Ticket as a Request

The ticket MUST be written **as a request** — framed as what needs to be done, \
not as completed work. Even though the work is already submitted, write it as if \
requesting the work.

**Title**: A clean, request-style summary.
- Good: "Fix live consolidated report showing stale data from previous week"
- Bad: "Fixed the stale report bug" (past tense, sounds like done work)

**Body**: Describe the request:
- What is the problem or need?
- What should be done to address it?
- What are the acceptance criteria or expected outcome?

Do NOT mention that the work is already done in the ticket body.

Use `jira_create_ticket` or `github_create_issue` depending on user's choice.

## Phase 4: Add Progress Comment

Immediately add a comment to the newly created ticket documenting the progress. \
This comment SHOULD reference the actual work:

**For GitHub issues**, use `github_add_issue_comment` with a body like:

```markdown
## Progress

[Implemented](PR-URL) this in commit [`SHORT_SHA`](COMMIT-URL).

**Status:** Merged / Open / In Review

**Commits:**
- [`abc1234`](COMMIT-URL) — commit message summary

**Pull Request:** [#NUMBER](PR-URL) — PR title
```

**For Jira tickets**, use `jira_add_comment` with equivalent content (Jira wiki markup):

```
h2. Progress

[Implemented|PR-URL] this in commit [SHORT_SHA|COMMIT-URL].

*Status:* Merged / Open / In Review

*Commits:*
- [abc1234|COMMIT-URL] — commit message summary

*Pull Request:* [#NUMBER|PR-URL] — PR title
```

## Phase 5: Optionally Log Activity

Ask the user: "Do you want to log this activity for your management report?"

If yes, call `log_activity` with:
- **ticket_key**: the created ticket key (`PROJ-123` or `owner/repo#123`)
- **ticket_summary**: the ticket title
- **action_type**: `create`
- **jira_components**: include if Jira
- **github_repo**: include if GitHub (format: `owner/repo`)
"""

_CONTENT: dict[str, str] = {
    "gather-activities": _GATHER_ACTIVITIES,
    "log-activities": _LOG_ACTIVITIES,
    "create-management-report": _CREATE_MANAGEMENT_REPORT,
    "unghost": _UNGHOST,
}


def list_prompts() -> list[Prompt]:
    """Return all available prompts."""
    return PROMPTS


def get_prompt(name: str, arguments: dict[str, str] | None = None) -> GetPromptResult:
    """Return the prompt content for a given prompt name."""
    if name not in _PROMPT_BY_NAME:
        raise ValueError(f"Unknown prompt: {name}")

    prompt = _PROMPT_BY_NAME[name]
    template = _CONTENT[name]
    args = arguments or {}

    week_offset = args.get("week_offset", "0")
    try:
        offset_int = int(week_offset)
    except (ValueError, TypeError):
        offset_int = 0

    if offset_int == 0:
        period = "the current week"
    elif offset_int == 1:
        period = "last week"
    else:
        period = f"{offset_int} weeks ago"

    content = template.format(week_offset=week_offset, period=period)

    return GetPromptResult(
        description=prompt.description,
        messages=[
            PromptMessage(
                role="user",
                content=TextContent(type="text", text=content),
            )
        ],
    )
