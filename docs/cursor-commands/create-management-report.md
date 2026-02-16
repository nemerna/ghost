Create a management report for the current week using my logged activities. Follow the formatting rules exactly.

**ALWAYS use MCP server tools** for all operations. Never use CLI tools (`gh`, `jira-cli`), direct API calls, `curl`, or custom HTTP clients. If an MCP tool is unavailable or fails with a connection error, **STOP immediately** -- do not fall back to alternatives. Inform the user that the MCP server appears to be down and suggest checking the server status.

## Step 0: Verify MCP Availability

Before doing anything else, verify that the MCP server is reachable:

1. Call `get_weekly_activity(week_offset=0)` as a connectivity check
2. If the tool is **not available**, returns a **connection error**, or **times out**: **STOP immediately**. Tell the user:
   > "The MCP server appears to be unavailable. Please check that the Ghost server is running (`curl http://localhost:8080/health`) and that your `.cursor/mcp.json` is configured correctly."
3. **Do NOT attempt to use CLI tools, direct API calls, or any alternative.** This workflow requires MCP tools -- there is no fallback.

## Prerequisites

Before creating the report, activities must be gathered and logged. If not done yet, run `/gather-activities` and `/log-activities` first. Ask me.

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
[Fixed](https://github.com/org/repo/pull/42) the [login timeout bug](https://issues.redhat.com/browse/PROJ-123) affecting production users
[Implemented](https://github.com/org/repo/pull/15) [role-based access control](https://issues.redhat.com/browse/PROJ-456) for the admin panel
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

1. **Get activity data**: `get_weekly_activity(week_offset=0)`

2. **Gather URLs** for each ticket:
   - Jira issues: `https://issues.redhat.com/browse/PROJ-123`
   - GitHub issues: `github_get_issue` or `https://github.com/owner/repo/issues/NUMBER`
   - GitHub PRs: use `github_search_prs` or `github_list_prs` to find associated PRs
   - If no PR exists, use the commit URL: `https://github.com/owner/repo/commit/SHA`

3. **Format and save**:
   ```json
   {
     "title": "Week N, Month Year",
     "report_period": "Week N, Mon Year",
     "entries": [
       {
         "text": "[Fixed](https://github.com/org/repo/commit/abc123) the [live report bug](https://github.com/org/repo/issues/32) that showed stale data",
         "ticket_key": "org/repo#32"
       }
     ],
     "referenced_tickets": ["org/repo#32"]
   }
   ```

4. **Show me the result** and ask if adjustments are needed. Use `update_management_report` for changes.
