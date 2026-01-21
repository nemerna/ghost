"""API middleware components."""

from jira_mcp.api.middleware.oauth import OAuthProxyMiddleware

__all__ = ["OAuthProxyMiddleware"]
