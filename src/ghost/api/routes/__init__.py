"""API route modules."""

from ghost.api.routes.activity import router as activity_router
from ghost.api.routes.fields import router as fields_router
from ghost.api.routes.github_tokens import router as github_tokens_router
from ghost.api.routes.goals import router as goals_router
from ghost.api.routes.health import router as health_router
from ghost.api.routes.reports import router as reports_router
from ghost.api.routes.teams import router as teams_router
from ghost.api.routes.tokens import router as tokens_router
from ghost.api.routes.users import router as users_router

__all__ = [
    "health_router",
    "users_router",
    "teams_router",
    "reports_router",
    "fields_router",
    "tokens_router",
    "github_tokens_router",
    "goals_router",
    "activity_router",
]
