"""GitHub API client wrapper for Pull Request operations."""

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
