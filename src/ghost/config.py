"""Configuration management for Ghost Server."""

import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Default instructions for management report generation
DEFAULT_MANAGEMENT_REPORT_INSTRUCTIONS = """
# Management Report Generation Instructions

Generate a management report using **structured entries** for per-item visibility control.

## Link Formatting Rules

### NO Raw Ticket Numbers
WRONG: "Worked on PROJ-7654"
RIGHT: "[Completed](PR-URL) [user authentication](ISSUE-URL)"

### Embed Links Naturally
WRONG: "Fixed the login bug. (JIRA: PROJ-123, PR: #456)"
RIGHT: "[Fixed](PR-URL) the [login bug](ISSUE-URL)"

### Format
Each entry follows this pattern:
[Action Verb](PR-URL) [brief description](ISSUE-URL) plus any additional context.

Action verbs: Completed, Implemented, Fixed, Added, Updated, Started, etc.

## Report Content

The report is ONLY a list of work items. No sections, no headers, no summaries, no future plans.

## CRITICAL: Use Structured Entries Format

You MUST use the `entries` parameter (NOT `content`) when calling save_management_report.

Each entry is an object with:
- **text**: The work item description with embedded links
- **ticket_key**: The Jira ticket key (e.g., "PROJ-123") - REQUIRED for visibility inheritance
- **private**: Optional boolean (default: false) - set to true only if you want to explicitly hide

### Why ticket_key Matters
When you include `ticket_key`, the system automatically checks if the user has marked that activity as private. If so, the entry is auto-hidden from managers. This ensures the user's visibility preferences are respected.

### Example Tool Call

```json
{
  "title": "Week 4, January 2026",
  "entries": [
    {
      "text": "[Completed](https://github.com/org/repo/pull/160) the [security mitigation](https://jira.example.com/browse/PROJ-1012) to minimize RBAC permissions",
      "ticket_key": "PROJ-1012"
    },
    {
      "text": "[Implemented](https://github.com/org/repo/pull/1) the [workflow API](https://jira.example.com/browse/PROJ-896) and addressed review comments",
      "ticket_key": "PROJ-896"
    },
    {
      "text": "[Started](https://github.com/org/repo/pull/6) [work](https://jira.example.com/browse/PROJ-789) on promoting the workflow to production",
      "ticket_key": "PROJ-789"
    }
  ],
  "referenced_tickets": ["PROJ-1012", "PROJ-896", "PROJ-789"]
}
```

## Field Mapping for save_management_report
- **title**: Report title (e.g., "Week 4, January 2026")
- **entries**: Array of entry objects (REQUIRED - use this instead of content)
  - **text**: Work item description with embedded links
  - **ticket_key**: Jira ticket key for auto-visibility (ALWAYS include this)
  - **private**: Optional, explicitly hide from manager
- **referenced_tickets**: Array of all ticket keys mentioned (for indexing)
- **project_key**: Optional project key
- **report_period**: Optional period description
""".strip()


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
    jira_default_project: str | None = Field(
        default=None,
        description="Default Jira project key to use when not specified",
    )

    # GitHub Configuration (optional)
    github_personal_access_token: str | None = Field(
        default=None,
        description="Personal Access Token for GitHub API authentication",
    )
    github_api_url: str | None = Field(
        default=None,
        description="GitHub API base URL (for GitHub Enterprise). Leave empty for github.com",
    )

    # Management Report Instructions
    management_report_instructions_file: str | None = Field(
        default=None,
        description="Path to a file containing custom management report instructions. If not set, uses default instructions.",
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


def get_management_report_instructions() -> str:
    """
    Get management report instructions.

    Loads from file if MANAGEMENT_REPORT_INSTRUCTIONS_FILE is set,
    otherwise returns default instructions.
    """
    # Check environment variable for file path
    instructions_file = os.environ.get("MANAGEMENT_REPORT_INSTRUCTIONS_FILE")

    if instructions_file:
        path = Path(instructions_file)
        if path.exists():
            return path.read_text(encoding="utf-8").strip()

    # Also check for a default location
    default_paths = [
        Path("management_report_instructions.md"),
        Path("config/management_report_instructions.md"),
        Path.home() / ".config" / "ghost" / "management_report_instructions.md",
    ]

    for path in default_paths:
        if path.exists():
            return path.read_text(encoding="utf-8").strip()

    return DEFAULT_MANAGEMENT_REPORT_INSTRUCTIONS
