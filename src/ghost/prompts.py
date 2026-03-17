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
            "Discover all work done during a period by checking Jira and GitHub, "
            "then compare against what's already logged."
        ),
        arguments=[
            PromptArgument(
                name="days",
                description="How many days back to look (e.g. 7 for the last week, 14 for last two weeks). Defaults to 7.",
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
                name="days",
                description="How many days back to log activities for (e.g. 7). Defaults to 7.",
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
            "Complete end-to-end workflow: gather activities from Jira and GitHub, "
            "log untracked items, and create a formatted management report — all in one go."
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

_GATHER_ACTIVITIES = """\
Discover all work I did during {period} by checking Jira and GitHub. \
Compare against what's already logged.

**ALWAYS use MCP server tools** for all Jira, GitHub, and work-reports operations. \
Never use CLI tools (`gh`, `jira-cli`), direct API calls, `curl`, or custom HTTP clients. \
If an MCP tool is unavailable or fails with a connection error, **STOP immediately** — \
do not fall back to alternatives. Inform the user that the MCP server appears to be down \
and suggest checking the server status.

**Tool servers**: Jira tools (`searchJiraIssuesUsingJql`, `getJiraIssue`, etc.) come from the \
**Atlassian MCP** server. GitHub tools (`github_*`) and Reports tools (`log_activity`, \
`get_weekly_activity`, etc.) come from the **Ghost MCP** server.

## Step 0: Verify MCP Availability

Before doing anything else, verify that the MCP servers are reachable:

1. Call `github_get_current_user` (Ghost) as a GitHub connectivity check
2. Call `atlassianUserInfo` (Atlassian) as a Jira connectivity check
3. If either tool is **not available**, returns a **connection error**, or **times out**: \
**STOP immediately**. Tell the user:
   > "An MCP server appears to be unavailable. Please check that the Ghost and Atlassian \
MCP servers are running and that your MCP configuration is correct."
4. **Do NOT attempt to use CLI tools, direct API calls, or any alternative.** \
This workflow requires MCP tools — there is no fallback.

## Steps

1. **Identify me** on both platforms (run in parallel):
   - `atlassianUserInfo` (Atlassian MCP) — returns my Atlassian account info
   - `github_get_current_user` (Ghost MCP)

2. **Check what's already logged**:
   - `get_weekly_activity(days={days})`
   - Note the `unique_tickets` list — these are already tracked

3. **Search Jira** for my tickets:
   - Use `searchJiraIssuesUsingJql` (Atlassian MCP) with JQL like: \
`assignee = currentUser() AND status IN ('In Progress', 'Done', 'In Review') ORDER BY updated DESC`
   - Filter results by the `updated` field to only include tickets updated within the target week
   - Compare against already-logged tickets to find gaps

4. **Enrich every Jira ticket** — for each Jira ticket found (both logged and unlogged), \
call `getJiraIssue` (Atlassian MCP) with the issue key to retrieve:
   - **`url`** — the canonical browse URL (e.g. `https://issues.redhat.com/browse/PROJ-123`)
   - **`summary`** — the ticket title/description
   - **`components`** — component names (needed later for project detection when logging)
   - **NEVER fabricate or guess a Jira URL.** Always use the URL from `getJiraIssue`.

5. **Search GitHub** for my activity:
   - `github_search_prs(query="author:USERNAME updated:>=YYYY-MM-DD")` — PRs in the period
   - `github_search_issues(query="author:USERNAME updated:>=YYYY-MM-DD")` — issues in the period
   - `list_report_fields` — check configured repos to know where to look
   - Compare against already-logged tickets to find gaps

6. **Match PRs to Jira tickets** — only when there is an explicit reference:
   - Check PR branch name for a ticket key (e.g. `feature/PROJ-123-fix-login`)
   - Check PR title and body for ticket key mentions (e.g. "Fixes PROJ-123")
   - **Do NOT match by time proximity alone.** If no explicit reference links a PR to a \
Jira ticket, treat them as separate work items.

7. **Present findings**:
   - **Already tracked**: activities in the system
   - **Not yet logged**: work found in Jira/GitHub that hasn't been logged
   - For each unlogged item, include the ticket key, summary, and the actual URL from the \
source system (Jira `url` field or GitHub URL)
   - Show any PR-to-ticket links found (with the evidence: branch name, PR body reference)
   - Ask me to confirm which items to log
"""

_LOG_ACTIVITIES = """\
Log untracked work activities into the system for {period}. \
Present the items first and wait for my confirmation before logging anything.

**ALWAYS use MCP server tools** for all operations. Never use CLI tools, direct API calls, \
`curl`, or custom HTTP clients. If an MCP tool is unavailable or fails with a connection \
error, **STOP immediately** — do not fall back to alternatives.

**Tool servers**: Jira tools (`getJiraIssue`, etc.) come from the **Atlassian MCP**. \
Reports tools (`log_activity`, `get_weekly_activity`) come from the **Ghost MCP**.

## Step 0: Verify MCP Availability

1. Call `get_weekly_activity(days={days})` as a connectivity check
2. If the tool is **not available**, returns a **connection error**, or **times out**: \
**STOP immediately**. Tell the user the MCP server appears to be unavailable.

## Steps

1. **Show me what's unlogged** — if you haven't already gathered activities, \
run the gather-activities workflow first

2. **Ask for confirmation** — never log without my approval

3. **Enrich every ticket** before logging — this is **mandatory**, not optional:
   - For **every Jira ticket**: call `getJiraIssue` (Atlassian MCP) with the issue key \
to get the issue's **components**, **summary**, and **url**
   - For **every GitHub item**: call `github_get_issue` or `github_get_pr` (Ghost MCP) to \
get summary, repo, and URL
   - **NEVER skip enrichment.** Without `jira_components`, project auto-detection will fail.
   - **NEVER fabricate or guess URLs.** Always use the URL from `getJiraIssue`.

4. **Log each confirmed item** using `log_activity` (Ghost MCP) with ALL fields:
   - **ticket_key**: `PROJ-123` (Jira) or `owner/repo#123` (GitHub)
   - **ticket_summary**: the summary from the enrichment call — **REQUIRED**, never leave blank
   - **ticket_url**: the canonical browse URL from `getJiraIssue` response (Jira) or \
the GitHub issue/PR URL — **REQUIRED**, this is stored and used in the UI and reports
   - **github_repo**: required for GitHub items (format: `owner/repo`)
   - **jira_components**: **REQUIRED for Jira tickets** — pass the component names from \
`getJiraIssue` response as a list of strings. Without this, the system cannot \
automatically detect which project/field this ticket belongs to.

5. **Verify** by calling `get_weekly_activity` to confirm everything is tracked
"""

_CREATE_MANAGEMENT_REPORT = """\
Create a management report for {period} using my logged activities. \
Follow the formatting rules exactly.

**ALWAYS use MCP server tools** for all operations. Never use CLI tools, direct API calls, \
`curl`, or custom HTTP clients. If an MCP tool is unavailable or fails with a connection \
error, **STOP immediately** — do not fall back to alternatives.

**Tool servers**: Jira tools (`getJiraIssue`) come from the **Atlassian MCP**. \
GitHub tools (`github_*`) and Reports tools come from the **Ghost MCP**.

## Step 0: Verify MCP Availability

1. Call `get_weekly_activity(days={days})` as a connectivity check
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

**WRONG — raw ticket numbers, no links:**
```
Worked on APPENG-1234
Fixed the login bug. (JIRA: PROJ-123, PR: #456)
```

**WRONG — links only, no description of the actual work:**
```
[Fixed](https://github.com/org/repo/pull/42) [PROJ-123](https://issues.redhat.com/browse/PROJ-123)
[Updated](https://github.com/org/repo/pull/15) [PROJ-456](https://issues.redhat.com/browse/PROJ-456)
```

**RIGHT — links embedded in a human-readable sentence describing what was done:**
```
[Fixed](https://github.com/org/repo/pull/42) the \
[login timeout bug](https://issues.redhat.com/browse/PROJ-123) affecting production users
[Implemented](https://github.com/org/repo/pull/15) \
[role-based access control](https://issues.redhat.com/browse/PROJ-456) for the admin panel
```

Every entry MUST read as a complete, meaningful sentence. The link text should describe \
the work (e.g. "login timeout bug", "role-based access control"), NOT just the ticket key. \
A manager reading the report should understand what was accomplished without clicking any links.

### Building URLs — CRITICAL RULES

- **Jira URLs**: For EVERY Jira ticket, you MUST call `getJiraIssue` \
(Atlassian MCP) with the issue key and use the URL from the response. \
**NEVER fabricate, guess, or construct Jira URLs manually.** The actual URL structure \
varies by instance and you cannot assume a pattern.
- **GitHub URLs**: Use the URLs returned by `github_get_issue`, `github_get_pr`, or \
construct from known patterns: `https://github.com/owner/repo/pull/NUMBER` or \
`https://github.com/owner/repo/issues/NUMBER`.
- If a URL cannot be obtained from an MCP tool, **omit the link** rather than guessing.

### PR-to-Ticket Matching — CRITICAL RULES

When associating GitHub PRs with Jira tickets:
- **Only match when there is an explicit reference**: the Jira ticket key appears in the \
PR branch name (e.g. `feature/PROJ-123-fix-login`), PR title, or PR body
- **NEVER match by time proximity alone.** Two items updated in the same week does NOT \
mean they are related.
- If no confident match is found, use the Jira URL alone (no PR link) for Jira entries, \
and create a separate entry for the PR as standalone GitHub work.

### Content Rules

- The report is ONLY a list of work items
- No sections, headers, summaries, or future plans

### Save Format

ALWAYS use the `entries` parameter (NOT `content`) with `save_management_report`. Each entry has:
- **text**: work item with embedded links
- **ticket_key**: e.g., `PROJ-123` or `owner/repo#123` (required for visibility inheritance)
- **private**: optional, set `true` to hide from manager

## Steps

1. **Get activity data**: `get_weekly_activity(days={days})`
   - Each ticket in `unique_tickets` now includes a `ticket_url` field (stored at log time)
   - If `ticket_url` is present and non-null, you can use it directly — no need to re-fetch

2. **Enrich tickets with missing data** — for tickets where `ticket_url` or `ticket_summary` \
is null/missing:
   - **Jira tickets**: call `getJiraIssue` (Atlassian MCP) with the issue key to get:
     - URL — the canonical browse URL (use this, never fabricate)
     - `summary` — use if `ticket_summary` is null
     - `components` — for reference
   - **GitHub items**: call `github_get_issue` or `github_get_pr` (Ghost MCP) to get the \
URL and summary
   - If `ticket_url` is already present from activity data, skip re-fetching for that ticket.

3. **Find associated PRs** — search for PRs related to each ticket:
   - `github_search_prs(query="PROJ-123")` — search by ticket key
   - Only use a PR if the ticket key appears in the branch name, PR title, or PR body
   - If no PR is found or no confident match exists, that's fine — use the issue URL only

4. **Format entries** using the enriched data:
   - Use the URL from `getJiraIssue` for Jira links (never construct manually)
   - Use the `summary` for the description text
   - Embed PR links only when confidently matched to the ticket

5. **Save the report**:
   ```json
   {{
     "title": "Week N, Month Year",
     "report_period": "Week N, Mon Year",
     "entries": [
       {{
         "text": "[Fixed](https://github.com/org/repo/pull/42) the [login timeout bug](https://issues.redhat.com/browse/PROJ-123) affecting production users",
         "ticket_key": "PROJ-123"
       }}
     ],
     "referenced_tickets": ["PROJ-123", "org/repo#32"]
   }}
   ```

6. **Show me the result** and ask if adjustments are needed. \
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
the **Atlassian MCP**. GitHub tools (`github_*`) and Reports tools (`log_activity`) come \
from the **Ghost MCP**.

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

## Phase 5: Optionally Log Activity

Ask the user: "Do you want to log this activity for your management report?"

If yes, and the ticket is a Jira ticket, first call \
`getJiraIssue` (Atlassian MCP) with the issue key to get the **components**, \
**summary**, and **url**. Then call `log_activity` (Ghost MCP) with ALL fields:
- **ticket_key**: the created ticket key (`PROJ-123` or `owner/repo#123`)
- **ticket_summary**: the ticket title — **REQUIRED**, never leave blank
- **ticket_url**: the URL from `getJiraIssue` or the GitHub issue URL — **REQUIRED**
- **action_type**: `create`
- **jira_components**: component names from `getJiraIssue` response — **REQUIRED for \
Jira tickets** (needed for automatic project/field detection)
- **github_repo**: include if GitHub (format: `owner/repo`)

**NEVER fabricate Jira URLs.** Always get them from `getJiraIssue`.
"""

_WEEKLY_REPORT = """\
Create my complete weekly management report for {period} — end-to-end. \
Gather activities, log anything untracked, and produce a formatted report.

**ALWAYS use MCP server tools** for all Jira, GitHub, and work-reports operations. \
Never use CLI tools (`gh`, `jira-cli`), direct API calls, `curl`, or custom HTTP clients. \
If an MCP tool is unavailable or fails with a connection error, **STOP immediately** — \
do not fall back to alternatives.

**Tool servers**: Jira tools (`searchJiraIssuesUsingJql`, `getJiraIssue`, `atlassianUserInfo`) \
come from the **Atlassian MCP** server. GitHub tools (`github_*`) and Reports tools \
(`log_activity`, `get_weekly_activity`, `save_management_report`, etc.) come from the \
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

## Phase 1: Gather Activities

1. **Check what's already logged**:
   - `get_weekly_activity(days={days})`
   - Note the `unique_tickets` list — these are already tracked

2. **Search Jira** for my tickets:
   - Use `searchJiraIssuesUsingJql` (Atlassian MCP) with JQL like: \
`assignee = currentUser() AND updated >= 'YYYY-MM-DD' AND updated <= 'YYYY-MM-DD' \
ORDER BY updated DESC` — scope to the target week
   - Compare against already-logged tickets to find unlogged items

3. **Search GitHub** for my activity:
   - `github_search_prs(query="author:USERNAME updated:>=YYYY-MM-DD")` — PRs in the period
   - `github_search_issues(query="author:USERNAME updated:>=YYYY-MM-DD")` — issues
   - `list_report_fields` — check configured repos/projects
   - Compare against already-logged tickets to find unlogged items

4. **Enrich EVERY Jira ticket** (both logged and newly found) — call \
`getJiraIssue` (Atlassian MCP) with the issue key for each one to get:
   - `url` — the canonical browse URL (**NEVER fabricate or guess a Jira URL**)
   - `summary` — the ticket title
   - `components` — component names (needed for project auto-detection)

5. **Match PRs to Jira tickets** — only by explicit reference:
   - Check PR branch name for ticket key (e.g. `feature/PROJ-123-fix-login`)
   - Check PR title and body for ticket key mentions
   - **NEVER match by time proximity alone.** If no explicit reference exists, \
treat them as separate work items.

6. **Present findings** to me:
   - **Already tracked**: list of logged activities
   - **Not yet logged**: untracked items from Jira/GitHub with ticket key, summary, \
and URL from the source system
   - Show PR-to-ticket matches with evidence (branch name, PR body reference)
   - **Ask me to confirm** which unlogged items to track

---

## Phase 2: Log Untracked Activities

After I confirm which items to log:

1. For each confirmed **Jira ticket** — you should already have enrichment data from Phase 1. \
Call `log_activity` (Ghost MCP) with ALL fields:
   - **ticket_key**: `PROJ-123`
   - **ticket_summary**: summary from `getJiraIssue` — **REQUIRED**, never leave blank
   - **ticket_url**: the URL from `getJiraIssue` — **REQUIRED** (stored for UI links and reports)
   - **jira_components**: component names from `getJiraIssue` — **REQUIRED** (needed for \
automatic project/field detection)
   - **action_type**: appropriate type (e.g. `update`, `create`)

2. For each confirmed **GitHub item** — call `log_activity` (Ghost MCP) with:
   - **ticket_key**: `owner/repo#123`
   - **ticket_summary**: PR/issue title — **REQUIRED**
   - **ticket_url**: the GitHub issue or PR URL — **REQUIRED**
   - **github_repo**: `owner/repo` — **REQUIRED**
   - **action_type**: appropriate type

3. **Verify logging** — call `get_weekly_activity(days={days})` to confirm \
all items are now tracked.

---

## Phase 3: Create the Management Report

1. **Gather verified data** — you now have:
   - All activity data from `get_weekly_activity` (includes `ticket_url` and `ticket_summary` \
for each ticket — these were stored at log time)
   - Enriched Jira data (URL, summary, components) from Phase 1
   - GitHub URLs from Phase 1
   - PR-to-ticket matches from Phase 1

2. **Build entries** — for each unique ticket:
   - Use the `ticket_url` from activity data when available (it was stored at log time)
   - If `ticket_url` is null (older activities), use the enriched URL from Phase 1
   - Only embed PR links when confidently matched by explicit reference
   - If `ticket_summary` from activity data is null, use the enriched summary

3. **Entry format** — embed links naturally, never use raw ticket numbers:

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
[Fixed](https://github.com/org/repo/pull/42) [PROJ-123](https://issues.redhat.com/browse/PROJ-123)
```

**RIGHT — links embedded in a human-readable sentence describing what was done:**
```
[Fixed](https://github.com/org/repo/pull/42) the \
[login timeout bug](https://issues.redhat.com/browse/PROJ-123) affecting production users
```

- If a ticket has no associated PR, use just the issue URL:
```
[Updated](https://issues.redhat.com/browse/PROJ-456) deployment configuration for staging environment
```

Every entry MUST read as a complete, meaningful sentence. The link text should describe \
the work (e.g. "login timeout bug", "deployment configuration"), NOT just the ticket key. \
A manager reading the report should understand what was accomplished without clicking any links.

4. **Content rules**:
   - The report is ONLY a list of work items
   - No sections, headers, summaries, or future plans

5. **Save the report** using `save_management_report` (Ghost MCP) with the `entries` \
parameter (NOT `content`):
   ```json
   {{
     "title": "Week N, Month Year",
     "report_period": "Week N, Mon Year",
     "entries": [
       {{
         "text": "[Fixed](https://github.com/org/repo/pull/42) the [login timeout bug](https://issues.redhat.com/browse/PROJ-123) affecting production users",
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

6. **Show me the result** and ask if adjustments are needed. \
Use `update_management_report` for any changes.
"""

_CONTENT: dict[str, str] = {
    "gather-activities": _GATHER_ACTIVITIES,
    "log-activities": _LOG_ACTIVITIES,
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
