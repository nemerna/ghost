# Jira MCP Server Container
# Based on Red Hat Universal Base Image 9 with Python 3.11

FROM registry.access.redhat.com/ubi9/python-311:latest

# Labels for container metadata
LABEL name="jira-mcp" \
      version="0.2.0" \
      summary="MCP Server for Jira ticket management with activity tracking" \
      description="Model Context Protocol server providing Jira integration and weekly report generation" \
      maintainer="Your Name <your.email@example.com>"

# Set working directory
WORKDIR /app

# Copy requirements first for better layer caching
COPY requirements.txt .

# Install dependencies
# Using --no-cache-dir to reduce image size
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/

# Create data directory for SQLite database (with proper permissions)
USER 0
RUN mkdir -p /app/data && chown -R 1001:0 /app/data && chmod -R g=u /app/data
USER 1001

# Set Python path to include src directory
ENV PYTHONPATH=/app/src

# Environment variables for configuration (override at runtime)
ENV JIRA_SERVER_URL="" \
    JIRA_PERSONAL_ACCESS_TOKEN="" \
    JIRA_VERIFY_SSL="true" \
    # Database configuration
    DATABASE_URL="" \
    JIRA_MCP_DATA_DIR="/app/data"

# Expose the MCP server port
EXPOSE 8080

# Volume for persistent data (SQLite database)
VOLUME ["/app/data"]

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

# Run as non-root user (ubi9/python-311 runs as user 1001 by default)
USER 1001

# Command to run the server with SSE transport for HTTP access
CMD ["python", "-m", "jira_mcp.server", "--transport", "sse", "--host", "0.0.0.0", "--port", "8080"]
