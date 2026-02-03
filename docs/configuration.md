# Configuration

This guide covers all configuration options for Ghost, including MCP client headers and environment variables.

## MCP Client Headers

Credentials are passed from the MCP client via HTTP headers. Each endpoint requires specific headers.

### Jira Endpoint (`/mcp/jira`)

| Header | Required | Description |
|--------|----------|-------------|
| `X-Jira-Server-URL` | Yes | Jira base URL (e.g., `https://jira.example.com`) |
| `X-Jira-Token` | Yes | Jira Personal Access Token |
| `X-Jira-Verify-SSL` | No | `true` (default) or `false` to skip SSL verification |

### GitHub Endpoint (`/mcp/github`)

| Header | Required | Description |
|--------|----------|-------------|
| `X-GitHub-Token` | Yes | GitHub Personal Access Token |
| `X-GitHub-API-URL` | No | GitHub Enterprise API URL (e.g., `https://github.yourcompany.com/api/v3`) |

### Reports Endpoint (`/mcp/reports`)

| Header | Required | Description |
|--------|----------|-------------|
| `X-Username` | Yes | Username for activity tracking |
| `X-Jira-Server-URL` | No | Jira base URL (enables auto-fetching ticket components for project detection) |
| `X-Jira-Token` | No | Jira PAT (required if `X-Jira-Server-URL` is set) |
| `X-Jira-Verify-SSL` | No | `true` (default) or `false` |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | — | PostgreSQL connection string (leave empty for SQLite) |
| `GHOST_DATA_DIR` | `./data` | SQLite storage directory |
| `DEV_MODE` | `false` | Enable development mode (bypass OAuth, enable API docs) |
| `DEV_EMAIL` | `dev@example.com` | Email to use in development mode |
| `CORS_ORIGINS` | `*` | Allowed CORS origins (comma-separated) |
| `MANAGEMENT_REPORT_INSTRUCTIONS_FILE` | — | Path to custom management report instructions |

## Client Setup Examples

### Cursor IDE

Create or edit `.cursor/mcp.json` in your project or home directory:

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

### GitHub Enterprise

For GitHub Enterprise instances, add the API URL header:

```json
{
  "mcpServers": {
    "github": {
      "url": "http://localhost:8080/mcp/github",
      "headers": {
        "X-GitHub-Token": "your-github-pat",
        "X-GitHub-API-URL": "https://github.yourcompany.com/api/v3"
      }
    }
  }
}
```

### Self-Signed SSL Certificates

If your Jira instance uses a self-signed certificate:

```json
{
  "mcpServers": {
    "jira": {
      "url": "http://localhost:8080/mcp/jira",
      "headers": {
        "X-Jira-Server-URL": "https://jira.example.com",
        "X-Jira-Token": "your-jira-pat",
        "X-Jira-Verify-SSL": "false"
      }
    }
  }
}
```

## Database Configuration

### SQLite (Default)

No configuration needed. Data is stored in the `GHOST_DATA_DIR` directory (default: `./data`).

### PostgreSQL

Set the `DATABASE_URL` environment variable:

```bash
DATABASE_URL=postgresql://user:password@localhost:5432/ghost
```

Or use Docker Compose with the PostgreSQL profile:

```bash
docker-compose --profile postgres up -d
```

## See Also

- [Getting Started](getting-started.md) - Initial setup and PAT creation
- [Deployment](deployment.md) - Production deployment options
- [Troubleshooting](troubleshooting.md) - Common configuration issues
