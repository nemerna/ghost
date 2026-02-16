Run the full weekly report workflow end-to-end: gather my activities, log anything missing, then create the management report.

**ALWAYS use MCP server tools** for all Jira, GitHub, and work-reports operations. Never use CLI tools (`gh`, `jira-cli`), direct API calls, `curl`, or custom HTTP clients. If an MCP tool is unavailable or fails with a connection error, **STOP immediately** -- do not fall back to alternatives. Inform the user that the MCP server appears to be down and suggest checking the server status.

## Phase 0: Verify MCP Availability

Before doing anything else, verify that the MCP server is reachable:

1. Call `github_get_current_user` as a connectivity check
2. If the tool is **not available**, returns a **connection error**, or **times out**: **STOP immediately**. Do not proceed to Phase 1. Tell the user:
   > "The MCP server appears to be unavailable. Please check that the Ghost server is running (`curl http://localhost:8080/health`) and that your `.cursor/mcp.json` is configured correctly."
3. **Do NOT attempt to use CLI tools, direct API calls, or any alternative.** This workflow requires MCP tools -- there is no fallback.

## Phase 1: Gather Activities

1. Identify me on both platforms (parallel): `jira_get_current_user` + `github_get_current_user`
2. Check already-logged activities: `get_weekly_activity(week_offset=0)`
3. Search Jira: `jira_list_tickets(assignee="currentUser")` with statuses "In Progress", "Done", "Review" — filter by `updated` date within the current week
4. Search GitHub: `github_search_prs(query="author:USERNAME updated:>=YYYY-MM-DD")` and `github_search_issues(query="author:USERNAME updated:>=YYYY-MM-DD")`
5. Present what's already tracked vs what's not yet logged

## Phase 2: Log Missing Activities

1. Show me unlogged items and **ask for confirmation** before logging anything
2. For Jira tickets, fetch components via `jira_get_ticket` before logging — needed for project detection
3. Log each confirmed item with `log_activity` (include `jira_components` for Jira, `github_repo` for GitHub)
4. Verify with `get_weekly_activity`

## Phase 3: Create the Management Report

1. Get all logged activities: `get_weekly_activity(week_offset=0)`
2. For each ticket, gather PR/issue URLs for link formatting
3. Format each entry as: `[Action Verb](PR-URL) [brief description](ISSUE-URL) plus context`
   - Embed links naturally — NO raw ticket numbers
   - The report is ONLY work items — no sections, headers, summaries, or plans
4. Save with `save_management_report` using **`entries`** (not `content`):
   - Each entry must include `text` and `ticket_key`
   - Include `referenced_tickets` array
5. Show me the result and ask if adjustments are needed
