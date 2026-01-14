"""Configuration management for Jira MCP Server."""

from functools import lru_cache
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Jira Configuration
    jira_server_url: str = Field(
        ...,
        description="Base URL of the Jira server (e.g., https://jira.example.com)",
    )
    jira_personal_access_token: str = Field(
        ...,
        description="Personal Access Token for Jira authentication",
    )
    jira_verify_ssl: bool = Field(
        default=True,
        description="Whether to verify SSL certificates when connecting to Jira",
    )

    # MCP Server Configuration
    mcp_server_host: str = Field(
        default="0.0.0.0",
        description="Host address for the MCP server",
    )
    mcp_server_port: int = Field(
        default=8080,
        description="Port for the MCP server",
    )

    # Optional: Default project for operations
    jira_default_project: Optional[str] = Field(
        default=None,
        description="Default Jira project key to use when not specified",
    )

    # GitHub Configuration (optional)
    github_personal_access_token: Optional[str] = Field(
        default=None,
        description="Personal Access Token for GitHub API authentication",
    )
    github_api_url: Optional[str] = Field(
        default=None,
        description="GitHub API base URL (for GitHub Enterprise). Leave empty for github.com",
    )

    @field_validator("jira_server_url")
    @classmethod
    def validate_server_url(cls, v: str) -> str:
        """Ensure server URL doesn't have a trailing slash."""
        return v.rstrip("/")

    @field_validator("mcp_server_port")
    @classmethod
    def validate_port(cls, v: int) -> int:
        """Ensure port is in valid range."""
        if not 1 <= v <= 65535:
            raise ValueError("Port must be between 1 and 65535")
        return v


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()

