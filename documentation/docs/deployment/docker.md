# Docker Deployment

Deploy PolyBot using Docker and Docker Compose.

## Quick Start

```bash
# Clone repository
git clone https://github.com/cryptuon/polybot
cd polybot

# Configure
cp .env.example .env
# Edit .env with your credentials

# Start
docker compose up -d
```

## Services

The default `docker-compose.yml` includes:

| Service | Port | Description |
|---------|------|-------------|
| `polybot` | 8000 | Main application |

Optional monitoring (use `--profile monitoring`):

| Service | Port | Description |
|---------|------|-------------|
| `prometheus` | 9090 | Metrics collection |
| `grafana` | 3000 | Dashboards |

## Configuration

### Environment Variables

Create `.env` in the project root:

```bash
# Required
POLYMARKET_PRIVATE_KEY=your_key
POLYMARKET_PROXY_ADDRESS=0x...

# Optional
LOG_LEVEL=INFO
API_HOST=0.0.0.0
```

### Volumes

Data is persisted in Docker volumes:

```yaml
volumes:
  polybot-data:    # SQLite, DuckDB databases
  polybot-logs:    # Application logs
```

## Commands

### Start Services

```bash
# Start main service
docker compose up -d

# Start with monitoring
docker compose --profile monitoring up -d

# View logs
docker compose logs -f polybot
```

### Stop Services

```bash
docker compose down

# Remove volumes (deletes data!)
docker compose down -v
```

### Update

```bash
docker compose pull
docker compose up -d
```

### Execute Commands

```bash
# Run CLI commands
docker compose exec polybot polybot strategy list

# Initialize databases
docker compose exec polybot polybot db init
```

## Production Configuration

### docker-compose.prod.yml

```yaml
version: '3.8'

services:
  polybot:
    image: ghcr.io/cryptuon/polybot:latest
    restart: always
    ports:
      - "127.0.0.1:8000:8000"
    volumes:
      - polybot-data:/app/data
      - polybot-logs:/app/logs
    env_file:
      - .env.prod
    environment:
      - LOG_LEVEL=INFO
      - LOG_FORMAT=json
      - AUTH_ENABLED=true
    deploy:
      resources:
        limits:
          memory: 2G
        reservations:
          memory: 512M
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health/live"]
      interval: 30s
      timeout: 10s
      retries: 3
```

### Reverse Proxy (nginx)

```nginx
server {
    listen 443 ssl;
    server_name polybot.example.com;

    ssl_certificate /etc/ssl/certs/polybot.crt;
    ssl_certificate_key /etc/ssl/private/polybot.key;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /ws {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

## Building the Image

### Local Build

```bash
docker build -t polybot:local .
```

### Multi-Platform

```bash
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t polybot:latest \
  --push .
```

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker compose logs polybot

# Verify configuration
docker compose config
```

### Database Issues

```bash
# Reset databases
docker compose exec polybot rm -rf /app/data/*
docker compose exec polybot polybot db init
```

### Permission Errors

```bash
# Fix volume permissions
docker compose exec polybot chown -R polybot:polybot /app/data
```

### Memory Issues

Increase memory limits:

```yaml
deploy:
  resources:
    limits:
      memory: 4G
```
