# Ghost

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![MCP](https://img.shields.io/badge/MCP-compatible-green.svg)](https://modelcontextprotocol.io/)

Ghost connects GitHub to AI-powered IDEs through [MCP](https://modelcontextprotocol.io/). It gives your IDE tools to browse PRs, log work, and generate management reports — all from real data, no copy-pasting.

Jira integration is handled via an external Atlassian MCP server — configure it alongside Ghost in your IDE.

## Get Started

### 1. Gather your credentials

| Value | Where to get it | Used by |
|-------|----------------|---------|
| `GHOST_URL` | Your Ghost instance URL (provided by your team) | All endpoints |
| `GITHUB_PAT` | [GitHub → Settings → Developer settings → Personal access tokens](https://github.com/settings/tokens) | GitHub |
| `GHOST_PAT` | Ghost web UI → Settings → Personal Access Tokens → Generate | Reports |

### 2. Configure your IDE

Replace the `ALL_CAPS` placeholders below with the values from step 1.

<details>
<summary><strong>Cursor</strong></summary>

Create or edit `.cursor/mcp.json` in your project root (or `~/.cursor/mcp.json` for global):

```json
{
  "mcpServers": {
    "github": {
      "url": "GHOST_URL/mcp/github",
      "headers": {
        "X-GitHub-Token": "GITHUB_PAT"
      }
    },
    "reports": {
      "url": "GHOST_URL/mcp/reports",
      "headers": {
        "Authorization": "Bearer GHOST_PAT"
      }
    },
    "jira": {
      "type": "streamable-http",
      "url": "https://mcp.atlassian.com/v1/mcp",
      "auth": {
        "type": "oauth"
      }
    }
  }
}
```

Restart Cursor after saving. The Jira server uses OAuth — you'll be prompted to authenticate on first use.

</details>

<details>
<summary><strong>Claude Code</strong></summary>

```bash
claude mcp add --transport streamable-http github \
  GHOST_URL/mcp/github \
  --header "X-GitHub-Token: GITHUB_PAT"

claude mcp add --transport streamable-http reports \
  GHOST_URL/mcp/reports \
  --header "Authorization: Bearer GHOST_PAT"

claude mcp add --transport streamable-http jira \
  https://mcp.atlassian.com/v1/mcp
```

Verify with `claude mcp list` — all three should show `✓ Connected`.

</details>

### 3. Try it

Ask your IDE:

- *"Show open PRs for my-org/my-repo"*
- *"Create a management report"*

### Prompts (slash-commands)

The **Reports** MCP server exposes prompts that appear as `/slash` commands in
IDEs like Cursor. Each prompt orchestrates a multi-step workflow using the
available MCP tools.

| Prompt | What it does |
|--------|-------------|
| `gather-activities` | Scans Jira (via external MCP) and GitHub for work you did during a given period and compares it against what's already logged, surfacing untracked items. |
| `log-activities` | Logs untracked items into the system. Shows you the list first and waits for confirmation before writing anything. |
| `create-management-report` | Builds a management report from your logged activities with properly formatted links, then saves it via the Reports API. |
| `unghost` | Creates a tracking ticket (via Jira MCP or GitHub issue) for work that was submitted without one, adds a progress comment linking the actual commits/PRs, and optionally logs the activity. |
| `weekly-report` | End-to-end workflow: gathers activities from Jira and GitHub, logs untracked items, and creates a formatted management report — all in one go. |

All prompts (except `unghost`) will prompt you to enter the number of days to
collect data from (e.g. `7` for the last week, `14` for the last two weeks).
`unghost` operates on the current branch and does not require a time range.

---

## License

MIT
