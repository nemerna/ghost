"""MCP Tools for management report tools."""

from ghost.tools.reports import (
    delete_management_report,
    detect_project_for_activity,
    get_management_report,
    list_management_reports,
    redetect_project_assignments,
    save_management_report,
    update_management_report,
)

__all__ = [
    # Management Reports
    "save_management_report",
    "list_management_reports",
    "get_management_report",
    "update_management_report",
    "delete_management_report",
    # Project Detection
    "detect_project_for_activity",
    "redetect_project_assignments",
]
