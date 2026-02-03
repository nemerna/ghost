# Development

This guide covers local development setup, testing, and project structure.

## Prerequisites

- Python 3.11+
- Node.js 22+ (for frontend)
- Docker (optional, for containerized development)

## Local Development Setup

### Backend

```bash
# Clone and setup
git clone <repository-url>
cd ghost

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies (with dev extras)
pip install -e ".[dev]"
```

### Running the Backend

```bash
# MCP server only (for AI tool integration)
python -m ghost.server --host 0.0.0.0 --port 8001

# REST API backend (for web UI)
DEV_MODE=true uvicorn ghost.api.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend

```bash
cd ui
npm install
npm run dev
```

The frontend dev server runs on `http://localhost:5173` with hot reload.

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=ghost

# Run specific test file
pytest tests/test_jira_client.py
```

## Code Quality

```bash
# Format code
black src/ tests/

# Lint
ruff check src/ tests/

# Type checking
mypy src/

# Frontend linting
cd ui
npm run lint
```

## Project Structure

```
ghost/
├── src/ghost/
│   ├── server.py              # MCP SSE server with /mcp/jira, /mcp/github, /mcp/reports
│   ├── jira_client.py         # Jira API wrapper
│   ├── github_client.py       # GitHub API wrapper (PRs and Issues)
│   ├── config.py              # Configuration helpers
│   ├── api/                   # REST API for web UI
│   │   ├── main.py            # FastAPI application
│   │   ├── deps.py            # Dependencies
│   │   ├── middleware/
│   │   │   └── oauth.py       # OAuth proxy middleware
│   │   └── routes/
│   │       ├── health.py      # Health check
│   │       ├── users.py       # User management
│   │       ├── teams.py       # Team management
│   │       ├── activities.py  # Activity tracking
│   │       └── reports.py     # Report management
│   ├── db/
│   │   ├── database.py        # Database connection
│   │   └── models.py          # SQLAlchemy models
│   └── tools/
│       ├── tickets.py         # Jira ticket tools
│       ├── comments.py        # Jira comment tools
│       ├── discovery.py       # Jira metadata tools
│       ├── reports.py         # Activity and report tools
│       └── schemas.py         # Pydantic schemas
├── ui/                        # PatternFly React frontend
│   ├── src/
│   │   ├── App.tsx            # Main application with routing
│   │   ├── api/               # API client
│   │   ├── auth/              # Authentication context
│   │   ├── components/        # Reusable components
│   │   ├── pages/             # Page components
│   │   └── types/             # TypeScript types
│   ├── package.json
│   └── vite.config.ts
├── openshift/                 # Kubernetes/OpenShift manifests
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── route.yaml
│   ├── configmap.yaml
│   ├── secrets.yaml
│   ├── pvc.yaml
│   └── kustomization.yaml
├── tests/
├── Containerfile.backend      # Backend container (Python/FastAPI)
├── Containerfile.frontend     # Frontend container (Nginx/React)
├── nginx.conf.template        # Nginx configuration template
├── docker-compose.yaml        # Multi-container orchestration
├── env.example                # Environment variables template
├── pyproject.toml
├── requirements.txt
└── README.md
```

## Key Components

### MCP Server (`server.py`)

The SSE server exposes three MCP endpoints:
- `/mcp/jira` - Jira tools
- `/mcp/github` - GitHub tools
- `/mcp/reports` - Activity and report tools

### REST API (`api/`)

FastAPI application serving the web UI:
- User and team management
- Activity CRUD operations
- Report storage and retrieval

### Database (`db/`)

SQLAlchemy models and database connection:
- Supports SQLite (development) and PostgreSQL (production)
- Automatic migrations on startup

### Frontend (`ui/`)

React application with PatternFly components:
- Vite for fast development builds
- TypeScript for type safety
- API client with automatic authentication

## Building Containers

```bash
# Build backend
docker build -t ghost:backend -f Containerfile.backend .

# Build frontend
docker build -t ghost:frontend -f Containerfile.frontend .

# Run with docker-compose
docker-compose up -d
```

## See Also

- [Architecture](architecture.md) - System design overview
- [Configuration](configuration.md) - Environment variables
- [Deployment](deployment.md) - Production deployment
