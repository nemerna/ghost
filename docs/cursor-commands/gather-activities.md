Discover all work I did during the current week by checking Jira and GitHub. Compare against what's already logged.

**ALWAYS use MCP server tools** for all Jira, GitHub, and work-reports operations. Never use CLI tools (`gh`, `jira-cli`), direct API calls, `curl`, or custom HTTP clients. If an MCP tool is unavailable or fails with a connection error, **STOP immediately** -- do not fall back to alternatives. Inform the user that the MCP server appears to be down and suggest checking the server status.

## Step 0: Verify MCP Availability

Before doing anything else, verify that the MCP server is reachable:

1. Call `github_get_current_user` as a connectivity check
2. If the tool is **not available**, returns a **connection error**, or **times out**: **STOP immediately**. Tell the user:
   > "The MCP server appears to be unavailable. Please check that the Ghost server is running (`curl http://localhost:8080/health`) and that your `.cursor/mcp.json` is configured correctly."
3. **Do NOT attempt to use CLI tools, direct API calls, or any alternative.** This workflow requires MCP tools -- there is no fallback.

## Steps

1. **Identify me** on both platforms (run in parallel):
   - `jira_get_current_user`
   - `github_get_current_user`

2. **Check what's already logged**:
   - `get_weekly_activity(week_offset=0)`
   - Note the `unique_tickets` list — these are already tracked

3. **Search Jira** for my tickets using `jira_list_tickets`:
   - `jira_list_tickets(assignee="currentUser", status="In Progress")`
   - `jira_list_tickets(assignee="currentUser", status="Done")`
   - `jira_list_tickets(assignee="currentUser", status="Review")`
   - Filter results by the `updated` field to only include tickets updated within this week
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
