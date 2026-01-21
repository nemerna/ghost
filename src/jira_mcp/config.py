"""Configuration management for Jira MCP Server."""

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# Default instructions for management report generation
DEFAULT_MANAGEMENT_REPORT_INSTRUCTIONS = """
# Management Report Generation Instructions

You are generating weekly status updates for directors and executive management.

## Audience & Purpose
- **Audience**: Directors and executive-level management
- **Purpose**: Information sharing across teams and higher-level organizations

## Critical Rules

### 1. NO Raw Jira Ticket Numbers
WRONG: "Worked on PROJ-7654"
RIGHT: "[Implemented](PR-URL) [user authentication](JIRA-URL) for the platform"

Never write ticket numbers like "PROJ-123" in the text. Summarize what the ticket is about and hyperlink that summary to the Jira URL.

### 2. Embed Links Naturally - Never Append
WRONG: "Fixed the login bug. (JIRA: PROJ-123, PR: #456)"
RIGHT: "[Fixed](PR-URL) the [login bug](JIRA-URL) affecting mobile users"

### 3. Link Action Verbs to PRs/MRs
The action verb (Completed, Implemented, Fixed) should link to the GitHub PR or GitLab MR.

### 4. Link Description to Issue
The first few words describing the work should link to the Jira issue.

### 5. Keep Updates Concise
Each item should be 1-2 sentences maximum.

## Formatting Template
Each status item follows this pattern:
```
[Action Verb](PR-URL) [brief description](JIRA-URL) plus any additional context.
```

## Style Requirements
1. **No abbreviations/acronyms**: Spell out terms for clarity
2. **Team-centric language**: Say "the team" or "stakeholders", never individual names
3. **Short link text**: Keep linked text brief
4. **No private links**: Only link to accessible documents

## Report Structure

### Completed This Week
List items that were finished/merged/resolved.

### In Progress
List substantial ongoing work.

### Blockers (if any)
Only include if there are actual blockers.

## Example Output
- [Completed](https://github.com/org/repo/pull/160) the [security mitigation](https://jira.example.com/browse/PROJ-1012) to minimize RBAC permissions
- [Implemented](https://github.com/org/repo/pull/1) the [workflow API](https://jira.example.com/browse/PROJ-896) and addressed review comments
- [Started](https://github.com/org/repo/pull/6) [work](https://jira.example.com/browse/PROJ-789) on promoting the workflow to production

## Field Mapping for save_management_report
- **one_liner**: Single sentence (max 15 words), no links
- **executive_summary**: 2-3 sentences, high-level outcomes, no links
- **content**: Full Markdown report with properly embedded links
- **referenced_tickets**: Array of all Jira ticket keys mentioned
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

    # Management Report Instructions
    management_report_instructions_file: Optional[str] = Field(
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
        Path.home() / ".config" / "jira-mcp" / "management_report_instructions.md",
    ]
    
    for path in default_paths:
        if path.exists():
            return path.read_text(encoding="utf-8").strip()
    
    return DEFAULT_MANAGEMENT_REPORT_INSTRUCTIONS

