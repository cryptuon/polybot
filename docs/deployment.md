# Deployment Guide

This guide covers deploying PolyBot to production environments.

## Prerequisites

- VPS with 2+ CPU cores, 4GB+ RAM
- Python 3.11+
- Node.js 18+ (for frontend build)
- Stable internet connection
- Funded Polymarket wallet

## Quick Deploy

### 1. Server Setup

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y python3.11 python3.11-venv nodejs npm

# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Clone and Configure

```bash
git clone https://github.com/yourusername/polybot.git
cd polybot

# Install dependencies
uv sync --frozen

# Configure environment
cp .env.example .env
nano .env  # Edit with your credentials
```

### 3. Build Frontend

```bash
cd frontend
npm install
npm run build
cd ..
```

### 4. Initialize Database

```bash
uv run polybot db init
```

### 5. Start Services

```bash
# Using systemd (recommended)
sudo cp deploy/polybot.service /etc/systemd/system/
sudo systemctl enable polybot
sudo systemctl start polybot

# Or run directly
uv run polybot start
```

---

## Docker Deployment

### Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install uv
RUN pip install uv

# Copy project files
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY src/ ./src/
COPY frontend/dist/ ./frontend/dist/

# Create data directory
RUN mkdir -p /app/data

ENV PYTHONPATH=/app/src
ENV SQLITE_PATH=/app/data/polybot.db
ENV DUCKDB_PATH=/app/data/analytics.duckdb

EXPOSE 8000

CMD ["uv", "run", "polybot", "start"]
```

### Docker Compose

```yaml
version: '3.8'

services:
  polybot:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - polybot-data:/app/data
    environment:
      - POLYMARKET_PRIVATE_KEY=${POLYMARKET_PRIVATE_KEY}
      - POLYMARKET_PROXY_ADDRESS=${POLYMARKET_PROXY_ADDRESS}
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./deploy/nginx.conf:/etc/nginx/nginx.conf
      - ./frontend/dist:/usr/share/nginx/html
    depends_on:
      - polybot
    restart: unless-stopped

volumes:
  polybot-data:
```

### Build and Run

```bash
docker-compose build
docker-compose up -d
```

---

## Systemd Service

Create `/etc/systemd/system/polybot.service`:

```ini
[Unit]
Description=PolyBot Trading Bot
After=network.target

[Service]
Type=simple
User=polybot
WorkingDirectory=/opt/polybot
ExecStart=/opt/polybot/.venv/bin/python -m polybot start
Restart=always
RestartSec=10
Environment=PYTHONPATH=/opt/polybot/src

[Install]
WantedBy=multi-user.target
```

### Service Management

```bash
# Enable on boot
sudo systemctl enable polybot

# Start/stop/restart
sudo systemctl start polybot
sudo systemctl stop polybot
sudo systemctl restart polybot

# View logs
sudo journalctl -u polybot -f
```

---

## Nginx Configuration

```nginx
upstream polybot_api {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    # Frontend
    location / {
        root /opt/polybot/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    # API
    location /api {
        proxy_pass http://polybot_api;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # WebSocket
    location /ws {
        proxy_pass http://polybot_api;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400;
    }

    # Health check
    location /health {
        proxy_pass http://polybot_api;
    }
}
```

---

## SSL/TLS Setup

Using Let's Encrypt:

```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx

# Get certificate
sudo certbot --nginx -d your-domain.com

# Auto-renewal
sudo systemctl enable certbot.timer
```

---

## Monitoring

### Health Checks

```bash
# API health
curl http://localhost:8000/health

# System status
curl http://localhost:8000/api/settings/system
```

### Log Monitoring

```bash
# Follow logs
tail -f /var/log/polybot/polybot.log

# Or with journalctl
journalctl -u polybot -f
```

### Prometheus Metrics

Add to your Prometheus config:

```yaml
scrape_configs:
  - job_name: 'polybot'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'
```

### Alerting

Example alert rules for Alertmanager:

```yaml
groups:
  - name: polybot
    rules:
      - alert: PolybotDown
        expr: up{job="polybot"} == 0
        for: 1m
        labels:
          severity: critical

      - alert: HighDailyLoss
        expr: polybot_daily_pnl < -400
        for: 5m
        labels:
          severity: warning
```

---

## Backup

### Database Backup

```bash
#!/bin/bash
# backup.sh
DATE=$(date +%Y%m%d)
BACKUP_DIR=/backup/polybot

mkdir -p $BACKUP_DIR
cp /opt/polybot/data/polybot.db $BACKUP_DIR/polybot-$DATE.db
cp /opt/polybot/data/analytics.duckdb $BACKUP_DIR/analytics-$DATE.duckdb

# Keep last 7 days
find $BACKUP_DIR -mtime +7 -delete
```

Add to crontab:
```bash
0 0 * * * /opt/polybot/backup.sh
```

### Configuration Backup

Never store `.env` in version control. Use:
- Encrypted secrets management
- Environment variable injection
- Config management tools (Ansible, etc.)

---

## Security Checklist

- [ ] Private key stored securely (not in code)
- [ ] API behind reverse proxy with SSL
- [ ] Firewall configured (only 80/443 open)
- [ ] Regular security updates
- [ ] Log monitoring enabled
- [ ] Backup strategy in place
- [ ] Rate limiting on public endpoints
- [ ] Authentication for dashboard (if public)

---

## Troubleshooting

### Common Issues

**Service won't start**
```bash
# Check logs
journalctl -u polybot -n 50

# Verify configuration
uv run polybot config
```

**Database locked**
```bash
# Check for zombie processes
ps aux | grep polybot

# Kill stale processes
pkill -f polybot
```

**Rate limit errors**
- Reduce polling intervals
- Check for multiple instances running
- Review rate limit configuration

**WebSocket disconnects**
- Check nginx timeout settings
- Verify proxy headers are set
- Check network stability

### Getting Help

1. Check logs: `journalctl -u polybot -f`
2. Validate config: `uv run polybot config`
3. Check system status: `curl localhost:8000/api/settings/system`
4. Open issue on GitHub with logs
