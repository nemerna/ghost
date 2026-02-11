# Ghost

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![MCP](https://img.shields.io/badge/MCP-compatible-green.svg)](https://modelcontextprotocol.io/)

Connect Jira and GitHub to AI-powered IDEs. Spend less time writing status updates—your IDE pulls real data and drafts reports from actual activity.

## What It Does

- **Jira Integration** — List, create, update tickets, and manage comments directly from your IDE
- **GitHub Integration** — Browse PRs, review code, manage issues, and search across repositories
- **Activity Tracking** — Automatically log work on tickets and generate weekly reports
- **Web Dashboard** — View activity, manage reports, and administer teams

## Quick Start

```bash
# 1. Clone and start
git clone <repository-url> && cd ghost
podman-compose up -d

# 2. Access web UI
open http://localhost:8080
```

Then configure your IDE (`.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "jira": {
      "url": "http://localhost:8080/mcp/jira",
      "headers": {
        "X-Jira-Server-URL": "https://jira.example.com",
        "X-Jira-Token": "your-jira-pat"
      }
    },
    "github": {
      "url": "http://localhost:8080/mcp/github",
      "headers": {
        "X-GitHub-Token": "your-github-pat"
      }
    },
    "reports": {
      "url": "http://localhost:8080/mcp/reports",
      "headers": {
        "Authorization": "Bearer your-personal-access-token",
        "X-Jira-Server-URL": "https://jira.example.com",
        "X-Jira-Token": "your-jira-pat"
      }
    }
  }
}
```

Generate a Personal Access Token from **Settings > Personal Access Tokens** in the web UI, then use it as the `Authorization: Bearer` header for the reports MCP. Restart Cursor after saving.

## Example Prompts

Once configured, try these in your AI-powered IDE:

- "List my in-progress Jira tickets"
- "Show open PRs for org/repo"
- "Create a bug ticket for the login issue"
- "Log that I worked on PROJ-123 today"
- "Generate my weekly report"

## Documentation

| Guide | Description |
|-------|-------------|
| [Getting Started](docs/getting-started.md) | Installation, PAT setup, and first steps |
| [Configuration](docs/configuration.md) | Headers, environment variables, client examples |
| [Architecture](docs/architecture.md) | System design, containers, data flows |
| [Tools Reference](docs/tools-reference.md) | Complete list of 50+ MCP tools |
| [Deployment](docs/deployment.md) | Podman Compose, OpenShift, production setup |
| [Web UI](docs/web-ui.md) | Dashboard features and authentication |
| [Development](docs/development.md) | Local setup, testing, project structure |
| [Troubleshooting](docs/troubleshooting.md) | Common issues and solutions |

## Requirements

- Podman and Podman Compose (recommended)
- Jira Server/Data Center with PAT authentication
- GitHub PAT (optional, for PR and issue tools)

## License

MIT
