# Security

Security best practices for deploying PolyBot.

## Authentication

### Enable API Authentication

For production, always enable authentication:

```bash
AUTH_ENABLED=true
AUTH_JWT_SECRET=your-secure-random-secret-at-least-32-chars
AUTH_JWT_EXPIRE_MINUTES=60
```

Generate a secure secret:
```bash
openssl rand -hex 32
```

### API Keys

Generate API keys for programmatic access:

```python
from polybot.api.auth import generate_api_key

key, hash = generate_api_key()
print(f"Key (share with client): {key}")
print(f"Hash (add to AUTH_API_KEYS_HASH): {hash}")
```

Add hashes to config:
```bash
AUTH_API_KEYS_HASH=hash1,hash2,hash3
```

## Credential Management

### Never Commit Credentials

- Use `.env` files (gitignored)
- Use environment variables
- Use secrets management (Docker secrets, Vault)

### Docker Secrets

```yaml
# docker-compose.yml
services:
  polybot:
    secrets:
      - polymarket_key
      - jwt_secret
    environment:
      - POLYMARKET_PRIVATE_KEY_FILE=/run/secrets/polymarket_key

secrets:
  polymarket_key:
    file: ./secrets/polymarket_key.txt
  jwt_secret:
    file: ./secrets/jwt_secret.txt
```

### Hardware Wallets

For maximum security, consider:
- Using a hardware wallet for signing
- Implementing a separate signing service
- Using multi-signature wallets

## Network Security

### Bind to Localhost

By default, bind only to localhost:

```bash
API_HOST=127.0.0.1
```

### Use a Reverse Proxy

Put nginx/Caddy in front:

```nginx
server {
    listen 443 ssl;
    
    # TLS configuration
    ssl_certificate /etc/ssl/cert.pem;
    ssl_certificate_key /etc/ssl/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    
    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Firewall Rules

```bash
# Only allow SSH and HTTPS
ufw default deny incoming
ufw allow ssh
ufw allow 443/tcp
ufw enable
```

## Rate Limiting

### Application Level

PolyBot includes built-in rate limiting:

```python
app.add_middleware(
    RateLimitMiddleware,
    requests_per_minute=120,
    burst_size=20
)
```

### Nginx Level

```nginx
limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;

location /api/ {
    limit_req zone=api burst=20 nodelay;
    proxy_pass http://127.0.0.1:8000;
}
```

## CORS Configuration

Restrict allowed origins:

```bash
CORS_ALLOWED_ORIGINS=https://your-domain.com
CORS_ALLOW_CREDENTIALS=true
```

## Security Headers

PolyBot adds security headers automatically:

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Strict-Transport-Security` (when behind HTTPS proxy)

## Audit Logging

Enable detailed logging for security events:

```bash
LOG_LEVEL=INFO
LOG_FORMAT=json
```

Monitor for:
- Failed authentication attempts
- Unusual order patterns
- API errors

## Container Security

### Run as Non-Root

The Dockerfile already runs as non-root:

```dockerfile
RUN useradd --create-home polybot
USER polybot
```

### Read-Only Filesystem

```yaml
services:
  polybot:
    read_only: true
    tmpfs:
      - /tmp
    volumes:
      - polybot-data:/app/data
```

### Security Scanning

Scan images for vulnerabilities:

```bash
docker scout cve polybot:latest
```

## Backup Security

### Encrypt Backups

```bash
# Backup with encryption
tar -czf - ./data | gpg -c > backup.tar.gz.gpg

# Restore
gpg -d backup.tar.gz.gpg | tar -xzf -
```

### Secure Storage

- Store backups in encrypted storage
- Use separate credentials for backup access
- Test restore procedures regularly

## Incident Response

### Emergency Procedures

1. **Stop trading immediately**:
   ```bash
   docker compose exec polybot polybot strategy disable --all
   ```

2. **Preserve evidence**:
   ```bash
   docker compose logs polybot > incident.log
   ```

3. **Rotate credentials** if compromised

4. **Review audit logs**

### Security Checklist

- [ ] Authentication enabled
- [ ] Strong JWT secret
- [ ] HTTPS configured
- [ ] Firewall rules in place
- [ ] Credentials not in code
- [ ] Regular backups
- [ ] Monitoring active
- [ ] Incident response plan
