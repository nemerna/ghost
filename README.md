# Jira MCP Server

A Model Context Protocol (MCP) server for Jira ticket management. This server enables AI assistants like Claude to interact with self-hosted Jira instances using Personal Access Token (PAT) authentication.

## Features

### Ticket Management
- **List Tickets**: Search and filter tickets by assignee, project, component, epic, and status
- **View Ticket Details**: Get full ticket information including description, components, labels, and comments
- **Create Tickets**: Create new issues with customizable fields (type, assignee, components, epic, priority, labels)
- **Update Tickets**: Modify ticket title, description, assignee, status, components, and priority
- **Manage Comments**: Add comments and retrieve comment history

### Discovery/Metadata
- **List Projects**: View all accessible projects
- **List Components**: Get available components for a project
- **List Issue Types**: Get available issue types (Task, Bug, Story, Epic, etc.)
- **List Priorities**: Get available priority levels
- **List Statuses**: Get available workflow statuses for a project
- **Get Transitions**: See available workflow transitions for a ticket
- **Get Current User**: Get authenticated user information

## Requirements

- Python 3.11+
- Self-hosted Jira Server or Data Center instance
- Personal Access Token (PAT) for authentication

## Installation

### Local Development

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd jira-mcp
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install the package:
   ```bash
   pip install -e .
   ```

## Configuration

The server requires two environment variables:

| Variable | Required | Description |
|----------|----------|-------------|
| `JIRA_SERVER_URL` | Yes | Base URL of your Jira server (e.g., `https://jira.example.com`) |
| `JIRA_PERSONAL_ACCESS_TOKEN` | Yes | Your Jira Personal Access Token |
| `JIRA_VERIFY_SSL` | No | Verify SSL certificates (default: `true`, set to `false` for self-signed certs) |

### Creating a Personal Access Token

1. Log in to your Jira instance
2. Go to Profile → Personal Access Tokens
3. Click "Create token"
4. Give it a name and set expiration
5. Copy the token (it won't be shown again)

## Client Configuration

### Cursor IDE (Recommended)

Add the following to your Cursor MCP settings (`.cursor/mcp.json` or via Settings → MCP Servers):

```json
{
  "mcpServers": {
    "jira": {
      "command": "jira-mcp",
      "env": {
        "JIRA_SERVER_URL": "https://jira.your-company.com",
        "JIRA_PERSONAL_ACCESS_TOKEN": "your-personal-access-token"
      }
    }
  }
}
```

If you installed in a virtual environment, use the full path:

```json
{
  "mcpServers": {
    "jira": {
      "command": "/path/to/your/venv/bin/jira-mcp",
      "env": {
        "JIRA_SERVER_URL": "https://jira.your-company.com",
        "JIRA_PERSONAL_ACCESS_TOKEN": "your-personal-access-token"
      }
    }
  }
}
```

For self-signed SSL certificates, add:

```json
{
  "mcpServers": {
    "jira": {
      "command": "jira-mcp",
      "env": {
        "JIRA_SERVER_URL": "https://jira.your-company.com",
        "JIRA_PERSONAL_ACCESS_TOKEN": "your-personal-access-token",
        "JIRA_VERIFY_SSL": "false"
      }
    }
  }
}
```

### Claude Desktop

Add the following to your Claude Desktop configuration (`~/.config/claude/claude_desktop_config.json` on macOS/Linux or `%APPDATA%\Claude\claude_desktop_config.json` on Windows):

```json
{
  "mcpServers": {
    "jira": {
      "command": "jira-mcp",
      "env": {
        "JIRA_SERVER_URL": "https://jira.your-company.com",
        "JIRA_PERSONAL_ACCESS_TOKEN": "your-personal-access-token"
      }
    }
  }
}
```

### SSE Transport (HTTP Server Mode)

For running as a shared HTTP server (e.g., for multiple users or containerized deployments):

```bash
# Set environment variables
export JIRA_SERVER_URL=https://jira.example.com
export JIRA_PERSONAL_ACCESS_TOKEN=your-token

# Run with SSE transport
jira-mcp --transport sse --host 0.0.0.0 --port 8080
```

Then configure your MCP client to connect to the SSE endpoint:

```json
{
  "mcpServers": {
    "jira": {
      "url": "http://localhost:8080/sse"
    }
  }
}
```

#### Container Deployment (SSE Mode)

Build the container image:

```bash
# Using Podman
podman build -t jira-mcp:latest -f Containerfile .

# Using Docker
docker build -t jira-mcp:latest -f Containerfile .
```

Run the container:

```bash
podman run -d \
  -p 8080:8080 \
  -e JIRA_SERVER_URL=https://jira.example.com \
  -e JIRA_PERSONAL_ACCESS_TOKEN=your-token \
  --name jira-mcp \
  jira-mcp:latest
```

## Usage

### Command-Line Options

```bash
# Run with stdio transport (default, for Cursor/Claude Desktop)
jira-mcp

# Run with SSE transport (HTTP server mode)
jira-mcp --transport sse --host 0.0.0.0 --port 8080

# Show help
jira-mcp --help
```

### MCP Tools

#### `jira_list_tickets`

List tickets with optional filters.

```json
{
  "assignee": "john.doe",
  "project": "PROJ",
  "component": "Backend",
  "epic_key": "PROJ-100",
  "status": "In Progress",
  "max_results": 50
}
```

#### `jira_get_ticket`

Get full details of a ticket.

```json
{
  "ticket_key": "PROJ-123"
}
```

#### `jira_create_ticket`

Create a new ticket.

```json
{
  "project": "PROJ",
  "summary": "Implement new feature",
  "description": "Detailed description here",
  "issue_type": "Task",
  "assignee": "john.doe",
  "components": ["Backend", "API"],
  "epic_key": "PROJ-100",
  "priority": "High",
  "labels": ["feature", "q1"]
}
```

#### `jira_update_ticket`

Update an existing ticket.

```json
{
  "ticket_key": "PROJ-123",
  "summary": "Updated title",
  "description": "Updated description",
  "assignee": "jane.doe",
  "status": "In Progress",
  "priority": "Critical"
}
```

#### `jira_add_comment`

Add a comment to a ticket.

```json
{
  "ticket_key": "PROJ-123",
  "body": "This is a comment with *Jira markup* support."
}
```

#### `jira_get_comments`

Get comments from a ticket.

```json
{
  "ticket_key": "PROJ-123",
  "max_results": 20
}
```

### Discovery/Metadata Tools

#### `jira_list_projects`

List all accessible projects. No parameters required.

```json
{}
```

**Response:**
```json
[
  {
    "key": "PROJ",
    "name": "My Project",
    "lead": "john.doe",
    "url": "https://jira.example.com/browse/PROJ"
  }
]
```

#### `jira_list_components`

List components for a project.

```json
{
  "project": "PROJ"
}
```

**Response:**
```json
[
  {
    "id": "10001",
    "name": "Backend",
    "description": "Backend services",
    "lead": "jane.doe"
  }
]
```

#### `jira_list_issue_types`

List issue types available for a project.

```json
{
  "project": "PROJ"
}
```

**Response:**
```json
[
  {
    "id": "10001",
    "name": "Task",
    "description": "A task that needs to be done",
    "subtask": false
  },
  {
    "id": "10002",
    "name": "Bug",
    "description": "A bug in the system",
    "subtask": false
  }
]
```

#### `jira_list_priorities`

List all available priorities. No parameters required.

```json
{}
```

**Response:**
```json
[
  {
    "id": "1",
    "name": "Highest",
    "description": "This problem will block progress.",
    "icon_url": "https://jira.example.com/images/icons/priorities/highest.svg"
  }
]
```

#### `jira_list_statuses`

List available statuses for a project.

```json
{
  "project": "PROJ"
}
```

**Response:**
```json
[
  {
    "id": "1",
    "name": "Open",
    "description": "The issue is open and ready for work",
    "category": "To Do"
  },
  {
    "id": "3",
    "name": "In Progress",
    "description": "Work is being done",
    "category": "In Progress"
  }
]
```

#### `jira_get_transitions`

Get available workflow transitions for a ticket.

```json
{
  "ticket_key": "PROJ-123"
}
```

**Response:**
```json
[
  {
    "id": "21",
    "name": "Start Progress",
    "to_status": "In Progress",
    "to_status_id": "3"
  },
  {
    "id": "31",
    "name": "Done",
    "to_status": "Done",
    "to_status_id": "10001"
  }
]
```

#### `jira_get_current_user`

Get information about the authenticated user. No parameters required.

```json
{}
```

**Response:**
```json
{
  "username": "john.doe",
  "display_name": "John Doe",
  "email": "john.doe@example.com",
  "active": true,
  "timezone": "America/New_York"
}
```

## Development

### Install Development Dependencies

```bash
pip install -e ".[dev]"
```

### Run Tests

```bash
pytest
```

### Code Formatting

```bash
black src/ tests/
ruff check src/ tests/
```

### Type Checking

```bash
mypy src/
```

## Project Structure

```
jira-mcp/
├── src/
│   └── jira_mcp/
│       ├── __init__.py          # Package initialization
│       ├── server.py            # MCP server (stdio + SSE)
│       ├── config.py            # Configuration management
│       ├── jira_client.py       # Jira API client wrapper
│       └── tools/
│           ├── __init__.py      # Tools exports
│           ├── tickets.py       # Ticket operations
│           ├── comments.py      # Comment operations
│           ├── discovery.py     # Discovery/metadata operations
│           └── schemas.py       # Pydantic schemas
├── tests/                       # Test files
├── Containerfile               # Red Hat UBI container build
├── pyproject.toml              # Project configuration
├── requirements.txt            # Python dependencies
└── README.md                   # This file
```

## Troubleshooting

### SSL Certificate Errors

If you're using a self-signed certificate, set `JIRA_VERIFY_SSL=false` in your MCP client configuration.

### Authentication Errors

- Verify your PAT is valid and not expired
- Ensure the PAT has the necessary permissions for the operations you're performing
- Check that the Jira server URL is correct (no trailing slash)

### Connection Refused

- For SSE mode: Verify the MCP server is running and the port is accessible
- For stdio mode: Check that the `jira-mcp` command is in your PATH or use the full path
- Ensure the Jira server is accessible from your machine

### Missing Environment Variables

If you see "JIRA_SERVER_URL environment variable is required", make sure you've configured the environment variables in your MCP client settings (not in a `.env` file on the server).

## License

MIT License - See LICENSE file for details.
