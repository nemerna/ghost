Log untracked work activities into the system. Present the items first and wait for my confirmation before logging anything.

**ALWAYS use MCP server tools** for all operations. Never use CLI tools, direct API calls, or custom clients.

## Steps

1. **Show me what's unlogged** — if you haven't already gathered activities, run `/gather-activities` first

2. **Ask for confirmation** — never log without my approval

3. **Enrich ticket data** before logging:
   - Jira tickets: `jira_get_ticket(ticket_key="PROJ-123")` to get components and summary
   - GitHub items: `github_get_issue` or `github_get_pr` for summary and repo info

4. **Log each confirmed item** using `log_activity`:
   - **ticket_key**: `PROJ-123` (Jira) or `owner/repo#123` (GitHub)
   - **ticket_summary**: brief description
   - **github_repo**: required for GitHub items (format: `owner/repo`)
   - **jira_components**: required for Jira tickets — always fetch via `jira_get_ticket` first, needed for project detection

5. **Verify** by calling `get_weekly_activity` to confirm everything is tracked
