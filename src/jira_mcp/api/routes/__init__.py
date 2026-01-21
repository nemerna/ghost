"""API route modules."""

from jira_mcp.api.routes.activities import router as activities_router
from jira_mcp.api.routes.health import router as health_router
from jira_mcp.api.routes.reports import router as reports_router
from jira_mcp.api.routes.teams import router as teams_router
from jira_mcp.api.routes.users import router as users_router

__all__ = [
    "health_router",
    "users_router",
    "teams_router",
    "activities_router",
    "reports_router",
]
