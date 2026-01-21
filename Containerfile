# Jira MCP Server Container
# Multi-stage build: Node.js for frontend, Python for backend
# Based on Red Hat Universal Base Image 9

# =============================================================================
# Stage 1: Build Frontend
# =============================================================================
FROM registry.access.redhat.com/ubi9/nodejs-20:latest AS frontend-builder

# Switch to root to create directories with proper permissions
USER 0
RUN mkdir -p /app/ui && chown -R 1001:0 /app/ui
USER 1001

WORKDIR /app/ui

# Copy frontend package files
COPY --chown=1001:0 ui/package.json ui/package-lock.json* ./

# Install dependencies
RUN npm ci --prefer-offline --no-audit

# Copy frontend source
COPY --chown=1001:0 ui/ ./

# Build frontend
RUN npm run build

# =============================================================================
# Stage 2: Python Backend with Frontend Static Files
# =============================================================================
FROM registry.access.redhat.com/ubi9/python-311:latest

# Labels for container metadata
LABEL name="jira-mcp" \
      version="1.0.0" \
      summary="MCP Server and Web UI for Jira activity tracking and reporting" \
      description="Model Context Protocol server with REST API and PatternFly React UI for Jira integration, activity tracking, and weekly report generation" \
      maintainer="Your Name <your.email@example.com>"

# Set working directory
WORKDIR /app

# Copy requirements first for better layer caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/

# Copy built frontend from previous stage
COPY --from=frontend-builder /app/ui/dist ./ui/dist

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
    JIRA_MCP_DATA_DIR="/app/data" \
    # UI configuration
    STATIC_DIR="/app/ui/dist" \
    DEV_MODE="false" \
    CORS_ORIGINS="*"

# Expose the server port
EXPOSE 8080

# Volume for persistent data (SQLite database)
VOLUME ["/app/data"]

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/api/health')" || exit 1

# Run as non-root user (ubi9/python-311 runs as user 1001 by default)
USER 1001

# Command to run the REST API server (serves both API and static frontend)
CMD ["python", "-m", "uvicorn", "jira_mcp.api.main:app", "--host", "0.0.0.0", "--port", "8080"]
