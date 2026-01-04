"""MCP Server for Jira with FastAPI and SSE transport."""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent
from sse_starlette.sse import EventSourceResponse

from jira_mcp.config import get_settings
from jira_mcp.jira_client import JiraClient, JiraClientError, get_jira_client
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
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create MCP Server
mcp_server = Server("jira-mcp")

# SSE Transport
sse_transport = SseServerTransport("/messages")


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


# --- FastAPI Application ---


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan handler."""
    logger.info("Starting Jira MCP Server...")
    yield
    logger.info("Shutting down Jira MCP Server...")


app = FastAPI(
    title="Jira MCP Server",
    description="Model Context Protocol server for Jira ticket management",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/sse")
async def sse_endpoint(request: Request) -> EventSourceResponse:
    """SSE endpoint for MCP communication."""

    async def event_generator() -> AsyncIterator[dict[str, Any]]:
        """Generate SSE events from MCP server."""
        async with sse_transport.connect_sse(
            request.scope, request.receive, request._send
        ) as streams:
            await mcp_server.run(
                streams[0],
                streams[1],
                mcp_server.create_initialization_options(),
            )

    return EventSourceResponse(event_generator())


@app.post("/messages")
async def messages_endpoint(request: Request) -> JSONResponse:
    """Handle incoming MCP messages."""
    body = await request.body()
    await sse_transport.handle_post_message(request.scope, request.receive, request._send)
    return JSONResponse({"status": "ok"})


def main() -> None:
    """Run the MCP server."""
    settings = get_settings()
    logger.info(f"Starting server on {settings.mcp_server_host}:{settings.mcp_server_port}")

    uvicorn.run(
        "jira_mcp.server:app",
        host=settings.mcp_server_host,
        port=settings.mcp_server_port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()

