# Deployment

This guide covers deployment options for Ghost, from local Podman Compose to production OpenShift.

## Podman Compose

### Quick Start

```bash
git clone <repository-url>
cd ghost
podman-compose up -d
```

Access the web UI at `http://localhost:8080`

### Database Options

```bash
# SQLite mode (default) - 3 containers: frontend, backend, mcp
podman-compose up -d

# PostgreSQL mode - adds postgres container
podman-compose --profile postgres up -d
```

### Building Container Images

Build the images locally:

```bash
# Build backend image
podman build -t ghost:backend -f Containerfile.backend .

# Build frontend image
podman build -t ghost:frontend -f Containerfile.frontend .
```

### Environment Configuration

Copy and edit the environment file:

```bash
cp env.example .env
# Edit .env with your settings
```

Key variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | — | PostgreSQL connection (empty for SQLite) |
| `GHOST_DATA_DIR` | `./data` | SQLite storage directory |
| `DEV_MODE` | `false` | Enable development mode |

## OpenShift Deployment

Kubernetes manifests are provided in the `openshift/` directory.

### Apply Manifests

```bash
# Using oc (recommended)
oc apply -k openshift/

# Using kubectl
kubectl apply -k openshift/
```

### Included Resources

| File | Description |
|------|-------------|
| `deployment.yaml` | Pod with oauth-proxy, frontend, backend, mcp containers |
| `service.yaml` | Service definition |
| `route.yaml` | OpenShift route for external access |
| `configmap.yaml` | Configuration settings |
| `secrets.yaml` | Secrets template |
| `pvc.yaml` | Persistent volume claim for database |
| `postgres.yaml` | Optional PostgreSQL deployment |
| `kustomization.yaml` | Kustomize configuration |

### OAuth Configuration

The OpenShift deployment includes an OAuth proxy sidecar for SSO authentication:

1. Create a service account with OAuth redirect annotation
2. Configure the route to use edge TLS termination
3. Set the OAuth proxy to validate tokens against OpenShift

### Persistent Storage

The deployment creates a PVC for database storage. Ensure your cluster has a default storage class or specify one in `pvc.yaml`.

## Production Considerations

### Database

For production, use PostgreSQL instead of SQLite:

```bash
# Set DATABASE_URL environment variable
DATABASE_URL=postgresql://user:password@postgres:5432/ghost
```

### SSL/TLS

- Configure OpenShift routes with edge TLS termination
- Or use a reverse proxy (nginx, HAProxy) with SSL termination

### Scaling

The MCP server and backend are stateless and can be scaled horizontally. Ensure you use PostgreSQL for shared state when running multiple replicas.

### Monitoring

Health check endpoints:

| Endpoint | Service |
|----------|---------|
| `/api/health` | REST API |
| `/health` | MCP Server |

## See Also

- [Getting Started](getting-started.md) - Initial setup
- [Configuration](configuration.md) - Environment variables
- [Architecture](architecture.md) - System design
