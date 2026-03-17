"""Main FastAPI application for Ghost UI API.

Note: Static frontend files are served by nginx, not FastAPI.
FastAPI only handles /api/* routes.
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ghost.api.middleware import OAuthProxyMiddleware
from ghost.db import init_db

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown."""
    # Startup
    logger.info("Starting Ghost API...")
    init_db()
    logger.info("Database initialized")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Ghost API...")


def create_app(
    dev_mode: bool | None = None,
    dev_email: str | None = None,
) -> FastAPI:
    """Create and configure the FastAPI application.
    
    Args:
        dev_mode: Enable development mode (bypass OAuth). 
                  Defaults to DEV_MODE env var.
        dev_email: Email to use in dev mode.
                   Defaults to DEV_EMAIL env var.
    
    Returns:
        Configured FastAPI application
    """
    # Read config from environment if not provided
    if dev_mode is None:
        dev_mode = os.environ.get("DEV_MODE", "false").lower() in ("true", "1", "yes")
    if dev_email is None:
        dev_email = os.environ.get("DEV_EMAIL", "dev@example.com")
    
    app = FastAPI(
        title="Ghost API",
        description="REST API for Ghost activity tracking and reporting UI",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/api/docs" if dev_mode else None,  # Only enable docs in dev mode
        redoc_url="/api/redoc" if dev_mode else None,
        openapi_url="/api/openapi.json" if dev_mode else None,
    )
    
    # CORS middleware (configure for your frontend domain in production)
    cors_origins = os.environ.get("CORS_ORIGINS", "*").split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # OAuth proxy middleware
    app.add_middleware(
        OAuthProxyMiddleware,
        dev_mode=dev_mode,
        dev_email=dev_email if dev_mode else None,
    )
    
    # Register API routes
    from ghost.api.routes import (
        activities_router,
        fields_router,
        github_tokens_router,
        health_router,
        reports_router,
        teams_router,
        tokens_router,
        users_router,
    )
    
    app.include_router(health_router, prefix="/api", tags=["health"])
    app.include_router(users_router, prefix="/api/users", tags=["users"])
    app.include_router(teams_router, prefix="/api/teams", tags=["teams"])
    app.include_router(activities_router, prefix="/api/activities", tags=["activities"])
    app.include_router(reports_router, prefix="/api/reports", tags=["reports"])
    app.include_router(fields_router, prefix="/api/fields", tags=["fields"])
    app.include_router(tokens_router, prefix="/api/tokens", tags=["tokens"])
    app.include_router(github_tokens_router, prefix="/api/github-tokens", tags=["github-tokens"])
    
    # Note: Static frontend files are served by nginx, not FastAPI
    # FastAPI only handles /api/* routes
    
    logger.info(f"Ghost API created (dev_mode={dev_mode})")
    return app


# Default app instance for uvicorn
app = create_app()
