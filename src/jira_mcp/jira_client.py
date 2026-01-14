"""Jira API client wrapper with Personal Access Token authentication."""

import os
from functools import lru_cache
from typing import Any, Optional

from jira import JIRA
from jira.exceptions import JIRAError


class JiraClientError(Exception):
    """Custom exception for Jira client errors."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class JiraClient:
    """Wrapper around the Jira Python library with PAT authentication."""

    def __init__(
        self,
        server_url: str,
        token: str,
        verify_ssl: bool = True,
    ) -> None:
        """
        Initialize the Jira client with explicit configuration.
        
        Args:
            server_url: Base URL of the Jira server (e.g., https://jira.example.com)
            token: Personal Access Token for authentication
            verify_ssl: Whether to verify SSL certificates (default: True)
        """
        # Ensure server URL doesn't have trailing slash
        self._server_url = server_url.rstrip("/")
        self._jira = JIRA(
            server=self._server_url,
            token_auth=token,
            options={"verify": verify_ssl},
        )

    @property
    def server_url(self) -> str:
        """Get the Jira server URL."""
        return self._server_url

    def build_jql(
        self,
        assignee: Optional[str] = None,
        project: Optional[str] = None,
        component: Optional[str] = None,
        epic_key: Optional[str] = None,
        status: Optional[str] = None,
        issue_type: Optional[str] = None,
    ) -> str:
        """Build a JQL query string from filter parameters."""
        conditions: list[str] = []

        if assignee:
            if assignee.lower() == "currentuser":
                conditions.append("assignee = currentUser()")
            else:
                conditions.append(f'assignee = "{assignee}"')

        if project:
            conditions.append(f'project = "{project}"')

        if component:
            conditions.append(f'component = "{component}"')

        if epic_key:
            # "Epic Link" is the standard field for Jira Server/Data Center
            # For newer versions, "parent" might be used
            conditions.append(f'"Epic Link" = "{epic_key}" OR parent = "{epic_key}"')

        if status:
            conditions.append(f'status = "{status}"')

        if issue_type:
            conditions.append(f'issuetype = "{issue_type}"')

        if conditions:
            return " AND ".join(conditions) + " ORDER BY updated DESC"
        return "ORDER BY updated DESC"

    def search_issues(
        self,
        jql: str,
        max_results: int = 50,
        fields: Optional[list[str]] = None,
    ) -> list[dict[str, Any]]:
        """Search for issues using JQL."""
        try:
            default_fields = [
                "key",
                "summary",
                "status",
                "assignee",
                "priority",
                "issuetype",
                "created",
                "updated",
            ]
            issues = self._jira.search_issues(
                jql,
                maxResults=max_results,
                fields=fields or default_fields,
            )

            results: list[dict[str, Any]] = []
            for issue in issues:
                results.append(self._format_issue_summary(issue))

            return results
        except JIRAError as e:
            raise JiraClientError(
                f"Failed to search issues: {e.text}",
                status_code=e.status_code,
            ) from e

    def get_issue(self, issue_key: str) -> dict[str, Any]:
        """Get full details of a specific issue."""
        try:
            issue = self._jira.issue(issue_key)
            return self._format_issue_full(issue)
        except JIRAError as e:
            raise JiraClientError(
                f"Failed to get issue {issue_key}: {e.text}",
                status_code=e.status_code,
            ) from e

    def create_issue(
        self,
        project: str,
        summary: str,
        description: Optional[str] = None,
        issue_type: str = "Task",
        assignee: Optional[str] = None,
        components: Optional[list[str]] = None,
        epic_key: Optional[str] = None,
        priority: Optional[str] = None,
        labels: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Create a new Jira issue."""
        try:
            fields: dict[str, Any] = {
                "project": {"key": project},
                "summary": summary,
                "issuetype": {"name": issue_type},
            }

            if description:
                fields["description"] = description

            if assignee:
                fields["assignee"] = {"name": assignee}

            if components:
                fields["components"] = [{"name": c} for c in components]

            if priority:
                fields["priority"] = {"name": priority}

            if labels:
                fields["labels"] = labels

            issue = self._jira.create_issue(fields=fields)

            # Link to epic if provided
            if epic_key:
                try:
                    self._jira.add_issues_to_epic(epic_key, [issue.key])
                except JIRAError:
                    # Try alternative method for older Jira versions
                    try:
                        issue.update(fields={"customfield_10014": epic_key})
                    except JIRAError:
                        pass  # Epic link failed, but issue was created

            return {
                "key": issue.key,
                "id": issue.id,
                "url": f"{self._server_url}/browse/{issue.key}",
                "summary": summary,
            }
        except JIRAError as e:
            raise JiraClientError(
                f"Failed to create issue: {e.text}",
                status_code=e.status_code,
            ) from e

    def update_issue(
        self,
        issue_key: str,
        summary: Optional[str] = None,
        description: Optional[str] = None,
        assignee: Optional[str] = None,
        status: Optional[str] = None,
        components: Optional[list[str]] = None,
        priority: Optional[str] = None,
    ) -> dict[str, Any]:
        """Update an existing Jira issue."""
        try:
            issue = self._jira.issue(issue_key)
            fields: dict[str, Any] = {}

            if summary is not None:
                fields["summary"] = summary

            if description is not None:
                fields["description"] = description

            if assignee is not None:
                fields["assignee"] = {"name": assignee} if assignee else None

            if components is not None:
                fields["components"] = [{"name": c} for c in components]

            if priority is not None:
                fields["priority"] = {"name": priority}

            if fields:
                issue.update(fields=fields)

            # Handle status transition separately
            if status:
                self._transition_issue(issue, status)

            return {
                "key": issue_key,
                "updated": True,
                "url": f"{self._server_url}/browse/{issue_key}",
            }
        except JIRAError as e:
            raise JiraClientError(
                f"Failed to update issue {issue_key}: {e.text}",
                status_code=e.status_code,
            ) from e

    def _transition_issue(self, issue: Any, target_status: str) -> None:
        """Transition an issue to a target status."""
        transitions = self._jira.transitions(issue)
        for transition in transitions:
            if transition["to"]["name"].lower() == target_status.lower():
                self._jira.transition_issue(issue, transition["id"])
                return

        available = [t["to"]["name"] for t in transitions]
        raise JiraClientError(
            f"Cannot transition to '{target_status}'. Available transitions: {available}"
        )

    def add_comment(self, issue_key: str, body: str) -> dict[str, Any]:
        """Add a comment to an issue."""
        try:
            comment = self._jira.add_comment(issue_key, body)
            return {
                "id": comment.id,
                "issue_key": issue_key,
                "body": body,
                "author": str(comment.author),
                "created": str(comment.created),
            }
        except JIRAError as e:
            raise JiraClientError(
                f"Failed to add comment to {issue_key}: {e.text}",
                status_code=e.status_code,
            ) from e

    def get_comments(
        self,
        issue_key: str,
        max_results: int = 20,
    ) -> list[dict[str, Any]]:
        """Get comments for an issue."""
        try:
            comments = self._jira.comments(issue_key)
            results: list[dict[str, Any]] = []

            for comment in comments[:max_results]:
                results.append({
                    "id": comment.id,
                    "author": str(comment.author),
                    "body": comment.body,
                    "created": str(comment.created),
                    "updated": str(getattr(comment, "updated", comment.created)),
                })

            return results
        except JIRAError as e:
            raise JiraClientError(
                f"Failed to get comments for {issue_key}: {e.text}",
                status_code=e.status_code,
            ) from e

    def update_comment(
        self,
        issue_key: str,
        comment_id: str,
        body: str,
    ) -> dict[str, Any]:
        """
        Update an existing comment on an issue.
        
        Note: Only comments authored by the current user can be updated.
        
        Args:
            issue_key: The issue key (e.g., 'PROJ-123').
            comment_id: The comment ID to update.
            body: New comment body (supports Jira wiki markup).
            
        Returns:
            Updated comment details.
        """
        try:
            comment = self._jira.comment(issue_key, comment_id)
            comment.update(body=body)
            return {
                "id": comment.id,
                "issue_key": issue_key,
                "body": body,
                "author": str(comment.author),
                "updated": True,
            }
        except JIRAError as e:
            error_msg = e.text
            if e.status_code == 403:
                error_msg = f"Permission denied. You can only edit comments you authored. {e.text}"
            raise JiraClientError(
                f"Failed to update comment {comment_id} on {issue_key}: {error_msg}",
                status_code=e.status_code,
            ) from e

    def delete_comment(
        self,
        issue_key: str,
        comment_id: str,
    ) -> dict[str, Any]:
        """
        Delete a comment from an issue.
        
        Note: Only comments authored by the current user can be deleted.
        
        Args:
            issue_key: The issue key (e.g., 'PROJ-123').
            comment_id: The comment ID to delete.
            
        Returns:
            Confirmation of deletion.
        """
        try:
            comment = self._jira.comment(issue_key, comment_id)
            comment.delete()
            return {
                "deleted": True,
                "issue_key": issue_key,
                "comment_id": comment_id,
                "message": f"Successfully deleted comment {comment_id} from {issue_key}",
            }
        except JIRAError as e:
            error_msg = e.text
            if e.status_code == 403:
                error_msg = f"Permission denied. You can only delete comments you authored. {e.text}"
            raise JiraClientError(
                f"Failed to delete comment {comment_id} on {issue_key}: {error_msg}",
                status_code=e.status_code,
            ) from e

    # --- Discovery/Metadata Methods ---

    def get_projects(self) -> list[dict[str, Any]]:
        """Get all accessible projects."""
        try:
            projects = self._jira.projects()
            results: list[dict[str, Any]] = []

            for project in projects:
                results.append({
                    "key": project.key,
                    "name": project.name,
                    "lead": str(getattr(project, "lead", None)) if hasattr(project, "lead") else None,
                    "url": f"{self._server_url}/browse/{project.key}",
                })

            return results
        except JIRAError as e:
            raise JiraClientError(
                f"Failed to get projects: {e.text}",
                status_code=e.status_code,
            ) from e

    def get_components(self, project: str) -> list[dict[str, Any]]:
        """Get components for a project."""
        try:
            components = self._jira.project_components(project)
            results: list[dict[str, Any]] = []

            for component in components:
                results.append({
                    "id": component.id,
                    "name": component.name,
                    "description": getattr(component, "description", None),
                    "lead": str(getattr(component, "lead", None)) if hasattr(component, "lead") and component.lead else None,
                })

            return results
        except JIRAError as e:
            raise JiraClientError(
                f"Failed to get components for project {project}: {e.text}",
                status_code=e.status_code,
            ) from e

    def get_issue_types(self, project: str) -> list[dict[str, Any]]:
        """Get issue types available for a project."""
        try:
            project_obj = self._jira.project(project)
            issue_types = project_obj.issueTypes
            results: list[dict[str, Any]] = []

            for issue_type in issue_types:
                results.append({
                    "id": issue_type.id,
                    "name": issue_type.name,
                    "description": getattr(issue_type, "description", None),
                    "subtask": getattr(issue_type, "subtask", False),
                })

            return results
        except JIRAError as e:
            raise JiraClientError(
                f"Failed to get issue types for project {project}: {e.text}",
                status_code=e.status_code,
            ) from e

    def get_priorities(self) -> list[dict[str, Any]]:
        """Get all available priorities."""
        try:
            priorities = self._jira.priorities()
            results: list[dict[str, Any]] = []

            for priority in priorities:
                results.append({
                    "id": priority.id,
                    "name": priority.name,
                    "description": getattr(priority, "description", None),
                    "icon_url": getattr(priority, "iconUrl", None),
                })

            return results
        except JIRAError as e:
            raise JiraClientError(
                f"Failed to get priorities: {e.text}",
                status_code=e.status_code,
            ) from e

    def get_statuses(self, project: str) -> list[dict[str, Any]]:
        """Get statuses available for a project."""
        try:
            statuses = self._jira.project(project).statuses
            results: list[dict[str, Any]] = []
            seen_ids: set[str] = set()

            # Statuses are grouped by issue type, so we flatten and deduplicate
            for issue_type_statuses in statuses:
                for status in issue_type_statuses.statuses:
                    if status.id not in seen_ids:
                        seen_ids.add(status.id)
                        results.append({
                            "id": status.id,
                            "name": status.name,
                            "description": getattr(status, "description", None),
                            "category": getattr(status.statusCategory, "name", None) if hasattr(status, "statusCategory") else None,
                        })

            return results
        except JIRAError as e:
            raise JiraClientError(
                f"Failed to get statuses for project {project}: {e.text}",
                status_code=e.status_code,
            ) from e

    def get_transitions(self, issue_key: str) -> list[dict[str, Any]]:
        """Get available transitions for an issue."""
        try:
            transitions = self._jira.transitions(issue_key)
            results: list[dict[str, Any]] = []

            for transition in transitions:
                results.append({
                    "id": transition["id"],
                    "name": transition["name"],
                    "to_status": transition["to"]["name"],
                    "to_status_id": transition["to"]["id"],
                })

            return results
        except JIRAError as e:
            raise JiraClientError(
                f"Failed to get transitions for {issue_key}: {e.text}",
                status_code=e.status_code,
            ) from e

    def get_current_user(self) -> dict[str, Any]:
        """Get information about the currently authenticated user."""
        try:
            user = self._jira.myself()
            return {
                "username": user.get("name", user.get("accountId")),
                "display_name": user.get("displayName"),
                "email": user.get("emailAddress"),
                "active": user.get("active", True),
                "timezone": user.get("timeZone"),
            }
        except JIRAError as e:
            raise JiraClientError(
                f"Failed to get current user: {e.text}",
                status_code=e.status_code,
            ) from e

    # --- Issue Linking & Hierarchy Methods ---

    def link_issues(
        self,
        from_key: str,
        to_key: str,
        link_type: str = "relates to",
    ) -> dict[str, Any]:
        """
        Create a link between two issues.

        Args:
            from_key: The source issue key (e.g., 'PROJ-123').
            to_key: The target issue key (e.g., 'PROJ-456').
            link_type: The type of link (e.g., 'relates to', 'blocks', 'is blocked by',
                      'is part of', 'duplicates').

        Returns:
            Confirmation with link details.
        """
        try:
            self._jira.create_issue_link(
                type=link_type,
                inwardIssue=from_key,
                outwardIssue=to_key,
            )
            return {
                "success": True,
                "from_key": from_key,
                "to_key": to_key,
                "link_type": link_type,
                "message": f"Successfully linked {from_key} to {to_key} with '{link_type}'",
            }
        except JIRAError as e:
            raise JiraClientError(
                f"Failed to link issues {from_key} -> {to_key}: {e.text}",
                status_code=e.status_code,
            ) from e

    def create_subtask(
        self,
        parent_key: str,
        summary: str,
        description: Optional[str] = None,
        assignee: Optional[str] = None,
        priority: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Create a sub-task under a parent issue.

        Args:
            parent_key: The parent issue key (e.g., 'PROJ-123').
            summary: Sub-task title/summary.
            description: Sub-task description (supports Jira wiki markup).
            assignee: Assignee username.
            priority: Priority name (e.g., 'High', 'Medium', 'Low').

        Returns:
            Created sub-task key, id, URL, and summary.
        """
        try:
            # Get the parent issue to determine project
            parent = self._jira.issue(parent_key)
            project_key = parent.fields.project.key

            # Get subtask type for this project
            subtask_type_name, _ = self._get_subtask_type(project_key)

            fields: dict[str, Any] = {
                "project": {"key": project_key},
                "parent": {"key": parent_key},
                "summary": summary,
                "issuetype": {"name": subtask_type_name},
            }

            if description:
                fields["description"] = description

            if assignee:
                fields["assignee"] = {"name": assignee}

            if priority:
                fields["priority"] = {"name": priority}

            issue = self._jira.create_issue(fields=fields)

            return {
                "key": issue.key,
                "id": issue.id,
                "url": f"{self._server_url}/browse/{issue.key}",
                "summary": summary,
                "parent_key": parent_key,
            }
        except JIRAError as e:
            raise JiraClientError(
                f"Failed to create sub-task under {parent_key}: {e.text}",
                status_code=e.status_code,
            ) from e

    def _get_subtask_type(self, project_key: str) -> tuple[str, str]:
        """Get the subtask issue type name and ID for a project."""
        try:
            project = self._jira.project(project_key)
            for issue_type in project.issueTypes:
                if getattr(issue_type, "subtask", False):
                    return issue_type.name, issue_type.id
            # Default fallback
            return "Sub-task", ""
        except JIRAError:
            return "Sub-task", ""

    def set_epic(
        self,
        issue_key: str,
        epic_key: str,
    ) -> dict[str, Any]:
        """
        Set the epic for an issue.

        Args:
            issue_key: The issue key to update (e.g., 'PROJ-123').
            epic_key: The epic issue key to set as parent (e.g., 'PROJ-100').

        Returns:
            Confirmation with updated issue details.
        """
        try:
            # Try the newer method first (Jira Server 8.x+, Jira Cloud)
            try:
                self._jira.add_issues_to_epic(epic_key, [issue_key])
                return {
                    "success": True,
                    "issue_key": issue_key,
                    "epic_key": epic_key,
                    "message": f"Successfully set epic {epic_key} for {issue_key}",
                    "url": f"{self._server_url}/browse/{issue_key}",
                }
            except JIRAError:
                pass

            # Try updating Epic Link custom field (common field IDs)
            issue = self._jira.issue(issue_key)
            epic_link_fields = ["customfield_10014", "customfield_10008", "customfield_10000"]
            
            for field_name in epic_link_fields:
                try:
                    issue.update(fields={field_name: epic_key})
                    return {
                        "success": True,
                        "issue_key": issue_key,
                        "epic_key": epic_key,
                        "message": f"Successfully set epic {epic_key} for {issue_key}",
                        "url": f"{self._server_url}/browse/{issue_key}",
                    }
                except JIRAError:
                    continue

            raise JiraClientError(
                f"Could not set epic for {issue_key}. Epic Link field not found or not editable."
            )
        except JIRAError as e:
            raise JiraClientError(
                f"Failed to set epic {epic_key} for {issue_key}: {e.text}",
                status_code=e.status_code,
            ) from e

    # --- Formatting Methods ---

    def _format_issue_summary(self, issue: Any) -> dict[str, Any]:
        """Format an issue for summary display."""
        fields = issue.fields
        return {
            "key": issue.key,
            "summary": fields.summary,
            "status": str(fields.status),
            "assignee": str(fields.assignee) if fields.assignee else None,
            "priority": str(fields.priority) if fields.priority else None,
            "issue_type": str(fields.issuetype),
            "created": str(fields.created),
            "updated": str(fields.updated),
        }

    def _format_issue_full(self, issue: Any) -> dict[str, Any]:
        """Format an issue with full details."""
        fields = issue.fields
        result = self._format_issue_summary(issue)

        # Add additional fields for full view
        result.update({
            "id": issue.id,
            "url": f"{self._server_url}/browse/{issue.key}",
            "description": fields.description,
            "reporter": str(fields.reporter) if fields.reporter else None,
            "components": [str(c) for c in (fields.components or [])],
            "labels": fields.labels or [],
            "comments_count": (
                len(fields.comment.comments) if hasattr(fields, "comment") else 0
            ),
        })

        # Try to get epic link (field name varies by Jira version)
        epic_link = None
        for field_name in ["parent", "customfield_10014", "customfield_10008"]:
            epic_value = getattr(fields, field_name, None)
            if epic_value:
                epic_link = str(epic_value)
                break
        result["epic_key"] = epic_link

        return result


@lru_cache
def get_jira_client() -> JiraClient:
    """
    Get a cached Jira client instance from environment variables.
    
    This is a convenience function for standalone usage.
    For MCP server usage, the client is managed per-connection.
    
    Environment Variables:
        JIRA_SERVER_URL: Jira server URL (required)
        JIRA_PERSONAL_ACCESS_TOKEN: Personal Access Token (required)
        JIRA_VERIFY_SSL: Verify SSL certificates (default: true)
    """
    server_url = os.environ.get("JIRA_SERVER_URL")
    token = os.environ.get("JIRA_PERSONAL_ACCESS_TOKEN")
    verify_ssl = os.environ.get("JIRA_VERIFY_SSL", "true").lower() in ("true", "1", "yes")
    
    if not server_url:
        raise ValueError("JIRA_SERVER_URL environment variable is required")
    if not token:
        raise ValueError("JIRA_PERSONAL_ACCESS_TOKEN environment variable is required")
    
    return JiraClient(
        server_url=server_url,
        token=token,
        verify_ssl=verify_ssl,
    )
