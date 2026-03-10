# Ghost

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![MCP](https://img.shields.io/badge/MCP-compatible-green.svg)](https://modelcontextprotocol.io/)

Ghost connects Jira and GitHub to AI-powered IDEs through [MCP](https://modelcontextprotocol.io/). It gives your IDE tools to search tickets, browse PRs, log work, and generate weekly reports — all from real data, no copy-pasting.

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
- *"Generate my weekly report"*

---

## Further Reading

| | |
|---|---|
| [Getting Started](docs/getting-started.md) | PAT creation walkthrough and first steps |
| [Configuration](docs/configuration.md) | All headers, env vars, GitHub Enterprise, multi-token, SSL options |
| [Tools Reference](docs/tools-reference.md) | Complete list of 50+ MCP tools |
| [Cursor Commands](docs/cursor-commands/) | Pre-built `/slash` commands for weekly reporting |
| [Architecture](docs/architecture.md) | System design, containers, data flows |
| [Deployment](docs/deployment.md) | Podman Compose, OpenShift, production setup |
| [Web UI](docs/web-ui.md) | Dashboard features and authentication |
| [Development](docs/development.md) | Local dev setup, testing, project structure |
| [Troubleshooting](docs/troubleshooting.md) | Common issues and solutions |

## License

MIT
