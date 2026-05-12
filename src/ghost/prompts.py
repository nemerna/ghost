"""MCP Prompts for Ghost workflows.

These prompts are exposed via the Reports MCP server and appear as
slash-commands (/commands) in clients like Cursor.
"""

from mcp.types import GetPromptResult, Prompt, PromptArgument, PromptMessage, TextContent

PROMPTS: list[Prompt] = [
    Prompt(
        name="create-management-report",
        title="Create Management Report",
        description=(
            "Discover work done in Jira and GitHub, then create a formatted management report directly from the findings."
        ),
        arguments=[
            PromptArgument(
                name="days",
                description="How many days back to include in the report (e.g. 7). Defaults to 7.",
                required=False,
            ),
        ],
    ),
    Prompt(
        name="unghost",
        title="Unghost (Track Untracked Work)",
        description=(
            "Create a tracking ticket (via Atlassian Jira or GitHub Issue) for work that was already "
            "submitted without proper tracking, then add a progress comment linking the actual work."
        ),
    ),
    Prompt(
        name="weekly-report",
        title="Weekly Report (End-to-End)",
        description=(
            "Complete end-to-end workflow: discover work from Jira and GitHub, "
            "then create a formatted management report — all in one go."
        ),
        arguments=[
            PromptArgument(
                name="days",
                description="How many days back to cover (e.g. 7 for the last week). Defaults to 7.",
                required=False,
            ),
        ],
    ),
]

_PROMPT_BY_NAME: dict[str, Prompt] = {p.name: p for p in PROMPTS}

# ---------------------------------------------------------------------------
# Prompt content
# ---------------------------------------------------------------------------

_CREATE_MANAGEMENT_REPORT = """\
Create a management report for {period}. \
Discover work done in Jira and GitHub, then build the report directly from the findings.

**ALWAYS use MCP server tools** for all Jira, GitHub, and work-reports operations. \
Never use CLI tools (`gh`, `jira-cli`), direct API calls, `curl`, or custom HTTP clients. \
If an MCP tool is unavailable or fails with a connection error, **STOP immediately** — \
do not fall back to alternatives.

**Tool servers**: Jira tools (`searchJiraIssuesUsingJql`, `getJiraIssue`, `atlassianUserInfo`) \
come from the **Atlassian MCP** server. GitHub tools (`github_*`) and Reports tools \
(`save_management_report`, `update_management_report`, `list_report_fields`) come from the \
**Ghost MCP** server.

## Step 0: Verify MCP Availability

Before doing anything, confirm both MCP servers are reachable (run in parallel):

1. `github_get_current_user` (Ghost MCP) — GitHub connectivity + get my username
2. `atlassianUserInfo` (Atlassian MCP) — Jira connectivity + get my user info

If either tool is **not available**, returns a **connection error**, or **times out**: \
**STOP immediately**. Tell me:
> "An MCP server appears to be unavailable. Please check that the Ghost and Atlassian \
MCP servers are running and that your MCP configuration is correct."

## Step 1: Discover work

Run the following in parallel:

1. **Search Jira** for my tickets:
   - Use `searchJiraIssuesUsingJql` (Atlassian MCP) with JQL like: \
`assignee = currentUser() AND updated >= 'YYYY-MM-DD' ORDER BY updated DESC`
   - Scope to the target period

2. **Search GitHub** for my activity:
   - `github_search_prs(query="author:USERNAME updated:>=YYYY-MM-DD")`
   - `github_search_issues(query="author:USERNAME updated:>=YYYY-MM-DD")`
   - `list_report_fields` — check configured repos/projects

## Step 2: Enrich every ticket

**For every Jira ticket** found, call `getJiraIssue` (Atlassian MCP) to get:
- `url` — the canonical browse URL (**NEVER fabricate or guess a Jira URL**)
- `summary` — the ticket title
- `components` — component names (used for project auto-detection in the report)

**For GitHub items**, use the URL and title from the search results directly.

## Step 3: Match PRs to Jira tickets

Only when there is an **explicit reference**:
- Ticket key appears in PR branch name (e.g. `feature/PROJ-123-fix-login`)
- Ticket key appears in PR title or PR body

**NEVER match by time proximity alone.** If no explicit reference exists, \
treat them as separate work items.

## Step 4: Build entries and save the report

### Formatting Rules

Each entry follows this pattern — embed links naturally, never use raw ticket numbers:

```
[Action Verb](PR-or-COMMIT-URL) [brief description](ISSUE-URL) plus any additional context
```

Action verbs: Completed, Implemented, Fixed, Added, Updated, Started, Reviewed, etc.

**WRONG — raw ticket numbers, no links:**
```
Worked on APPENG-1234
Fixed the login bug. (JIRA: PROJ-123, PR: #456)
```

**WRONG — links only, no description of the actual work:**
```
[Fixed](https://github.com/org/repo/pull/42) [PROJ-123](https://redhat.atlassian.net/browse/PROJ-123)
```

**RIGHT — links embedded in a human-readable sentence describing what was done:**
```
[Fixed](https://github.com/org/repo/pull/42) the \
[login timeout bug](https://redhat.atlassian.net/browse/PROJ-123) affecting production users
[Implemented](https://github.com/org/repo/pull/15) \
[role-based access control](https://redhat.atlassian.net/browse/PROJ-456) for the admin panel
```

Every entry MUST read as a complete, meaningful sentence describing what was accomplished. \
A manager reading the report should understand the work without clicking any links.

**Building URLs — CRITICAL RULES**
- **Jira URLs**: MUST use the URL from `getJiraIssue` response. **NEVER fabricate or guess.**
- **GitHub URLs**: Use URLs from search results or construct from known patterns: \
`https://github.com/owner/repo/pull/NUMBER` or `https://github.com/owner/repo/issues/NUMBER`.

**Content Rules**
- The report is ONLY a list of work items
- No sections, headers, summaries, or future plans

### Save Format

ALWAYS use the `entries` parameter (NOT `content`) with `save_management_report`. Each entry has:
- **text**: work item with embedded links
- **ticket_key**: e.g., `PROJ-123` or `owner/repo#123` (required for project auto-detection)
- **private**: optional, set `true` to hide from manager

Save the report:
```json
{{
  "title": "Week N, Month Year",
  "report_period": "Week N, Mon Year",
  "entries": [
    {{
      "text": "[Fixed](https://github.com/org/repo/pull/42) the [login timeout bug](https://redhat.atlassian.net/browse/PROJ-123) affecting production users",
      "ticket_key": "PROJ-123"
    }}
  ],
  "referenced_tickets": ["PROJ-123", "org/repo#32"]
}}
```

## Step 5: Show result

Show me the report and ask if adjustments are needed. \
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

**Tool servers**: Jira tools (`createJiraIssue`, `addCommentToJiraIssue`, etc.) come from \
the **Atlassian MCP**. GitHub tools (`github_*`) come from the **Ghost MCP**.

## Phase 0: Verify MCP Availability

1. Call `github_get_current_user` (Ghost MCP) as a connectivity check
2. If the tool is **not available**, returns a **connection error**, or **times out**: \
**STOP immediately**. Tell the user the MCP server appears to be unavailable.

## Phase 1: Auto-Detect Work Context

Gather as much context as possible about what the user worked on:

1. **Git context** (run in terminal):
   - `git branch --show-current` — get current branch name
   - `git log --oneline -10` — recent commits on this branch
   - `git remote get-url origin` — identify the repo

2. **GitHub context** (Ghost MCP):
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
   - Which project — call `getVisibleJiraProjects` (Atlassian MCP) to list options
   - Which components — call `getJiraIssue` (Atlassian MCP) on an existing ticket in that \
project to see available components, or ask the user
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

Use `createJiraIssue` (Atlassian MCP) or `github_create_issue` (Ghost MCP) \
depending on user's choice.

## Phase 4: Add Progress Comment

Immediately add a comment to the newly created ticket documenting the progress. \
This comment SHOULD reference the actual work:

**For GitHub issues**, use `github_add_issue_comment` (Ghost MCP) with a body like:

```markdown
## Progress

[Implemented](PR-URL) this in commit [`SHORT_SHA`](COMMIT-URL).

**Status:** Merged / Open / In Review

**Commits:**
- [`abc1234`](COMMIT-URL) — commit message summary

**Pull Request:** [#NUMBER](PR-URL) — PR title
```

**For Jira tickets**, use `addCommentToJiraIssue` (Atlassian MCP) with Markdown content:

```markdown
## Progress

[Implemented](PR-URL) this in commit [`SHORT_SHA`](COMMIT-URL).

**Status:** Merged / Open / In Review

**Commits:**
- [`abc1234`](COMMIT-URL) — commit message summary

**Pull Request:** [#NUMBER](PR-URL) — PR title
```
"""

_WEEKLY_REPORT = """\
Create my complete weekly management report for {period} — end-to-end. \
Discover work from Jira and GitHub, then produce a formatted report.

**ALWAYS use MCP server tools** for all Jira, GitHub, and work-reports operations. \
Never use CLI tools (`gh`, `jira-cli`), direct API calls, `curl`, or custom HTTP clients. \
If an MCP tool is unavailable or fails with a connection error, **STOP immediately** — \
do not fall back to alternatives.

**Tool servers**: Jira tools (`searchJiraIssuesUsingJql`, `getJiraIssue`, `atlassianUserInfo`) \
come from the **Atlassian MCP** server. GitHub tools (`github_*`) and Reports tools \
(`save_management_report`, `update_management_report`, `list_report_fields`) come from the \
**Ghost MCP** server.

## Step 0: Verify MCP Availability

Before doing anything, confirm both MCP servers are reachable (run in parallel):

1. `github_get_current_user` (Ghost MCP) — GitHub connectivity + get my username
2. `atlassianUserInfo` (Atlassian MCP) — Jira connectivity + get my user info

If either tool is **not available**, returns a **connection error**, or **times out**: \
**STOP immediately**. Tell me:
> "An MCP server appears to be unavailable. Please check that the Ghost and Atlassian \
MCP servers are running and that your MCP configuration is correct."

**Do NOT attempt CLI tools, direct API calls, or any alternative.**

---

## Phase 1: Discover Work

Run the following in parallel:

1. **Search Jira** for my tickets:
   - Use `searchJiraIssuesUsingJql` (Atlassian MCP) with JQL like: \
`assignee = currentUser() AND updated >= 'YYYY-MM-DD' AND updated <= 'YYYY-MM-DD' \
ORDER BY updated DESC` — scope to the target period
   - Filter by the target date range

2. **Search GitHub** for my activity:
   - `github_search_prs(query="author:USERNAME updated:>=YYYY-MM-DD")` — PRs in the period
   - `github_search_issues(query="author:USERNAME updated:>=YYYY-MM-DD")` — issues
   - `list_report_fields` — check configured repos/projects

3. **Enrich EVERY Jira ticket** — call `getJiraIssue` (Atlassian MCP) for each one to get:
   - `url` — the canonical browse URL (**NEVER fabricate or guess a Jira URL**)
   - `summary` — the ticket title
   - `components` — component names (used for project auto-detection in the report)

4. **Match PRs to Jira tickets** — only by explicit reference:
   - Check PR branch name for ticket key (e.g. `feature/PROJ-123-fix-login`)
   - Check PR title and body for ticket key mentions
   - **NEVER match by time proximity alone.** If no explicit reference exists, \
treat them as separate work items.

5. **Present findings** to me:
   - All discovered Jira tickets and GitHub work items with keys, summaries, and URLs
   - PR-to-ticket matches with evidence (branch name, PR body reference)
   - **Ask me to confirm** the list before building the report

---

## Phase 2: Build and Save the Report

### Entry format

Each entry follows this pattern — embed links naturally, never use raw ticket numbers:

```
[Action Verb](PR-or-COMMIT-URL) [brief description](ISSUE-URL) plus context
```

Action verbs: Completed, Implemented, Fixed, Added, Updated, Started, Reviewed, etc.

**WRONG — raw ticket numbers, no links:**
```
Worked on APPENG-1234
Fixed the login bug. (JIRA: PROJ-123, PR: #456)
```

**WRONG — links only, no description of the actual work:**
```
[Fixed](https://github.com/org/repo/pull/42) [PROJ-123](https://redhat.atlassian.net/browse/PROJ-123)
```

**RIGHT — links embedded in a human-readable sentence describing what was done:**
```
[Fixed](https://github.com/org/repo/pull/42) the \
[login timeout bug](https://redhat.atlassian.net/browse/PROJ-123) affecting production users
```

Every entry MUST read as a complete, meaningful sentence. A manager reading the report \
should understand what was accomplished without clicking any links.

**Content rules**:
- The report is ONLY a list of work items
- No sections, headers, summaries, or future plans

### Save the report

Use `save_management_report` (Ghost MCP) with the `entries` parameter (NOT `content`):
```json
{{
  "title": "Week N, Month Year",
  "report_period": "Week N, Mon Year",
  "entries": [
    {{
      "text": "[Fixed](https://github.com/org/repo/pull/42) the [login timeout bug](https://redhat.atlassian.net/browse/PROJ-123) affecting production users",
      "ticket_key": "PROJ-123"
    }},
    {{
      "text": "[Reviewed](https://github.com/org/repo/pull/55) the [CI pipeline improvements](https://github.com/org/repo/issues/50)",
      "ticket_key": "org/repo#50"
    }}
  ],
  "referenced_tickets": ["PROJ-123", "org/repo#50"]
}}
```

### Show result

Show me the report and ask if adjustments are needed. \
Use `update_management_report` for any changes.
"""

_CONTENT: dict[str, str] = {
    "create-management-report": _CREATE_MANAGEMENT_REPORT,
    "unghost": _UNGHOST,
    "weekly-report": _WEEKLY_REPORT,
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

    days_str = args.get("days", "7")
    try:
        days = max(1, int(days_str))
    except (ValueError, TypeError):
        days = 7

    if days <= 1:
        period = "today"
    elif days == 7:
        period = "the last 7 days"
    elif days == 14:
        period = "the last 2 weeks"
    else:
        period = f"the last {days} days"

    content = template.format(days=days, period=period)

    return GetPromptResult(
        description=prompt.description,
        messages=[
            PromptMessage(
                role="user",
                content=TextContent(type="text", text=content),
            )
        ],
    )
