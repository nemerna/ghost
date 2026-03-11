# Ghost

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![MCP](https://img.shields.io/badge/MCP-compatible-green.svg)](https://modelcontextprotocol.io/)

Ghost connects Jira and GitHub to AI-powered IDEs through [MCP](https://modelcontextprotocol.io/). It gives your IDE tools to search tickets, browse PRs, log work, and generate management reports — all from real data, no copy-pasting.

## Get Started

### 1. Run the server

```bash
git clone <repository-url> && cd ghost
podman-compose up -d
```

Open `http://localhost:8080` to access the web UI.

### 2. Gather your credentials

| Value | Where to get it | Used by |
|-------|----------------|---------|
| `GHOST_URL` | `http://localhost:8080` for local, or your hosted instance URL | All endpoints |
| `JIRA_SERVER_URL` | Your Jira base URL (e.g. `https://issues.redhat.com`) | Jira, Reports |
| `JIRA_PAT` | Jira → Profile → Personal Access Tokens → Create token | Jira, Reports |
| `GITHUB_PAT` | [GitHub → Settings → Developer settings → Personal access tokens](https://github.com/settings/tokens) | GitHub |
| `GHOST_PAT` | Ghost web UI → Settings → Personal Access Tokens → Generate | Reports |

### 3. Configure your IDE

Replace the `ALL_CAPS` placeholders below with the values from step 2.

<details>
<summary><strong>Cursor</strong></summary>

Create or edit `.cursor/mcp.json` in your project root (or `~/.cursor/mcp.json` for global):

```json
{
  "mcpServers": {
    "jira": {
      "url": "GHOST_URL/mcp/jira",
      "headers": {
        "X-Jira-Server-URL": "JIRA_SERVER_URL",
        "X-Jira-Token": "JIRA_PAT"
      }
    },
    "github": {
      "url": "GHOST_URL/mcp/github",
      "headers": {
        "X-GitHub-Token": "GITHUB_PAT"
      }
    },
    "reports": {
      "url": "GHOST_URL/mcp/reports",
      "headers": {
        "Authorization": "Bearer GHOST_PAT",
        "X-Jira-Server-URL": "JIRA_SERVER_URL",
        "X-Jira-Token": "JIRA_PAT"
      }
    }
  }
}
```

Restart Cursor after saving.

</details>

<details>
<summary><strong>Claude Code</strong></summary>

```bash
claude mcp add --transport streamable-http jira \
  GHOST_URL/mcp/jira \
  --header "X-Jira-Server-URL: JIRA_SERVER_URL" \
  --header "X-Jira-Token: JIRA_PAT"

claude mcp add --transport streamable-http github \
  GHOST_URL/mcp/github \
  --header "X-GitHub-Token: GITHUB_PAT"

claude mcp add --transport streamable-http reports \
  GHOST_URL/mcp/reports \
  --header "Authorization: Bearer GHOST_PAT" \
  --header "X-Jira-Server-URL: JIRA_SERVER_URL" \
  --header "X-Jira-Token: JIRA_PAT"
```

Verify with `claude mcp list` — all three should show `✓ Connected`.

</details>

### 4. Try it

Ask your IDE:

- *"List my in-progress Jira tickets"*
- *"Show open PRs for my-org/my-repo"*
- *"Create a management report"*

### Prompts (slash-commands)

The **Reports** MCP server exposes prompts that appear as `/slash` commands in
IDEs like Cursor. Each prompt orchestrates a multi-step workflow using the
available MCP tools.

| Prompt | What it does |
|--------|-------------|
| `gather-activities` | Scans Jira and GitHub for work you did during a given week and compares it against what's already logged, surfacing untracked items. |
| `log-activities` | Logs untracked items into the system. Shows you the list first and waits for confirmation before writing anything. |
| `create-management-report` | Builds a management report from your logged activities with properly formatted links, then saves it via the Reports API. |
| `unghost` | Creates a tracking ticket (Jira issue or GitHub issue) for work that was submitted without one, adds a progress comment linking the actual commits/PRs, and optionally logs the activity. |

All prompts accept an optional `week_offset` argument (`0` = current week,
`1` = last week, etc.) except `unghost`, which operates on the current branch.

---

## Configuration

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | — | PostgreSQL connection string (empty = SQLite) |
| `GHOST_DATA_DIR` | `./data` | SQLite storage directory |
| `DEV_MODE` | `false` | Bypass OAuth, enable API docs |

### Optional headers

| Header | Endpoint | Description |
|--------|----------|-------------|
| `X-GitHub-API-URL` | `/mcp/github` | GitHub Enterprise API URL (e.g. `https://github.yourcompany.com/api/v3`) |
| `X-Jira-Verify-SSL` | `/mcp/jira` | Set to `false` for self-signed certificates |

---

## Local Development

```bash
pip install -e ".[dev]"

python -m ghost.server --host 0.0.0.0 --port 8001          # MCP server
DEV_MODE=true uvicorn ghost.api.main:app --port 8000 --reload  # REST API

cd ui && npm install && npm run dev                         # Frontend (localhost:5173)
```

## License

MIT
