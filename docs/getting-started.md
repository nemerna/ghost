# Getting Started

This guide covers installation and initial setup for Ghost.

## Prerequisites

- Podman and Podman Compose (recommended)
- Or: Python 3.11+ for local development
- Jira Server or Data Center with PAT authentication
- (Optional) GitHub PAT for PR and issue integration

## Installation

### Podman Compose (Recommended)

The fastest way to get started:

```bash
git clone <repository-url>
cd ghost
podman-compose up -d
```

This starts three containers:
- **Frontend** (port 8080) - Nginx serving the web UI
- **Backend** (port 8000) - FastAPI REST API
- **MCP Server** (port 8001) - SSE server for AI tools

Access the web UI at `http://localhost:8080`

### Local Development

For development without containers:

```bash
git clone <repository-url>
cd ghost
python -m venv venv
source venv/bin/activate
pip install -e .

# Run MCP server only
python -m ghost.server --host 0.0.0.0 --port 8001

# Or run the REST API backend
uvicorn ghost.api.main:app --host 0.0.0.0 --port 8000
```

## Creating Personal Access Tokens

### Jira PAT

1. Log in to your Jira instance
2. Click your profile icon → **Profile**
3. Go to **Personal Access Tokens** (left sidebar)
4. Click **Create token**
5. Enter a name (e.g., "Ghost MCP") and set expiration
6. Click **Create** and copy the token immediately (it won't be shown again)

**Required permissions:** The token inherits your Jira user permissions. Ensure you have access to the projects you want to query.

### GitHub PAT

1. Go to [GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)](https://github.com/settings/tokens)
2. Click **Generate new token (classic)**
3. Enter a note (e.g., "Ghost MCP")
4. Select scopes:
   - `repo` — Full control of private repositories (or `public_repo` for public only)
   - `read:org` — Read org membership (if querying org repos)
5. Click **Generate token** and copy it immediately

**For GitHub Enterprise:** Use the same process on your enterprise instance, then set the `X-GitHub-API-URL` header to your API endpoint (e.g., `https://github.yourcompany.com/api/v3`).

## Configure Your IDE

Add the MCP servers to your Cursor IDE configuration (`.cursor/mcp.json`):

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
        "X-Username": "your-username",
        "X-Jira-Server-URL": "https://jira.example.com",
        "X-Jira-Token": "your-jira-pat"
      }
    }
  }
}
```

Restart Cursor after saving the configuration.

## Verify Setup

Test that everything is working:

1. **Web UI**: Open `http://localhost:8080` in your browser
2. **MCP Tools**: In Cursor, ask the AI to "list my Jira projects" or "show my GitHub PRs"

## Next Steps

- [Configuration](configuration.md) - Customize headers and environment variables
- [Tools Reference](tools-reference.md) - Explore available AI tools
- [Web UI](web-ui.md) - Learn about the dashboard features
