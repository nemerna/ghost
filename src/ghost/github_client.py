"""GitHub API client wrapper for Pull Request and Issue operations."""

import json
from fnmatch import fnmatch
from typing import Any

import httpx


class GitHubClientError(Exception):
    """Custom exception for GitHub client errors."""

    def __init__(self, message: str, status_code: int | None = None):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class GitHubClient:
    """GitHub API client for read-only Pull Request operations."""

    def __init__(
        self,
        token: str,
        api_url: str | None = None,
    ) -> None:
        """
        Initialize the GitHub client.

        Args:
            token: Personal Access Token for GitHub API authentication
            api_url: GitHub API base URL (for GitHub Enterprise). Defaults to github.com
        """
        self._token = token
        self._api_url = (api_url or "https://api.github.com").rstrip("/")
        self._headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    @property
    def api_url(self) -> str:
        """Get the GitHub API URL."""
        return self._api_url

    def _request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> Any:
        """Make an HTTP request to the GitHub API."""
        url = f"{self._api_url}{endpoint}"
        request_headers = {**self._headers, **(headers or {})}

        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_body,
                    headers=request_headers,
                )

                if response.status_code == 404:
                    raise GitHubClientError(
                        f"Resource not found: {endpoint}",
                        status_code=404,
                    )
                elif response.status_code == 401:
                    raise GitHubClientError(
                        "Authentication failed. Please check your GitHub token.",
                        status_code=401,
                    )
                elif response.status_code == 403:
                    # Check for rate limiting
                    if "rate limit" in response.text.lower():
                        raise GitHubClientError(
                            "GitHub API rate limit exceeded. Please try again later.",
                            status_code=403,
                        )
                    raise GitHubClientError(
                        f"Access forbidden: {response.text}",
                        status_code=403,
                    )
                elif response.status_code >= 400:
                    raise GitHubClientError(
                        f"GitHub API error: {response.text}",
                        status_code=response.status_code,
                    )

                return response.json()
        except httpx.RequestError as e:
            raise GitHubClientError(f"Request failed: {str(e)}") from e

    def _get(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        """Make a GET request to the GitHub API."""
        return self._request("GET", endpoint, params=params, headers=headers)

    def _post(
        self,
        endpoint: str,
        json_body: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> Any:
        """Make a POST request to the GitHub API."""
        return self._request("POST", endpoint, headers=headers, json_body=json_body)

    def _patch(
        self,
        endpoint: str,
        json_body: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> Any:
        """Make a PATCH request to the GitHub API."""
        return self._request("PATCH", endpoint, headers=headers, json_body=json_body)

    def _put(
        self,
        endpoint: str,
        json_body: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> Any:
        """Make a PUT request to the GitHub API."""
        return self._request("PUT", endpoint, headers=headers, json_body=json_body)

    def _delete(
        self,
        endpoint: str,
        json_body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        """Make a DELETE request to the GitHub API."""
        return self._request("DELETE", endpoint, headers=headers, json_body=json_body)

    # --- Pull Request Methods ---

    def list_pull_requests(
        self,
        owner: str,
        repo: str,
        state: str = "open",
        head: str | None = None,
        base: str | None = None,
        sort: str = "created",
        direction: str = "desc",
        per_page: int = 30,
        page: int = 1,
    ) -> list[dict[str, Any]]:
        """
        List pull requests for a repository.

        Args:
            owner: Repository owner (user or organization)
            repo: Repository name
            state: Filter by state: 'open', 'closed', or 'all'
            head: Filter by head user/org and branch (format: 'user:branch')
            base: Filter by base branch name
            sort: Sort by: 'created', 'updated', 'popularity', 'long-running'
            direction: Sort direction: 'asc' or 'desc'
            per_page: Results per page (max 100)
            page: Page number

        Returns:
            List of pull request summaries
        """
        params: dict[str, Any] = {
            "state": state,
            "sort": sort,
            "direction": direction,
            "per_page": min(per_page, 100),
            "page": page,
        }

        if head:
            params["head"] = head
        if base:
            params["base"] = base

        prs = self._get(f"/repos/{owner}/{repo}/pulls", params=params)
        return [self._format_pr_summary(pr) for pr in prs]

    def get_pull_request(
        self,
        owner: str,
        repo: str,
        pr_number: int,
    ) -> dict[str, Any]:
        """
        Get details of a specific pull request.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number

        Returns:
            Full pull request details
        """
        pr = self._get(f"/repos/{owner}/{repo}/pulls/{pr_number}")
        return self._format_pr_detail(pr)

    def get_pull_request_diff(
        self,
        owner: str,
        repo: str,
        pr_number: int,
    ) -> str:
        """
        Get the diff of a pull request.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number

        Returns:
            Unified diff as string
        """
        url = f"{self._api_url}/repos/{owner}/{repo}/pulls/{pr_number}"
        headers = {
            **self._headers,
            "Accept": "application/vnd.github.v3.diff",
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(url, headers=headers)

                if response.status_code >= 400:
                    raise GitHubClientError(
                        f"Failed to get diff: {response.text}",
                        status_code=response.status_code,
                    )

                return response.text
        except httpx.RequestError as e:
            raise GitHubClientError(f"Request failed: {str(e)}") from e

    def get_pull_request_files(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        per_page: int = 30,
        page: int = 1,
    ) -> list[dict[str, Any]]:
        """
        Get files changed in a pull request.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
            per_page: Results per page (max 100)
            page: Page number

        Returns:
            List of files with change details
        """
        params = {
            "per_page": min(per_page, 100),
            "page": page,
        }

        files = self._get(
            f"/repos/{owner}/{repo}/pulls/{pr_number}/files",
            params=params,
        )

        return [
            {
                "filename": f["filename"],
                "status": f["status"],  # added, removed, modified, renamed, copied, changed
                "additions": f["additions"],
                "deletions": f["deletions"],
                "changes": f["changes"],
                "patch": f.get("patch"),  # May be None for binary files
                "previous_filename": f.get("previous_filename"),  # For renamed files
            }
            for f in files
        ]

    def get_pull_request_commits(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        per_page: int = 30,
        page: int = 1,
    ) -> list[dict[str, Any]]:
        """
        Get commits in a pull request.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
            per_page: Results per page (max 100)
            page: Page number

        Returns:
            List of commits with details
        """
        params = {
            "per_page": min(per_page, 100),
            "page": page,
        }

        commits = self._get(
            f"/repos/{owner}/{repo}/pulls/{pr_number}/commits",
            params=params,
        )

        return [
            {
                "sha": c["sha"],
                "message": c["commit"]["message"],
                "author": c["commit"]["author"]["name"],
                "author_email": c["commit"]["author"]["email"],
                "date": c["commit"]["author"]["date"],
                "committer": c["commit"]["committer"]["name"],
                "url": c["html_url"],
            }
            for c in commits
        ]

    def get_pull_request_reviews(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        per_page: int = 30,
        page: int = 1,
    ) -> list[dict[str, Any]]:
        """
        Get reviews on a pull request.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
            per_page: Results per page (max 100)
            page: Page number

        Returns:
            List of reviews
        """
        params = {
            "per_page": min(per_page, 100),
            "page": page,
        }

        reviews = self._get(
            f"/repos/{owner}/{repo}/pulls/{pr_number}/reviews",
            params=params,
        )

        return [
            {
                "id": r["id"],
                "user": r["user"]["login"] if r["user"] else None,
                "state": r["state"],  # APPROVED, CHANGES_REQUESTED, COMMENTED, DISMISSED, PENDING
                "body": r["body"],
                "submitted_at": r["submitted_at"],
                "commit_id": r["commit_id"],
                "url": r["html_url"],
            }
            for r in reviews
        ]

    def get_pull_request_comments(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        per_page: int = 30,
        page: int = 1,
    ) -> dict[str, list[dict[str, Any]]]:
        """
        Get all comments on a pull request (both issue comments and review comments).

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
            per_page: Results per page (max 100)
            page: Page number

        Returns:
            Dict with 'issue_comments' and 'review_comments' lists
        """
        params = {
            "per_page": min(per_page, 100),
            "page": page,
        }

        # Get issue comments (general PR comments)
        issue_comments = self._get(
            f"/repos/{owner}/{repo}/issues/{pr_number}/comments",
            params=params,
        )

        # Get review comments (inline code comments)
        review_comments = self._get(
            f"/repos/{owner}/{repo}/pulls/{pr_number}/comments",
            params=params,
        )

        return {
            "issue_comments": [
                {
                    "id": c["id"],
                    "user": c["user"]["login"] if c["user"] else None,
                    "body": c["body"],
                    "created_at": c["created_at"],
                    "updated_at": c["updated_at"],
                    "url": c["html_url"],
                }
                for c in issue_comments
            ],
            "review_comments": [
                {
                    "id": c["id"],
                    "user": c["user"]["login"] if c["user"] else None,
                    "body": c["body"],
                    "path": c["path"],
                    "line": c.get("line"),
                    "original_line": c.get("original_line"),
                    "diff_hunk": c["diff_hunk"],
                    "created_at": c["created_at"],
                    "updated_at": c["updated_at"],
                    "url": c["html_url"],
                }
                for c in review_comments
            ],
        }

    def add_pull_request_comment(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        body: str,
    ) -> dict[str, Any]:
        """
        Add a general (issue) comment to a pull request.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
            body: Comment body (Markdown)

        Returns:
            Created comment details
        """
        comment = self._post(
            f"/repos/{owner}/{repo}/issues/{pr_number}/comments",
            json_body={"body": body},
        )

        return {
            "id": comment["id"],
            "user": comment["user"]["login"] if comment["user"] else None,
            "body": comment["body"],
            "created_at": comment["created_at"],
            "updated_at": comment["updated_at"],
            "url": comment["html_url"],
        }

    def reply_pull_request_comment(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        comment_id: int,
        body: str,
    ) -> dict[str, Any]:
        """
        Reply to an existing pull request review comment thread.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
            comment_id: Review comment ID to reply to
            body: Reply body (Markdown)

        Returns:
            Created reply comment details
        """
        comment = self._post(
            f"/repos/{owner}/{repo}/pulls/{pr_number}/comments",
            json_body={"body": body, "in_reply_to": comment_id},
        )

        return {
            "id": comment["id"],
            "user": comment["user"]["login"] if comment["user"] else None,
            "body": comment["body"],
            "created_at": comment["created_at"],
            "updated_at": comment["updated_at"],
            "url": comment["html_url"],
        }

    def create_pull_request_review(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        event: str,
        body: str | None = None,
        comments: list[dict[str, Any]] | None = None,
        commit_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Create a review on a pull request (approve, request changes, or comment).

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
            event: Review action: 'APPROVE', 'REQUEST_CHANGES', or 'COMMENT'
            body: Review body/summary (Markdown). Required for REQUEST_CHANGES.
            comments: Optional list of inline comments to include with the review.
                      Each comment dict should have: path, line, body, and optionally
                      side ('LEFT' or 'RIGHT'), start_line (for multi-line comments).
            commit_id: Optional SHA of the commit to review. Defaults to PR head.

        Returns:
            Created review details
        """
        json_body: dict[str, Any] = {"event": event}

        if body:
            json_body["body"] = body
        if commit_id:
            json_body["commit_id"] = commit_id
        if comments:
            json_body["comments"] = comments

        review = self._post(
            f"/repos/{owner}/{repo}/pulls/{pr_number}/reviews",
            json_body=json_body,
        )

        return {
            "id": review["id"],
            "user": review["user"]["login"] if review["user"] else None,
            "state": review["state"],
            "body": review.get("body"),
            "submitted_at": review.get("submitted_at"),
            "commit_id": review.get("commit_id"),
            "url": review.get("html_url"),
        }

    def add_pull_request_review_comment(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        body: str,
        commit_id: str,
        path: str,
        line: int,
        side: str = "RIGHT",
        start_line: int | None = None,
        start_side: str | None = None,
    ) -> dict[str, Any]:
        """
        Add an inline review comment on a specific file and line in a PR diff.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
            body: Comment body (Markdown)
            commit_id: SHA of the commit to comment on (use PR head SHA)
            path: Relative path to the file being commented on
            line: Line number in the diff to comment on
            side: Which side of the diff: 'LEFT' (deletions) or 'RIGHT' (additions)
            start_line: For multi-line comments, the first line of the range
            start_side: For multi-line comments, the side of the start line

        Returns:
            Created comment details
        """
        json_body: dict[str, Any] = {
            "body": body,
            "commit_id": commit_id,
            "path": path,
            "line": line,
            "side": side,
        }

        if start_line is not None:
            json_body["start_line"] = start_line
            if start_side:
                json_body["start_side"] = start_side

        comment = self._post(
            f"/repos/{owner}/{repo}/pulls/{pr_number}/comments",
            json_body=json_body,
        )

        return {
            "id": comment["id"],
            "user": comment["user"]["login"] if comment["user"] else None,
            "body": comment["body"],
            "path": comment["path"],
            "line": comment.get("line"),
            "side": comment.get("side"),
            "start_line": comment.get("start_line"),
            "diff_hunk": comment.get("diff_hunk"),
            "commit_id": comment.get("commit_id"),
            "created_at": comment["created_at"],
            "updated_at": comment["updated_at"],
            "url": comment["html_url"],
        }

    def request_reviewers(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        reviewers: list[str] | None = None,
        team_reviewers: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Request reviewers for a pull request.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
            reviewers: List of usernames to request as reviewers
            team_reviewers: List of team slugs to request as reviewers

        Returns:
            Updated PR details with requested reviewers
        """
        json_body: dict[str, Any] = {}

        if reviewers:
            json_body["reviewers"] = reviewers
        if team_reviewers:
            json_body["team_reviewers"] = team_reviewers

        result = self._post(
            f"/repos/{owner}/{repo}/pulls/{pr_number}/requested_reviewers",
            json_body=json_body,
        )

        return {
            "pr_number": result["number"],
            "title": result["title"],
            "requested_reviewers": [r["login"] for r in result.get("requested_reviewers", [])],
            "requested_teams": [t["slug"] for t in result.get("requested_teams", [])],
            "url": result["html_url"],
        }

    def remove_requested_reviewers(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        reviewers: list[str] | None = None,
        team_reviewers: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Remove requested reviewers from a pull request.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
            reviewers: List of usernames to remove from reviewers
            team_reviewers: List of team slugs to remove from reviewers

        Returns:
            Updated PR details with remaining requested reviewers
        """
        json_body: dict[str, Any] = {}

        if reviewers:
            json_body["reviewers"] = reviewers
        if team_reviewers:
            json_body["team_reviewers"] = team_reviewers

        result = self._delete(
            f"/repos/{owner}/{repo}/pulls/{pr_number}/requested_reviewers",
            json_body=json_body,
        )

        return {
            "pr_number": result["number"],
            "title": result["title"],
            "requested_reviewers": [r["login"] for r in result.get("requested_reviewers", [])],
            "requested_teams": [t["slug"] for t in result.get("requested_teams", [])],
            "url": result["html_url"],
        }

    def dismiss_pull_request_review(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        review_id: int,
        message: str,
    ) -> dict[str, Any]:
        """
        Dismiss a pull request review.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
            review_id: The review ID to dismiss
            message: Reason for dismissing the review

        Returns:
            Dismissed review details
        """
        review = self._put(
            f"/repos/{owner}/{repo}/pulls/{pr_number}/reviews/{review_id}/dismissals",
            json_body={"message": message},
        )

        return {
            "id": review["id"],
            "user": review["user"]["login"] if review["user"] else None,
            "state": review["state"],
            "body": review.get("body"),
            "dismissed_at": review.get("submitted_at"),
            "dismissal_message": message,
            "url": review.get("html_url"),
        }

    def search_pull_requests(
        self,
        query: str,
        sort: str = "created",
        order: str = "desc",
        per_page: int = 30,
        page: int = 1,
    ) -> dict[str, Any]:
        """
        Search for pull requests across repositories.

        Args:
            query: GitHub search query (e.g., 'is:pr author:username repo:owner/repo')
            sort: Sort by: 'created', 'updated', 'comments'
            order: Sort order: 'asc' or 'desc'
            per_page: Results per page (max 100)
            page: Page number

        Returns:
            Search results with total count and PR list
        """
        # Ensure query includes type:pr
        if "type:pr" not in query and "is:pr" not in query:
            query = f"is:pr {query}"

        params = {
            "q": query,
            "sort": sort,
            "order": order,
            "per_page": min(per_page, 100),
            "page": page,
        }

        result = self._get("/search/issues", params=params)

        return {
            "total_count": result["total_count"],
            "incomplete_results": result["incomplete_results"],
            "pull_requests": [self._format_search_result(item) for item in result["items"]],
        }

    def get_current_user(self) -> dict[str, Any]:
        """Get information about the authenticated user."""
        user = self._get("/user")
        return {
            "login": user["login"],
            "name": user.get("name"),
            "email": user.get("email"),
            "avatar_url": user["avatar_url"],
            "url": user["html_url"],
            "type": user["type"],
        }

    # --- Issue Methods ---

    def list_issues(
        self,
        owner: str,
        repo: str,
        state: str = "open",
        labels: str | None = None,
        assignee: str | None = None,
        creator: str | None = None,
        milestone: str | None = None,
        sort: str = "created",
        direction: str = "desc",
        since: str | None = None,
        per_page: int = 30,
        page: int = 1,
    ) -> list[dict[str, Any]]:
        """
        List issues for a repository.

        Args:
            owner: Repository owner (user or organization)
            repo: Repository name
            state: Filter by state: 'open', 'closed', or 'all'
            labels: Comma-separated list of label names
            assignee: Filter by assignee username. Use '*' for any, 'none' for unassigned
            creator: Filter by creator username
            milestone: Filter by milestone number or '*' for any, 'none' for no milestone
            sort: Sort by: 'created', 'updated', 'comments'
            direction: Sort direction: 'asc' or 'desc'
            since: Only issues updated after this ISO 8601 timestamp
            per_page: Results per page (max 100)
            page: Page number

        Returns:
            List of issue summaries (excludes pull requests)
        """
        params: dict[str, Any] = {
            "state": state,
            "sort": sort,
            "direction": direction,
            "per_page": min(per_page, 100),
            "page": page,
        }

        if labels:
            params["labels"] = labels
        if assignee:
            params["assignee"] = assignee
        if creator:
            params["creator"] = creator
        if milestone:
            params["milestone"] = milestone
        if since:
            params["since"] = since

        issues = self._get(f"/repos/{owner}/{repo}/issues", params=params)

        # Filter out pull requests (they appear in the issues endpoint)
        issues = [i for i in issues if "pull_request" not in i]

        return [self._format_issue_summary(issue, owner, repo) for issue in issues]

    def get_issue(
        self,
        owner: str,
        repo: str,
        issue_number: int,
    ) -> dict[str, Any]:
        """
        Get details of a specific issue.

        Args:
            owner: Repository owner
            repo: Repository name
            issue_number: Issue number

        Returns:
            Full issue details
        """
        issue = self._get(f"/repos/{owner}/{repo}/issues/{issue_number}")
        return self._format_issue_detail(issue, owner, repo)

    def create_issue(
        self,
        owner: str,
        repo: str,
        title: str,
        body: str | None = None,
        assignees: list[str] | None = None,
        labels: list[str] | None = None,
        milestone: int | None = None,
    ) -> dict[str, Any]:
        """
        Create a new issue.

        Args:
            owner: Repository owner
            repo: Repository name
            title: Issue title
            body: Issue body (Markdown)
            assignees: List of usernames to assign
            labels: List of label names
            milestone: Milestone number to associate

        Returns:
            Created issue details
        """
        json_body: dict[str, Any] = {"title": title}

        if body:
            json_body["body"] = body
        if assignees:
            json_body["assignees"] = assignees
        if labels:
            json_body["labels"] = labels
        if milestone is not None:
            json_body["milestone"] = milestone

        issue = self._post(f"/repos/{owner}/{repo}/issues", json_body=json_body)
        return self._format_issue_detail(issue, owner, repo)

    def update_issue(
        self,
        owner: str,
        repo: str,
        issue_number: int,
        title: str | None = None,
        body: str | None = None,
        state: str | None = None,
        assignees: list[str] | None = None,
        labels: list[str] | None = None,
        milestone: int | None = None,
    ) -> dict[str, Any]:
        """
        Update an existing issue.

        Args:
            owner: Repository owner
            repo: Repository name
            issue_number: Issue number
            title: New title
            body: New body (Markdown)
            state: New state: 'open' or 'closed'
            assignees: New list of assignees (replaces existing)
            labels: New list of labels (replaces existing)
            milestone: New milestone number (use 0 or None to clear)

        Returns:
            Updated issue details
        """
        json_body: dict[str, Any] = {}

        if title is not None:
            json_body["title"] = title
        if body is not None:
            json_body["body"] = body
        if state is not None:
            json_body["state"] = state
        if assignees is not None:
            json_body["assignees"] = assignees
        if labels is not None:
            json_body["labels"] = labels
        if milestone is not None:
            json_body["milestone"] = milestone if milestone > 0 else None

        issue = self._patch(f"/repos/{owner}/{repo}/issues/{issue_number}", json_body=json_body)
        return self._format_issue_detail(issue, owner, repo)

    def close_issue(
        self,
        owner: str,
        repo: str,
        issue_number: int,
        state_reason: str | None = None,
    ) -> dict[str, Any]:
        """
        Close an issue.

        Args:
            owner: Repository owner
            repo: Repository name
            issue_number: Issue number
            state_reason: Reason for closing: 'completed' or 'not_planned'

        Returns:
            Updated issue details
        """
        json_body: dict[str, Any] = {"state": "closed"}

        if state_reason:
            json_body["state_reason"] = state_reason

        issue = self._patch(f"/repos/{owner}/{repo}/issues/{issue_number}", json_body=json_body)
        return self._format_issue_detail(issue, owner, repo)

    def reopen_issue(
        self,
        owner: str,
        repo: str,
        issue_number: int,
    ) -> dict[str, Any]:
        """
        Reopen a closed issue.

        Args:
            owner: Repository owner
            repo: Repository name
            issue_number: Issue number

        Returns:
            Updated issue details
        """
        issue = self._patch(
            f"/repos/{owner}/{repo}/issues/{issue_number}",
            json_body={"state": "open"},
        )
        return self._format_issue_detail(issue, owner, repo)

    def get_issue_comments(
        self,
        owner: str,
        repo: str,
        issue_number: int,
        since: str | None = None,
        per_page: int = 30,
        page: int = 1,
    ) -> list[dict[str, Any]]:
        """
        Get comments on an issue.

        Args:
            owner: Repository owner
            repo: Repository name
            issue_number: Issue number
            since: Only comments updated after this ISO 8601 timestamp
            per_page: Results per page (max 100)
            page: Page number

        Returns:
            List of comments
        """
        params: dict[str, Any] = {
            "per_page": min(per_page, 100),
            "page": page,
        }

        if since:
            params["since"] = since

        comments = self._get(
            f"/repos/{owner}/{repo}/issues/{issue_number}/comments",
            params=params,
        )

        return [
            {
                "id": c["id"],
                "user": c["user"]["login"] if c["user"] else None,
                "body": c["body"],
                "created_at": c["created_at"],
                "updated_at": c["updated_at"],
                "url": c["html_url"],
            }
            for c in comments
        ]

    def add_issue_comment(
        self,
        owner: str,
        repo: str,
        issue_number: int,
        body: str,
    ) -> dict[str, Any]:
        """
        Add a comment to an issue.

        Args:
            owner: Repository owner
            repo: Repository name
            issue_number: Issue number
            body: Comment body (Markdown)

        Returns:
            Created comment details
        """
        comment = self._post(
            f"/repos/{owner}/{repo}/issues/{issue_number}/comments",
            json_body={"body": body},
        )

        return {
            "id": comment["id"],
            "user": comment["user"]["login"] if comment["user"] else None,
            "body": comment["body"],
            "created_at": comment["created_at"],
            "updated_at": comment["updated_at"],
            "url": comment["html_url"],
        }

    def search_issues(
        self,
        query: str,
        sort: str = "created",
        order: str = "desc",
        per_page: int = 30,
        page: int = 1,
    ) -> dict[str, Any]:
        """
        Search for issues across repositories.

        Args:
            query: GitHub search query (e.g., 'is:issue author:username repo:owner/repo')
            sort: Sort by: 'created', 'updated', 'comments'
            order: Sort order: 'asc' or 'desc'
            per_page: Results per page (max 100)
            page: Page number

        Returns:
            Search results with total count and issues list
        """
        # Ensure query includes type:issue (exclude PRs)
        if "type:issue" not in query and "is:issue" not in query:
            query = f"is:issue {query}"

        params = {
            "q": query,
            "sort": sort,
            "order": order,
            "per_page": min(per_page, 100),
            "page": page,
        }

        result = self._get("/search/issues", params=params)

        return {
            "total_count": result["total_count"],
            "incomplete_results": result["incomplete_results"],
            "issues": [self._format_issue_search_result(item) for item in result["items"]],
        }

    # --- Formatting Methods ---

    def _format_pr_summary(self, pr: dict[str, Any]) -> dict[str, Any]:
        """Format a PR for summary display."""
        return {
            "number": pr["number"],
            "title": pr["title"],
            "state": pr["state"],
            "draft": pr.get("draft", False),
            "user": pr["user"]["login"] if pr["user"] else None,
            "created_at": pr["created_at"],
            "updated_at": pr["updated_at"],
            "head": {
                "ref": pr["head"]["ref"],
                "sha": pr["head"]["sha"][:7],
            },
            "base": {
                "ref": pr["base"]["ref"],
            },
            "url": pr["html_url"],
        }

    def _format_pr_detail(self, pr: dict[str, Any]) -> dict[str, Any]:
        """Format a PR with full details."""
        result = self._format_pr_summary(pr)
        result.update(
            {
                "id": pr["id"],
                "body": pr["body"],
                "merged": pr.get("merged", False),
                "mergeable": pr.get("mergeable"),
                "mergeable_state": pr.get("mergeable_state"),
                "merged_at": pr.get("merged_at"),
                "merged_by": pr["merged_by"]["login"] if pr.get("merged_by") else None,
                "additions": pr["additions"],
                "deletions": pr["deletions"],
                "changed_files": pr["changed_files"],
                "commits": pr["commits"],
                "comments": pr["comments"],
                "review_comments": pr["review_comments"],
                "labels": [label["name"] for label in pr.get("labels", [])],
                "assignees": [a["login"] for a in pr.get("assignees", [])],
                "requested_reviewers": [r["login"] for r in pr.get("requested_reviewers", [])],
                "milestone": pr["milestone"]["title"] if pr.get("milestone") else None,
                "closed_at": pr.get("closed_at"),
            }
        )
        return result

    def _format_search_result(self, item: dict[str, Any]) -> dict[str, Any]:
        """Format a search result item."""
        # Parse owner/repo from repository_url
        repo_parts = item.get("repository_url", "").split("/")
        owner = repo_parts[-2] if len(repo_parts) >= 2 else None
        repo = repo_parts[-1] if len(repo_parts) >= 1 else None

        return {
            "number": item["number"],
            "title": item["title"],
            "state": item["state"],
            "user": item["user"]["login"] if item["user"] else None,
            "repository": f"{owner}/{repo}" if owner and repo else None,
            "created_at": item["created_at"],
            "updated_at": item["updated_at"],
            "closed_at": item.get("closed_at"),
            "labels": [label["name"] for label in item.get("labels", [])],
            "url": item["html_url"],
        }

    def _format_issue_summary(
        self, issue: dict[str, Any], owner: str, repo: str
    ) -> dict[str, Any]:
        """Format an issue for summary display."""
        return {
            "number": issue["number"],
            "title": issue["title"],
            "state": issue["state"],
            "user": issue["user"]["login"] if issue["user"] else None,
            "assignees": [a["login"] for a in issue.get("assignees", [])],
            "labels": [label["name"] for label in issue.get("labels", [])],
            "comments": issue.get("comments", 0),
            "created_at": issue["created_at"],
            "updated_at": issue["updated_at"],
            "closed_at": issue.get("closed_at"),
            "repository": f"{owner}/{repo}",
            "issue_key": f"{owner}/{repo}#{issue['number']}",
            "url": issue["html_url"],
        }

    def _format_issue_detail(
        self, issue: dict[str, Any], owner: str, repo: str
    ) -> dict[str, Any]:
        """Format an issue with full details."""
        result = self._format_issue_summary(issue, owner, repo)
        result.update(
            {
                "id": issue["id"],
                "body": issue.get("body"),
                "milestone": issue["milestone"]["title"] if issue.get("milestone") else None,
                "milestone_number": (
                    issue["milestone"]["number"] if issue.get("milestone") else None
                ),
                "state_reason": issue.get("state_reason"),
                "locked": issue.get("locked", False),
                "reactions": {
                    "total": issue.get("reactions", {}).get("total_count", 0),
                    "+1": issue.get("reactions", {}).get("+1", 0),
                    "-1": issue.get("reactions", {}).get("-1", 0),
                },
            }
        )
        return result

    def _format_issue_search_result(self, item: dict[str, Any]) -> dict[str, Any]:
        """Format an issue search result item."""
        # Parse owner/repo from repository_url
        repo_parts = item.get("repository_url", "").split("/")
        owner = repo_parts[-2] if len(repo_parts) >= 2 else None
        repo = repo_parts[-1] if len(repo_parts) >= 1 else None

        return {
            "number": item["number"],
            "title": item["title"],
            "state": item["state"],
            "user": item["user"]["login"] if item["user"] else None,
            "repository": f"{owner}/{repo}" if owner and repo else None,
            "issue_key": f"{owner}/{repo}#{item['number']}" if owner and repo else None,
            "assignees": [a["login"] for a in item.get("assignees", [])],
            "labels": [label["name"] for label in item.get("labels", [])],
            "comments": item.get("comments", 0),
            "created_at": item["created_at"],
            "updated_at": item["updated_at"],
            "closed_at": item.get("closed_at"),
            "url": item["html_url"],
        }


class GitHubTokenManager:
    """Manages multiple GitHub PATs with glob-based repo pattern matching.

    Each token entry has a list of glob patterns matched against 'owner/repo'.
    Patterns are evaluated in order; first match wins.

    Example token entries:
        [
            {"token": "ghp_personal", "patterns": ["myuser/*"]},
            {"token": "ghp_org", "patterns": ["my-org/*", "partner-org/shared-repo"]},
            {"token": "ghp_fallback", "patterns": ["*"]}
        ]
    """

    def __init__(
        self,
        entries: list[dict[str, Any]],
        api_url: str | None = None,
    ) -> None:
        """
        Initialize the token manager.

        Args:
            entries: Ordered list of dicts with 'token' and 'patterns' keys.
                     Each entry may also include an optional 'api_url' override.
            api_url: Default GitHub API base URL (for GitHub Enterprise).
                     Individual entries can override this.
        """
        self._entries = entries
        self._default_api_url = api_url
        self._client_cache: dict[str, GitHubClient] = {}

    def _get_or_create_client(self, token: str, api_url: str | None = None) -> GitHubClient:
        """Get a cached GitHubClient or create a new one for the given token."""
        effective_api_url = api_url or self._default_api_url
        cache_key = f"{token}:{effective_api_url or ''}"
        if cache_key not in self._client_cache:
            self._client_cache[cache_key] = GitHubClient(
                token=token,
                api_url=effective_api_url,
            )
        return self._client_cache[cache_key]

    def get_client(self, owner: str, repo: str) -> GitHubClient:
        """Resolve the correct GitHubClient for the given owner/repo.

        Iterates through entries in order and returns the client for the
        first entry whose patterns match 'owner/repo'.

        Args:
            owner: Repository owner (user or organization)
            repo: Repository name

        Returns:
            GitHubClient configured with the matched token

        Raises:
            GitHubClientError: If no token pattern matches the owner/repo
        """
        target = f"{owner}/{repo}"
        for entry in self._entries:
            patterns = entry.get("patterns", [])
            token = entry["token"]
            entry_api_url = entry.get("api_url")
            for pattern in patterns:
                if fnmatch(target, pattern):
                    return self._get_or_create_client(token, entry_api_url)

        raise GitHubClientError(
            f"No GitHub token configured for repository '{target}'. "
            f"Check your X-GitHub-Tokens header patterns.",
            status_code=None,
        )

    def get_default_client(self) -> GitHubClient:
        """Get the default GitHubClient for non-repo-scoped operations.

        Returns the client for the first entry with a '*' (catch-all) pattern,
        or falls back to the first entry in the list.

        Returns:
            GitHubClient for general use

        Raises:
            GitHubClientError: If no tokens are configured
        """
        if not self._entries:
            raise GitHubClientError(
                "No GitHub tokens configured. Set X-GitHub-Token or X-GitHub-Tokens header.",
                status_code=None,
            )

        # Prefer the entry with a catch-all '*' pattern
        for entry in self._entries:
            patterns = entry.get("patterns", [])
            if "*" in patterns or "*/*" in patterns:
                return self._get_or_create_client(entry["token"], entry.get("api_url"))

        # Fall back to the first entry
        first = self._entries[0]
        return self._get_or_create_client(first["token"], first.get("api_url"))

    def get_token_info(self) -> list[dict[str, Any]]:
        """Return token pattern info without exposing full tokens.

        Returns:
            List of dicts with 'patterns' and 'token_hint' (last 4 chars).
        """
        result = []
        for entry in self._entries:
            token = entry["token"]
            # Show only last 4 characters as a hint
            hint = f"...{token[-4:]}" if len(token) > 4 else "****"
            result.append({
                "patterns": entry.get("patterns", []),
                "token_hint": hint,
                "api_url": entry.get("api_url"),
            })
        return result

    @classmethod
    def from_header(cls, tokens_json: str, api_url: str | None = None) -> "GitHubTokenManager":
        """Create a GitHubTokenManager from the X-GitHub-Tokens header value.

        Args:
            tokens_json: JSON string - an array of objects with 'token' and 'patterns' keys.
            api_url: Default GitHub API base URL.

        Returns:
            Configured GitHubTokenManager

        Raises:
            ValueError: If the JSON is malformed or entries are invalid
        """
        try:
            entries = json.loads(tokens_json)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid X-GitHub-Tokens JSON: {e}") from e

        if not isinstance(entries, list):
            raise ValueError("X-GitHub-Tokens must be a JSON array")

        for i, entry in enumerate(entries):
            if not isinstance(entry, dict):
                raise ValueError(f"X-GitHub-Tokens entry {i} must be an object")
            if "token" not in entry:
                raise ValueError(f"X-GitHub-Tokens entry {i} missing 'token' field")
            if "patterns" not in entry or not isinstance(entry["patterns"], list):
                raise ValueError(f"X-GitHub-Tokens entry {i} missing or invalid 'patterns' field")

        return cls(entries=entries, api_url=api_url)

    @classmethod
    def from_single_token(cls, token: str, api_url: str | None = None) -> "GitHubTokenManager":
        """Create a GitHubTokenManager from a single token (backward compatibility).

        The single token matches all repositories (catch-all '*' pattern).

        Args:
            token: GitHub Personal Access Token
            api_url: GitHub API base URL

        Returns:
            Configured GitHubTokenManager with a single catch-all entry
        """
        return cls(
            entries=[{"token": token, "patterns": ["*"]}],
            api_url=api_url,
        )

    @classmethod
    def from_named_headers(
        cls,
        named_tokens: dict[str, str],
        configs: list[dict[str, Any]],
        api_url: str | None = None,
    ) -> "GitHubTokenManager":
        """Create a GitHubTokenManager from named headers and DB-stored configs.

        Matches header names (from X-GitHub-Token-{name}) to DB config names
        and builds entries using the stored patterns.

        Args:
            named_tokens: Dict mapping config name to token value,
                          e.g., {"personal": "ghp_abc", "work": "ghp_xyz"}
            configs: List of dicts from DB with 'name', 'patterns', and
                     optionally 'display_order' keys.
            api_url: Default GitHub API base URL.

        Returns:
            Configured GitHubTokenManager

        Raises:
            ValueError: If no matching configs are found for the provided headers
        """
        # Build a lookup from config name to patterns
        config_lookup = {c["name"]: c["patterns"] for c in configs}

        entries = []
        for name, token in named_tokens.items():
            patterns = config_lookup.get(name)
            if patterns:
                entries.append({"token": token, "patterns": patterns})

        if not entries:
            available = list(config_lookup.keys())
            provided = list(named_tokens.keys())
            raise ValueError(
                f"No matching GitHub token configs found. "
                f"Headers provided tokens for: {provided}. "
                f"DB has configs for: {available}."
            )

        return cls(entries=entries, api_url=api_url)
