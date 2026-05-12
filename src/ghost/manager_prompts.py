"""MCP Prompts for manager workflows.

These prompts are exposed via the Manager MCP server and appear as
slash-commands (/commands) in clients like Cursor or Gemini.
Each prompt guides the LLM through a common manager task using the
manager_* tools available on this server.
"""

from mcp.types import GetPromptResult, Prompt, PromptMessage, TextContent

MANAGER_PROMPTS: list[Prompt] = [
    Prompt(
        name="team-weekly-summary",
        title="Team Weekly Summary",
        description=(
            "Interactive guided workflow: discovers available teams and periods, asks you to choose, "
            "then produces a narrative summary of the team's work organised by project/field."
        ),
    ),
    Prompt(
        name="team-reporting-status",
        title="Team Reporting Status",
        description=(
            "Interactive guided workflow: discovers available teams, asks which week to check, "
            "then shows who submitted / in progress / missing and drafts nudge messages."
        ),
    ),
    Prompt(
        name="member-activity",
        title="Member Activity Deep Dive",
        description=(
            "Interactive guided workflow: lists team members for you to choose from, "
            "then summarises that member's contribution history, patterns, and highlights."
        ),
    ),
    Prompt(
        name="cross-period-comparison",
        title="Cross-Period Comparison",
        description=(
            "Interactive guided workflow: discovers available periods from snapshots, asks you to pick two, "
            "then compares team work side-by-side highlighting changes and momentum shifts."
        ),
    ),
    Prompt(
        name="project-focus",
        title="Project Focus",
        description=(
            "Interactive guided workflow: lists available projects/fields and periods for you to choose from, "
            "then summarises all team contributions to that project."
        ),
    ),
]

_PROMPT_BY_NAME: dict[str, Prompt] = {p.name: p for p in MANAGER_PROMPTS}

# =============================================================================
# Prompt content templates
# =============================================================================

_TEAM_WEEKLY_SUMMARY = """\
Produce a narrative summary of your team's work. Follow the steps below exactly — \
gather context first, ask the user to choose, then fetch and write.

**ALWAYS use Manager MCP tools** for all data retrieval. \
Never call REST endpoints, CLI tools, or external services directly.

---

## Phase 1: Gather context (run in parallel)

Call these two tools simultaneously:
1. `manager_list_all_teams` — discover which team(s) are available
2. `manager_list_snapshots` with `limit`: 20 — discover available report periods

---

## Phase 2: Ask the user to choose

Present the following questions **one at a time** and **wait for the user's answer** before continuing.

**Question 1 — Team** (only ask if the previous step returned more than one team):
> Which team would you like to summarise?
> [List each team as a numbered option, e.g. "1. Platform Engineering  2. Infra  3. Frontend"]
> Record the chosen `team_id`.

**Question 2 — Report period:**
> Which period would you like to summarise?
> Provide these choices (extract unique `report_period` values from the snapshots, newest first):
> 1. Current week (live data — no period filter)
> 2. [period from snapshot 1]
> 3. [period from snapshot 2]
> … (up to 8 periods)
> N. Enter a custom period (I will type it)
> Record the chosen `report_period` (or `null` for current week).

---

## Phase 3: Fetch data (run in parallel)

1. `manager_get_consolidated_report` — use chosen `team_id` and `report_period`
2. `manager_list_report_fields` — get the field/project taxonomy

---

## Phase 4: Write the summary

### Team Weekly Summary — [Team Name] — [Period]

For each **Field** that has entries:
- Field name as a heading
- For each **Project**: 2–4 sentence description of the combined work, naming contributors

Add a short **Uncategorised** section if there are entries with no detected project.

End with a one-paragraph **Overall Highlights** capturing the most important team-wide themes.
Keep the tone professional and concise — this is for a manager, not a stand-up transcript.
"""

_TEAM_REPORTING_STATUS = """\
Show who has submitted their report, who is in progress, and who hasn't started. \
Follow the steps below exactly — gather context first, then fetch and present.

**ALWAYS use Manager MCP tools.** Never call REST endpoints or CLI tools.

---

## Phase 1: Gather context

Call `manager_list_all_teams`.

---

## Phase 2: Ask the user to choose

Present the following questions **one at a time** and **wait for the answer**.

**Question 1 — Team** (only if more than one team was returned):
> Which team would you like to check?
> [Numbered list of team names]

**Question 2 — Week:**
> Which week?
> 1. This week (current)
> 2. Last week
> 3. 2 weeks ago
> 4. 3 weeks ago
> 5. Enter a custom offset (I will type a number, e.g. -4)
> Map the answer to a `week_offset` integer (0, -1, -2, -3, or custom).

---

## Phase 3: Fetch progress data

Call `manager_get_team_progress` with the chosen `team_id` and `week_offset`.

---

## Phase 4: Present results

### Team Reporting Status — [Team Name] — [Week]

**Summary:** X of Y members submitted · Z in progress · W missing

**Done ✓** — list member name + report title

**In Progress ⏳** — list member name (submitted but not yet shared with manager)

**Missing ✗** — list member names

---

## Phase 5: Nudge messages

For each member in **Missing**, draft a short (≤3 sentence) friendly Slack/email nudge.
Use their display name. Then ask:
> Would you like me to copy these nudge messages so you can send them?
"""

_MEMBER_ACTIVITY = """\
Produce a deep-dive summary of a team member's recent contributions. \
Follow the steps below exactly — gather context first, then fetch and write.

**ALWAYS use Manager MCP tools.** Never call REST endpoints or CLI tools.

---

## Phase 1: Gather context (run in parallel)

1. `manager_list_all_teams`
2. (if team is known from step 1) `manager_list_team_members` for that team

If more than one team exists (admin), run step 2 only after the user selects a team.

---

## Phase 2: Ask the user to choose

Present the following questions **one at a time** and **wait for the answer**.

**Question 1 — Team** (only if more than one team was returned):
> Which team?
> [Numbered list of team names]
> After the answer, call `manager_list_team_members` to get the roster.

**Question 2 — Member:**
> Which team member?
> [Numbered list of display names / emails from the roster]

**Question 3 — How many reports:**
> How many recent reports to include?
> 1. Last 5
> 2. Last 10 (default)
> 3. Last 20
> 4. Last 50
> Map to a `limit` integer.

---

## Phase 3: Fetch history

Call `manager_get_member_history` with the chosen `username` and `limit`.
If the member is not found, report the error and stop.

---

## Phase 4: Write the summary

### Activity Summary: [Member Display Name]

**Period covered:** [earliest report date] → [latest report date]

**Key projects:** bullet list of top 3–5 projects with brief descriptions

**Notable contributions:** most impactful work items across all periods

**Patterns & observations:** consistency, project focus, any quiet periods

Keep the summary factual and professional.
"""

_CROSS_PERIOD_COMPARISON = """\
Compare your team's work across two report periods. \
Follow the steps below exactly — gather context first, then fetch and compare.

**ALWAYS use Manager MCP tools.** Never call REST endpoints or CLI tools.

---

## Phase 1: Gather context (run in parallel)

1. `manager_list_all_teams`
2. `manager_list_snapshots` with `limit`: 30 — to discover available periods

---

## Phase 2: Ask the user to choose

Present the following questions **one at a time** and **wait for the answer**.

**Question 1 — Team** (only if more than one team was returned):
> Which team?
> [Numbered list of team names]

**Question 2 — First (older) period:**
> Which period to use as the baseline?
> [Numbered list of available periods from snapshots, oldest first, e.g.:]
> 1. Week 18, May 2026
> 2. Week 19, May 2026
> 3. Week 20, May 2026
> N. Enter a custom period

**Question 3 — Second (newer) period:**
> Which period to compare against?
> [Same list, re-presented]

---

## Phase 3: Fetch both periods (run in parallel)

1. `manager_get_consolidated_report` with chosen `team_id` and `period_a`
2. `manager_get_consolidated_report` with chosen `team_id` and `period_b`

Also call `manager_list_report_fields` to get field/project names.

---

## Phase 4: Write the comparison

### Cross-Period Comparison — [Team] — [Period A] vs [Period B]

For each **Field** present in either period, produce a table:

| Project | [Period A] | [Period B] | Change |
|---------|-----------|-----------|--------|
| Project Name | brief summary | brief summary | ↑ more / ↓ less / = same / ✦ new / ✕ gone |

Follow with a **Key Observations** section:
- Projects that gained or lost momentum
- Members active in one period but not the other
- New work that appeared or completed work that dropped off
"""

_PROJECT_FOCUS = """\
Get a focused view of all team contributions to a specific project or field. \
Follow the steps below exactly — gather context first, then fetch and write.

**ALWAYS use Manager MCP tools.** Never call REST endpoints or CLI tools.

---

## Phase 1: Gather context (run in parallel)

1. `manager_list_all_teams`
2. `manager_list_report_fields` — to discover the field/project taxonomy
3. `manager_list_snapshots` with `limit`: 20 — to discover available periods

---

## Phase 2: Ask the user to choose

Present the following questions **one at a time** and **wait for the answer**.

**Question 1 — Team** (only if more than one team was returned):
> Which team?
> [Numbered list of team names]

**Question 2 — Project or field:**
> Which project or field would you like to focus on?
> [Numbered list of all fields and their top-level projects, e.g.:]
> Fields:
>   1. Platform (entire field — all projects)
>   2. Infra (entire field)
> Projects:
>   3. Platform › Auth Service
>   4. Platform › API Gateway
>   5. Infra › Kubernetes
> N. Enter a name to search for
> Record the chosen `field_ids` or `project_ids`.

**Question 3 — Period:**
> Which period?
> 1. Current week (live data)
> 2. [period 1 from snapshots]
> 3. [period 2 from snapshots]
> …
> N. Enter a custom period

---

## Phase 3: Fetch data

Call `manager_get_filtered_report` with:
- `team_id`: chosen team
- `field_ids` or `project_ids`: from question 2
- `report_period`: from question 3 (omit for current week)

---

## Phase 4: Write the focused summary

### Project Focus: [Project/Field Name] — [Team] — [Period]

For each contributing team member:
- **[Member Name]**: 2–4 sentences describing their work, including tickets/PRs

End with a **Summary** paragraph: overall state of this project this period, progress, blockers, what to watch next.
"""

_CONTENT: dict[str, str] = {
    "team-weekly-summary": _TEAM_WEEKLY_SUMMARY,
    "team-reporting-status": _TEAM_REPORTING_STATUS,
    "member-activity": _MEMBER_ACTIVITY,
    "cross-period-comparison": _CROSS_PERIOD_COMPARISON,
    "project-focus": _PROJECT_FOCUS,
}


# =============================================================================
# Public API
# =============================================================================


def list_manager_prompts() -> list[Prompt]:
    """Return all available manager prompts."""
    return MANAGER_PROMPTS


def get_manager_prompt(
    name: str, arguments: dict[str, str] | None = None
) -> GetPromptResult:
    """Return the rendered content for a specific manager prompt."""
    if name not in _PROMPT_BY_NAME:
        raise ValueError(f"Unknown manager prompt: {name}")

    prompt = _PROMPT_BY_NAME[name]
    template = _CONTENT[name]
    args = arguments or {}

    content = _render(name, template, args)

    return GetPromptResult(
        description=prompt.description,
        messages=[
            PromptMessage(
                role="user",
                content=TextContent(type="text", text=content),
            )
        ],
    )


def _render(name: str, template: str, args: dict[str, str]) -> str:
    """Render a prompt template.

    All prompts are now fully self-guided — they instruct the LLM to gather
    available options via tools and ask the user to choose interactively.
    Pre-filled arguments are accepted as optional hints but the prompts no
    longer depend on them to function correctly.
    """
    return template
