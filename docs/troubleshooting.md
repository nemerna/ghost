# Troubleshooting

Common issues and their resolutions.

## Connection Issues

| Issue | Resolution |
|-------|------------|
| Connection refused | Confirm server is running and endpoint is reachable. Check `podman-compose ps` for container status. |
| SSL errors | Set `X-Jira-Verify-SSL: false` in client headers for self-signed certificates. |
| Timeout errors | Increase client timeout settings. Check network connectivity to Jira/GitHub. |

## Authentication Issues

| Issue | Resolution |
|-------|------------|
| Auth failures (Jira) | Verify PAT is valid and not expired. Ensure you have access to the projects you're querying. |
| Auth failures (GitHub) | Check PAT has required scopes (`repo`, `read:org`). Verify token hasn't been revoked. |
| Missing headers | Ensure client sends required headers for the endpoint. `X-Username` is required for `/mcp/reports`. |
| OAuth errors | Check OpenShift service account has correct redirect URI annotation. |

## MCP Tool Issues

| Issue | Resolution |
|-------|------------|
| Tools not loading | Restart Cursor after updating `.cursor/mcp.json`. Check server logs for errors. |
| Tool returns error | Check the error message for missing required parameters. Verify headers are configured. |
| Reports not saving | Verify `X-Username` header is set on the `/mcp/reports` endpoint. |

## Database Issues

| Issue | Resolution |
|-------|------------|
| Database errors | Check `GHOST_DATA_DIR` is writable (SQLite) or `DATABASE_URL` is correct (PostgreSQL). |
| Migration errors | Delete the SQLite file and restart to recreate. For PostgreSQL, check connection string. |
| Data not persisting | Ensure volume is mounted correctly in Podman. Check PVC status in OpenShift. |

## Frontend Issues

| Issue | Resolution |
|-------|------------|
| Frontend not loading | Verify nginx config. Check `BACKEND_URL` and `MCP_URL` environment variables. |
| API errors in browser | Check browser console for CORS errors. Verify `CORS_ORIGINS` environment variable. |
| Authentication loop | Clear browser cookies. Check OAuth proxy configuration. |

## Container Issues

| Issue | Resolution |
|-------|------------|
| Container won't start | Check `podman-compose logs <service>` for error messages. |
| Port already in use | Stop conflicting services or change ports in `podman-compose.yaml`. |
| Build failures | Ensure Podman has enough resources. Try `podman system prune` to free space. |

## Debugging Tips

### Check Server Logs

```bash
# Podman Compose
podman-compose logs -f backend
podman-compose logs -f mcp

# Local development
# Logs appear in terminal where server is running
```

### Test Endpoints Directly

```bash
# Health check
curl http://localhost:8080/api/health
curl http://localhost:8080/health

# Test with headers
curl -H "X-Jira-Server-URL: https://jira.example.com" \
     -H "X-Jira-Token: your-token" \
     http://localhost:8080/mcp/jira
```

### Verify MCP Configuration

1. Check `.cursor/mcp.json` syntax is valid JSON
2. Verify URLs are correct (include `/mcp/jira`, not just `/mcp`)
3. Restart Cursor after any configuration changes

### Database Inspection

```bash
# SQLite
sqlite3 data/ghost.db ".tables"
sqlite3 data/ghost.db "SELECT * FROM users;"

# PostgreSQL
psql $DATABASE_URL -c "\dt"
psql $DATABASE_URL -c "SELECT * FROM users;"
```

## Getting Help

If you're still experiencing issues:

1. Check server logs for detailed error messages
2. Verify all configuration values are correct
3. Try the minimal setup (Podman Compose with defaults)
4. Open an issue with:
   - Error messages from logs
   - Configuration (redact tokens)
   - Steps to reproduce

## See Also

- [Configuration](configuration.md) - All configuration options
- [Getting Started](getting-started.md) - Initial setup guide
- [Deployment](deployment.md) - Deployment-specific issues
