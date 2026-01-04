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

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure environment variables:
   ```bash
   cp env.example .env
   # Edit .env with your Jira server URL and PAT
   ```

### Container Deployment

Build the container image using Podman or Docker:

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

## Configuration

Configuration is done via environment variables or a `.env` file:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `JIRA_SERVER_URL` | Yes | - | Base URL of your Jira server |
| `JIRA_PERSONAL_ACCESS_TOKEN` | Yes | - | Your Jira Personal Access Token |
| `JIRA_VERIFY_SSL` | No | `true` | Verify SSL certificates (set to `false` for self-signed certs) |
| `MCP_SERVER_HOST` | No | `0.0.0.0` | Server bind address |
| `MCP_SERVER_PORT` | No | `8080` | Server port |
| `JIRA_DEFAULT_PROJECT` | No | - | Default project key when not specified |

### Creating a Personal Access Token

1. Log in to your Jira instance
2. Go to Profile → Personal Access Tokens
3. Click "Create token"
4. Give it a name and set expiration
5. Copy the token (it won't be shown again)

## Usage

### Starting the Server

```bash
# Using the installed entry point
jira-mcp

# Or run directly
python -m jira_mcp.server
```

The server will start on `http://0.0.0.0:8080` by default.

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/sse` | GET | SSE connection for MCP clients |
| `/messages` | POST | Handle MCP messages |

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

## MCP Client Configuration

### Claude Desktop

Add the following to your Claude Desktop configuration (`~/.config/claude/config.json` or equivalent):

```json
{
  "mcpServers": {
    "jira": {
      "url": "http://localhost:8080/sse"
    }
  }
}
```

### Cursor IDE

Add the server URL in your Cursor MCP settings:

```
http://localhost:8080/sse
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
│       ├── server.py            # MCP server with FastAPI
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

If you're using a self-signed certificate, set:
```bash
JIRA_VERIFY_SSL=false
```

### Authentication Errors

- Verify your PAT is valid and not expired
- Ensure the PAT has the necessary permissions for the operations you're performing
- Check that the Jira server URL is correct (no trailing slash)

### Connection Refused

- Verify the MCP server is running
- Check firewall rules allow connections on the configured port
- Ensure the Jira server is accessible from the MCP server host

## License

MIT License - See LICENSE file for details.

