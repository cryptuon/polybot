# Deployment

Deploy PolyBot in production environments.

## Deployment Options

### Docker (Recommended)

The simplest production deployment:

```bash
docker compose up -d
```

[Docker deployment guide](docker.md)

### Manual

For custom setups:

```bash
pip install polybot-trader
polybot start
```

## Production Checklist

- [ ] Enable authentication (`AUTH_ENABLED=true`)
- [ ] Set secure JWT secret
- [ ] Configure risk limits
- [ ] Set up monitoring
- [ ] Configure backups
- [ ] Review security settings

## Monitoring

PolyBot exposes Prometheus metrics at `/metrics`:

- Request latency
- Order counts
- Position values
- Strategy performance

[Monitoring guide](monitoring.md)

## Security

Production security considerations:

- API authentication
- Network isolation
- Secret management
- Audit logging

[Security guide](security.md)
