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
    "github-multi": {
      "url": "http://localhost:8080/mcp/github",
      "headers": {
        "Authorization": "Bearer your-reports-pat",
        "X-GitHub-Token-personal": "ghp_personal_token_here",
        "X-GitHub-Token-work": "ghp_org_token_here"
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

> **Note:** The `github` and `github-multi` entries above show two alternatives -- use one or the other, not both. Use `X-GitHub-Token` for a single token, or named headers for multiple tokens (see below).

## Multiple GitHub PATs

A single GitHub PAT may not have access to all the repositories you work with (e.g., personal repos vs organization repos with different scopes). You can configure multiple PATs, each mapped to specific owners or repositories using glob patterns.

### Setup via the Web UI (recommended)

1. Go to **Settings > GitHub Token Configuration** in the web UI
2. Add named entries with repo patterns:
   - `personal` with patterns `myuser/*`
   - `work` with patterns `my-org/*, partner-org/shared-repo`
3. Copy the generated MCP config snippet into your `.cursor/mcp.json`
4. Replace the placeholder values with your actual GitHub PATs

The web UI generates clean, ready-to-paste configuration like:

```json
{
  "url": "http://localhost:8080/mcp/github",
  "headers": {
    "Authorization": "Bearer <your reports PAT>",
    "X-GitHub-Token-personal": "<paste your personal GitHub PAT here>",
    "X-GitHub-Token-work": "<paste your org GitHub PAT here>"
  }
}
```

The `Authorization: Bearer` header (same PAT you use for reports) identifies you so the server can load your pattern config. The `X-GitHub-Token-{name}` headers carry the actual GitHub tokens, which are never stored on the server.

### How pattern matching works

- Patterns use `fnmatch`-style globs matched against `owner/repo`
- `my-org/*` matches any repo under `my-org`
- `my-org/specific-repo` matches exactly that repo
- `*` matches everything (catch-all fallback)
- Entries are evaluated in order -- first match wins
- Use the `github_list_tokens` tool to verify your configured patterns

## Cursor Commands

Ghost ships with pre-built Cursor slash commands that streamline your weekly reporting workflow. Type `/` in the Cursor agent input to access them.

| Command | What it does |
|---------|-------------|
| `/gather-activities` | Discovers work from Jira and GitHub for the current week, compares against already-logged activities |
| `/log-activities` | Logs untracked items into the system (asks for confirmation first) |
| `/create-management-report` | Creates a properly formatted management report from logged activities |
| `/weekly-report` | Runs all three steps end-to-end in one go |

### Setup

The command files live in [`docs/cursor-commands/`](docs/cursor-commands/). Copy them to either location:

```bash
# Global (available in all projects)
mkdir -p ~/.cursor/commands
cp docs/cursor-commands/*.md ~/.cursor/commands/

# Or project-level (this project only)
mkdir -p .cursor/commands
cp docs/cursor-commands/*.md .cursor/commands/
```

Then type `/` in Cursor's agent input to see them in the dropdown.

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
