"""MCP Server for Jira with stdio and SSE transport support."""

import argparse
import asyncio
import json
import logging
import os
import sys
from contextvars import ContextVar
from typing import Any, Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from jira_mcp.jira_client import JiraClient, JiraClientError

from jira_mcp.tools.schemas import (
    ListTicketsInput,
    GetTicketInput,
    CreateTicketInput,
    UpdateTicketInput,
    AddCommentInput,
    GetCommentsInput,
    ListComponentsInput,
    ListIssueTypesInput,
    ListStatusesInput,
    GetTransitionsInput,
)

# Configure logging
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger(__name__)

# Create MCP Server
mcp_server = Server("jira-mcp")

# Context variable for per-connection Jira client (used in SSE mode)
_jira_client_ctx: ContextVar[Optional[JiraClient]] = ContextVar("jira_client", default=None)

# Global Jira client for stdio mode
_jira_client_global: Optional[JiraClient] = None


def create_jira_client(
    server_url: Optional[str] = None,
    token: Optional[str] = None,
    verify_ssl: bool = True,
) -> JiraClient:
    """Create a Jira client with the given or environment configuration."""
    # Use provided values or fall back to environment variables
    server_url = server_url or os.environ.get("JIRA_SERVER_URL")
    token = token or os.environ.get("JIRA_PERSONAL_ACCESS_TOKEN")
    
    if verify_ssl is True:
        # Check environment variable
        env_verify = os.environ.get("JIRA_VERIFY_SSL", "true").lower()
        verify_ssl = env_verify in ("true", "1", "yes")
    
    if not server_url:
        raise ValueError(
            "Jira server URL is required. "
            "Set X-Jira-Server-URL header or JIRA_SERVER_URL environment variable."
        )
    if not token:
        raise ValueError(
            "Jira token is required. "
            "Set X-Jira-Token header or JIRA_PERSONAL_ACCESS_TOKEN environment variable."
        )
    
    return JiraClient(
        server_url=server_url,
        token=token,
        verify_ssl=verify_ssl,
    )


def get_jira_client() -> JiraClient:
    """Get Jira client from context (SSE) or global (stdio)."""
    # First try context variable (set per SSE connection)
    client = _jira_client_ctx.get()
    if client is not None:
        return client
    
    # Fall back to global client (stdio mode)
    global _jira_client_global
    if _jira_client_global is None:
        _jira_client_global = create_jira_client()
    return _jira_client_global


# --- MCP Tool Definitions ---

TOOLS: list[Tool] = [
    Tool(
        name="jira_list_tickets",
        description="List Jira tickets with optional filters. Returns ticket summaries including key, summary, status, assignee, and priority.",
        inputSchema={
            "type": "object",
            "properties": {
                "assignee": {
                    "type": "string",
                    "description": "Filter by assignee username. Use 'currentUser' for the authenticated user.",
                },
                "project": {
                    "type": "string",
                    "description": "Filter by project key (e.g., 'PROJ').",
                },
                "component": {
                    "type": "string",
                    "description": "Filter by component name.",
                },
                "epic_key": {
                    "type": "string",
                    "description": "Filter by epic issue key (e.g., 'PROJ-100').",
                },
                "status": {
                    "type": "string",
                    "description": "Filter by issue status (e.g., 'Open', 'In Progress', 'Done').",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return (1-100). Default: 50.",
                    "default": 50,
                    "minimum": 1,
                    "maximum": 100,
                },
            },
        },
    ),
    Tool(
        name="jira_get_ticket",
        description="Get full details of a specific Jira ticket including description, components, labels, comments count, and epic link.",
        inputSchema={
            "type": "object",
            "properties": {
                "ticket_key": {
                    "type": "string",
                    "description": "The issue key (e.g., 'PROJ-123').",
                },
            },
            "required": ["ticket_key"],
        },
    ),
    Tool(
        name="jira_create_ticket",
        description="Create a new Jira ticket with specified fields. Returns the created ticket key and URL.",
        inputSchema={
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Project key (e.g., 'PROJ').",
                },
                "summary": {
                    "type": "string",
                    "description": "Issue title/summary.",
                },
                "description": {
                    "type": "string",
                    "description": "Issue description (supports Jira wiki markup).",
                },
                "issue_type": {
                    "type": "string",
                    "description": "Issue type (e.g., 'Task', 'Bug', 'Story', 'Epic'). Default: 'Task'.",
                    "default": "Task",
                },
                "assignee": {
                    "type": "string",
                    "description": "Assignee username.",
                },
                "components": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of component names.",
                },
                "epic_key": {
                    "type": "string",
                    "description": "Parent epic issue key.",
                },
                "priority": {
                    "type": "string",
                    "description": "Priority name (e.g., 'High', 'Medium', 'Low').",
                },
                "labels": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of labels.",
                },
            },
            "required": ["project", "summary"],
        },
    ),
    Tool(
        name="jira_update_ticket",
        description="Update an existing Jira ticket's fields including title, description, assignee, status, components, and priority.",
        inputSchema={
            "type": "object",
            "properties": {
                "ticket_key": {
                    "type": "string",
                    "description": "The issue key (e.g., 'PROJ-123').",
                },
                "summary": {
                    "type": "string",
                    "description": "New issue title/summary.",
                },
                "description": {
                    "type": "string",
                    "description": "New issue description (supports Jira wiki markup).",
                },
                "assignee": {
                    "type": "string",
                    "description": "New assignee username. Use empty string to unassign.",
                },
                "status": {
                    "type": "string",
                    "description": "Transition to this status (e.g., 'In Progress', 'Done').",
                },
                "components": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "New list of component names (replaces existing).",
                },
                "priority": {
                    "type": "string",
                    "description": "New priority name.",
                },
            },
            "required": ["ticket_key"],
        },
    ),
    Tool(
        name="jira_add_comment",
        description="Add a comment to a Jira ticket. Supports Jira wiki markup in the comment body.",
        inputSchema={
            "type": "object",
            "properties": {
                "ticket_key": {
                    "type": "string",
                    "description": "The issue key (e.g., 'PROJ-123').",
                },
                "body": {
                    "type": "string",
                    "description": "Comment body (supports Jira wiki markup).",
                },
            },
            "required": ["ticket_key", "body"],
        },
    ),
    Tool(
        name="jira_get_comments",
        description="Get comments from a Jira ticket. Returns comment ID, author, body, and timestamps.",
        inputSchema={
            "type": "object",
            "properties": {
                "ticket_key": {
                    "type": "string",
                    "description": "The issue key (e.g., 'PROJ-123').",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of comments to return (1-100). Default: 20.",
                    "default": 20,
                    "minimum": 1,
                    "maximum": 100,
                },
            },
            "required": ["ticket_key"],
        },
    ),
    # --- Discovery/Metadata Tools ---
    Tool(
        name="jira_list_projects",
        description="List all accessible Jira projects. Returns project key, name, lead, and URL for each project.",
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
    Tool(
        name="jira_list_components",
        description="List components available in a Jira project. Useful for knowing valid component names when creating or filtering tickets.",
        inputSchema={
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Project key (e.g., 'PROJ').",
                },
            },
            "required": ["project"],
        },
    ),
    Tool(
        name="jira_list_issue_types",
        description="List issue types available in a Jira project. Returns types like Task, Bug, Story, Epic, etc.",
        inputSchema={
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Project key (e.g., 'PROJ').",
                },
            },
            "required": ["project"],
        },
    ),
    Tool(
        name="jira_list_priorities",
        description="List all available priority levels in Jira. Returns priority names like High, Medium, Low, etc.",
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
    Tool(
        name="jira_list_statuses",
        description="List available statuses for a Jira project. Returns status names and their categories (To Do, In Progress, Done).",
        inputSchema={
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Project key (e.g., 'PROJ').",
                },
            },
            "required": ["project"],
        },
    ),
    Tool(
        name="jira_get_transitions",
        description="Get available workflow transitions for a specific ticket. Shows what status changes are possible from the current state.",
        inputSchema={
            "type": "object",
            "properties": {
                "ticket_key": {
                    "type": "string",
                    "description": "The issue key (e.g., 'PROJ-123').",
                },
            },
            "required": ["ticket_key"],
        },
    ),
    Tool(
        name="jira_get_current_user",
        description="Get information about the currently authenticated user. Returns username, display name, email, and timezone.",
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
]


@mcp_server.list_tools()
async def list_tools() -> list[Tool]:
    """List available MCP tools."""
    return TOOLS


@mcp_server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls from MCP clients."""
    try:
        jira_client = get_jira_client()
        result = await _execute_tool(name, arguments, jira_client)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    except JiraClientError as e:
        error_response = {
            "error": True,
            "message": e.message,
            "status_code": e.status_code,
        }
        return [TextContent(type="text", text=json.dumps(error_response, indent=2))]
    except Exception as e:
        logger.exception(f"Error executing tool {name}")
        error_response = {
            "error": True,
            "message": str(e),
        }
        return [TextContent(type="text", text=json.dumps(error_response, indent=2))]


async def _execute_tool(
    name: str, arguments: dict[str, Any], jira_client: JiraClient
) -> dict[str, Any] | list[dict[str, Any]]:
    """Execute a specific tool and return the result."""

    if name == "jira_list_tickets":
        input_data = ListTicketsInput(**arguments)
        jql = jira_client.build_jql(
            assignee=input_data.assignee,
            project=input_data.project,
            component=input_data.component,
            epic_key=input_data.epic_key,
            status=input_data.status,
        )
        return jira_client.search_issues(jql, max_results=input_data.max_results)

    elif name == "jira_get_ticket":
        input_data = GetTicketInput(**arguments)
        return jira_client.get_issue(input_data.ticket_key)

    elif name == "jira_create_ticket":
        input_data = CreateTicketInput(**arguments)
        return jira_client.create_issue(
            project=input_data.project,
            summary=input_data.summary,
            description=input_data.description,
            issue_type=input_data.issue_type,
            assignee=input_data.assignee,
            components=input_data.components,
            epic_key=input_data.epic_key,
            priority=input_data.priority,
            labels=input_data.labels,
        )

    elif name == "jira_update_ticket":
        input_data = UpdateTicketInput(**arguments)
        return jira_client.update_issue(
            issue_key=input_data.ticket_key,
            summary=input_data.summary,
            description=input_data.description,
            assignee=input_data.assignee,
            status=input_data.status,
            components=input_data.components,
            priority=input_data.priority,
        )

    elif name == "jira_add_comment":
        input_data = AddCommentInput(**arguments)
        return jira_client.add_comment(
            issue_key=input_data.ticket_key,
            body=input_data.body,
        )

    elif name == "jira_get_comments":
        input_data = GetCommentsInput(**arguments)
        return jira_client.get_comments(
            issue_key=input_data.ticket_key,
            max_results=input_data.max_results,
        )

    # --- Discovery/Metadata Tools ---

    elif name == "jira_list_projects":
        return jira_client.get_projects()

    elif name == "jira_list_components":
        input_data = ListComponentsInput(**arguments)
        return jira_client.get_components(input_data.project)

    elif name == "jira_list_issue_types":
        input_data = ListIssueTypesInput(**arguments)
        return jira_client.get_issue_types(input_data.project)

    elif name == "jira_list_priorities":
        return jira_client.get_priorities()

    elif name == "jira_list_statuses":
        input_data = ListStatusesInput(**arguments)
        return jira_client.get_statuses(input_data.project)

    elif name == "jira_get_transitions":
        input_data = GetTransitionsInput(**arguments)
        return jira_client.get_transitions(input_data.ticket_key)

    elif name == "jira_get_current_user":
        return jira_client.get_current_user()

    else:
        raise ValueError(f"Unknown tool: {name}")


# --- Transport Implementations ---


async def run_stdio() -> None:
    """Run the MCP server with stdio transport (for Cursor/Claude Desktop)."""
    logger.info("Starting Jira MCP server with stdio transport")
    
    async with stdio_server() as (read_stream, write_stream):
        await mcp_server.run(
            read_stream,
            write_stream,
            mcp_server.create_initialization_options(),
        )


async def run_sse(host: str, port: int) -> None:
    """Run the MCP server with SSE transport (HTTP server mode)."""
    import uvicorn
    from mcp.server.sse import SseServerTransport
    from starlette.applications import Starlette
    from starlette.requests import Request
    from starlette.responses import JSONResponse, Response
    from starlette.routing import Mount, Route
    from starlette.types import Receive, Scope, Send

    logger.info(f"Starting Jira MCP server with SSE transport on {host}:{port}")

    # SSE Transport
    sse_transport = SseServerTransport("/messages/")

    async def health_check(request: Request) -> JSONResponse:
        """Health check endpoint."""
        return JSONResponse({"status": "healthy"})

    async def handle_sse_raw(scope: Scope, receive: Receive, send: Send) -> None:
        """Handle SSE connection as raw ASGI app."""
        # Extract headers from scope
        headers = dict(scope.get("headers", []))
        
        # Get Jira configuration from headers (case-insensitive)
        server_url = None
        token = None
        verify_ssl = True
        
        for key, value in headers.items():
            key_lower = key.decode("utf-8").lower() if isinstance(key, bytes) else key.lower()
            value_str = value.decode("utf-8") if isinstance(value, bytes) else value
            
            if key_lower == "x-jira-server-url":
                server_url = value_str
            elif key_lower == "x-jira-token":
                token = value_str
            elif key_lower == "x-jira-verify-ssl":
                verify_ssl = value_str.lower() in ("true", "1", "yes")
        
        # Create client and set in context
        try:
            client = create_jira_client(
                server_url=server_url,
                token=token,
                verify_ssl=verify_ssl,
            )
            _jira_client_ctx.set(client)
            logger.info(f"SSE connection established with Jira server: {client.server_url}")
        except ValueError as e:
            logger.warning(f"Jira client configuration: {e}")
            # Will fail when tool is called if not configured
        
        async with sse_transport.connect_sse(scope, receive, send) as streams:
            await mcp_server.run(
                streams[0],
                streams[1],
                mcp_server.create_initialization_options(),
            )

    async def handle_sse(request: Request) -> Response:
        """Handle SSE connection - wrapper for Starlette Route."""
        await handle_sse_raw(request.scope, request.receive, request._send)
        return Response()

    # Create Starlette app with routes
    app = Starlette(
        debug=False,
        routes=[
            Route("/health", endpoint=health_check, methods=["GET"]),
            Route("/sse", endpoint=handle_sse, methods=["GET"]),
            Mount("/messages/", app=sse_transport.handle_post_message),
        ],
    )

    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="info",
    )
    server = uvicorn.Server(config)
    await server.serve()


def main() -> None:
    """Run the MCP server."""
    parser = argparse.ArgumentParser(
        description="Jira MCP Server - Model Context Protocol server for Jira",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with stdio transport (default, for Cursor/Claude Desktop)
  jira-mcp

  # Run with SSE transport (HTTP server mode)
  jira-mcp --transport sse --host 0.0.0.0 --port 8080

Configuration:
  For stdio transport: Set environment variables or pass via MCP client config
  For SSE transport: Set via HTTP headers or environment variables

  Headers (SSE mode):
    X-Jira-Server-URL    Jira server URL
    X-Jira-Token         Personal Access Token  
    X-Jira-Verify-SSL    Verify SSL (true/false)

  Environment Variables:
    JIRA_SERVER_URL              Jira server URL
    JIRA_PERSONAL_ACCESS_TOKEN   Personal Access Token
    JIRA_VERIFY_SSL              Verify SSL certificates (default: true)
        """,
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="Transport type: 'stdio' for Cursor/Claude Desktop, 'sse' for HTTP server (default: stdio)",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host address for SSE transport (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port for SSE transport (default: 8080)",
    )

    args = parser.parse_args()

    if args.transport == "stdio":
        asyncio.run(run_stdio())
    else:
        asyncio.run(run_sse(args.host, args.port))


if __name__ == "__main__":
    main()
