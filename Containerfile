# Jira MCP Server Container
# Based on Red Hat Universal Base Image 9 with Python 3.11

FROM registry.access.redhat.com/ubi9/python-311:latest

# Labels for container metadata
LABEL name="jira-mcp" \
      version="0.1.0" \
      summary="MCP Server for Jira ticket management" \
      description="Model Context Protocol server providing Jira integration capabilities" \
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

# Set Python path to include src directory
ENV PYTHONPATH=/app/src

# Environment variables for configuration (override at runtime)
ENV JIRA_SERVER_URL="" \
    JIRA_PERSONAL_ACCESS_TOKEN="" \
    JIRA_VERIFY_SSL="true" \
    MCP_SERVER_HOST="0.0.0.0" \
    MCP_SERVER_PORT="8080"

# Expose the MCP server port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

# Run as non-root user (ubi9/python-311 runs as user 1001 by default)
USER 1001

# Command to run the server
CMD ["python", "-m", "jira_mcp.server"]

