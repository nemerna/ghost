# Jira MCP Server

A Model Context Protocol (MCP) server for Jira ticket management. This server enables AI assistants like Claude to interact with self-hosted Jira instances using Personal Access Token (PAT) authentication.

## Features

### Ticket Management
- **List Tickets**: Search and filter tickets by assignee, project, component, epic, and status
- **View Ticket Details**: Get full ticket information including description, components, labels, and comments
- **Create Tickets**: Create new issues with customizable fields (type, assignee, components, epic, priority, labels)
- **Update Tickets**: Modify ticket title, description, assignee, status, components, and priority
- **Manage Comments**: Add, update, and delete comments

### Issue Hierarchy & Linking
- **Link Issues**: Create relationships between issues (relates to, blocks, duplicates, etc.)
- **Create Subtasks**: Add sub-tasks under parent issues
- **Set Epic**: Associate issues with epics

### Discovery/Metadata
- **List Projects**: View all accessible projects
- **List Components**: Get available components for a project
- **List Issue Types**: Get available issue types (Task, Bug, Story, Epic, etc.)
- **List Priorities**: Get available priority levels
- **List Statuses**: Get available workflow statuses for a project
- **Get Transitions**: See available workflow transitions for a ticket
- **Get Current User**: Get authenticated user information

### 📊 Activity Tracking & Reports (NEW)
- **Log Activity**: Track your work on Jira tickets throughout the week
- **Get Weekly Activity**: View summary of tickets worked on
- **Generate Weekly Report**: Create activity-based reports from logged work
- **Save Reports**: Persist reports to database for future reference

### 📋 Management Reports (NEW)
- **Save Management Report**: Store AI-generated project progress reports for stakeholders
- **List/Get/Update/Delete**: Full CRUD for management reports
- High-level, non-technical summaries with Jira links
- Perfect for weekly status updates to management

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
| `DATABASE_URL` | No | PostgreSQL URL (leave empty for SQLite) |
| `JIRA_MCP_DATA_DIR` | No | Directory for SQLite database (default: `./data`) |

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

## 🐳 Container Deployment

### Quick Start with Docker Compose

1. Copy the environment file and configure:
   ```bash
   cp env.example .env
   # Edit .env with your Jira credentials
   ```

2. Start the server:
   ```bash
   # SQLite mode (default - simple, file-based)
   docker-compose up -d jira-mcp

   # PostgreSQL mode (production-ready)
   docker-compose --profile postgres up -d
   ```

3. Access the server at `http://localhost:8080/sse`

### Build Container Image

```bash
# Using Podman
podman build -t jira-mcp:latest -f Containerfile .

# Using Docker
docker build -t jira-mcp:latest -f Containerfile .
```

### Run Container Manually

```bash
# With SQLite (data persisted in volume)
docker run -d \
  -p 8080:8080 \
  -v jira-mcp-data:/app/data \
  -e JIRA_SERVER_URL=https://jira.example.com \
  -e JIRA_PERSONAL_ACCESS_TOKEN=your-token \
  --name jira-mcp \
  jira-mcp:latest

# With PostgreSQL
docker run -d \
  -p 8080:8080 \
  -e JIRA_SERVER_URL=https://jira.example.com \
  -e JIRA_PERSONAL_ACCESS_TOKEN=your-token \
  -e DATABASE_URL=postgresql://user:pass@host:5432/jira_mcp \
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

#### Ticket Management

##### `jira_list_tickets`

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

##### `jira_get_ticket`

Get full details of a ticket.

```json
{
  "ticket_key": "PROJ-123"
}
```

##### `jira_create_ticket`

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

##### `jira_update_ticket`

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

#### Comment Management

##### `jira_add_comment`

Add a comment to a ticket.

```json
{
  "ticket_key": "PROJ-123",
  "body": "This is a comment with *Jira markup* support."
}
```

##### `jira_get_comments`

Get comments from a ticket.

```json
{
  "ticket_key": "PROJ-123",
  "max_results": 20
}
```

##### `jira_update_comment`

Update an existing comment.

```json
{
  "ticket_key": "PROJ-123",
  "comment_id": "12345",
  "body": "Updated comment text"
}
```

##### `jira_delete_comment`

Delete a comment.

```json
{
  "ticket_key": "PROJ-123",
  "comment_id": "12345"
}
```

#### Issue Linking & Hierarchy

##### `jira_link_issues`

Link two issues together.

```json
{
  "from_key": "PROJ-123",
  "to_key": "PROJ-456",
  "link_type": "blocks"
}
```

##### `jira_create_subtask`

Create a subtask under a parent issue.

```json
{
  "parent_key": "PROJ-123",
  "summary": "Subtask title",
  "description": "Subtask description",
  "assignee": "john.doe"
}
```

##### `jira_set_epic`

Set or change the epic for an issue.

```json
{
  "issue_key": "PROJ-123",
  "epic_key": "PROJ-100"
}
```

#### Discovery/Metadata Tools

##### `jira_list_projects`

List all accessible projects. No parameters required.

##### `jira_list_components`

List components for a project.

```json
{
  "project": "PROJ"
}
```

##### `jira_list_issue_types`

List issue types available for a project.

```json
{
  "project": "PROJ"
}
```

##### `jira_list_priorities`

List all available priorities. No parameters required.

##### `jira_list_statuses`

List available statuses for a project.

```json
{
  "project": "PROJ"
}
```

##### `jira_get_transitions`

Get available workflow transitions for a ticket.

```json
{
  "ticket_key": "PROJ-123"
}
```

##### `jira_get_current_user`

Get information about the authenticated user. No parameters required.

### 📊 Activity Tracking & Weekly Reports

These tools help you track your work and generate executive-style weekly reports.

##### `log_jira_activity`

Log when you work on a ticket (for weekly report tracking).

```json
{
  "ticket_key": "PROJ-123",
  "action_type": "update",
  "ticket_summary": "Fix login bug"
}
```

**Action Types:** `view`, `create`, `update`, `comment`, `transition`, `link`, `other`

##### `get_weekly_activity`

Get summary of activity for a specific week.

```json
{
  "week_offset": 0,
  "project": "PROJ"
}
```

**Response:**
```json
{
  "username": "john.doe",
  "week_start": "2026-01-13",
  "week_end": "2026-01-19",
  "total_activities": 15,
  "unique_tickets": [
    {"ticket_key": "PROJ-123", "ticket_summary": "Fix login bug", "action_count": 5}
  ],
  "by_action_type": {
    "update": [...],
    "comment": [...]
  }
}
```

##### `generate_weekly_report`

Generate an executive-style weekly report (Markdown format).

```json
{
  "week_offset": 0,
  "include_details": true
}
```

**Response includes:**
- Title and summary
- Key metrics (tickets worked on, created, updated, etc.)
- Full Markdown report with tables

##### `save_weekly_report`

Save a generated report to the database.

```json
{
  "week_offset": 0,
  "custom_title": "Sprint 42 Report",
  "custom_summary": "Focused on performance improvements"
}
```

##### `list_saved_reports`

List previously saved reports.

```json
{
  "limit": 10
}
```

##### `get_saved_report`

Get a saved report by ID.

```json
{
  "report_id": 1
}
```

##### `delete_saved_report`

Delete a saved report.

```json
{
  "report_id": 1
}
```

### 📋 Management Reports (AI-Generated)

These tools store **AI-written** management reports. Cursor writes the content, these tools save it.

##### `save_management_report`

Save an AI-generated management report for high-level stakeholders.

```json
{
  "title": "APPENG Project Progress - Week 3",
  "executive_summary": "Completed OAuth integration and resolved 3 critical production issues. On track for Q1 milestone.",
  "content": "# Project Progress Report\n\n## Highlights\n- Completed OAuth token refresh implementation\n- Fixed 3 critical production bugs\n\n## Key Deliverables\n- [APPENG-4112](https://jira.example.com/browse/APPENG-4112): OAuth integration\n- [APPENG-4256](https://jira.example.com/browse/APPENG-4256): Performance fix\n\n## Next Week\n- API rate limiting implementation\n- Documentation updates",
  "project_key": "APPENG",
  "report_period": "Week 3, January 2026",
  "referenced_tickets": ["APPENG-4112", "APPENG-4256", "APPENG-4257"]
}
```

##### `list_management_reports`

List saved management reports, optionally filtered by project.

```json
{
  "project_key": "APPENG",
  "limit": 10
}
```

##### `get_management_report`

Get a saved management report with full content.

```json
{
  "report_id": 1
}
```

##### `update_management_report`

Update an existing management report.

```json
{
  "report_id": 1,
  "executive_summary": "Updated summary with new information."
}
```

##### `delete_management_report`

Delete a management report.

```json
{
  "report_id": 1
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
│       ├── db/                  # Database layer
│       │   ├── __init__.py
│       │   ├── database.py      # SQLite/PostgreSQL connection
│       │   └── models.py        # SQLAlchemy models
│       └── tools/
│           ├── __init__.py      # Tools exports
│           ├── tickets.py       # Ticket operations
│           ├── comments.py      # Comment operations
│           ├── discovery.py     # Discovery/metadata operations
│           ├── reports.py       # Activity tracking & reports
│           └── schemas.py       # Pydantic schemas
├── tests/                       # Test files
├── Containerfile               # Container build file
├── docker-compose.yaml         # Full deployment stack
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

### Database Errors

- Ensure the data directory is writable (`JIRA_MCP_DATA_DIR`)
- For PostgreSQL: verify connection string and credentials
- Check that SQLAlchemy and psycopg2-binary are installed

### Missing Environment Variables

If you see "JIRA_SERVER_URL environment variable is required", make sure you've configured the environment variables in your MCP client settings (not in a `.env` file on the server).

## License

MIT License - See LICENSE file for details.
