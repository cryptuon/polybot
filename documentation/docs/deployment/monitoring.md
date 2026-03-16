# Monitoring

Monitor PolyBot with Prometheus and Grafana.

## Quick Setup

```bash
docker compose --profile monitoring up -d
```

Access:
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000 (admin/polybot123)

## Metrics

PolyBot exposes Prometheus metrics at `/metrics`:

### Request Metrics

```
# HTTP request duration
polybot_http_request_duration_seconds{method, endpoint, status}

# HTTP request count
polybot_http_requests_total{method, endpoint, status}
```

### Trading Metrics

```
# Orders placed
polybot_orders_total{strategy, side, status}

# Position value
polybot_position_value_usd{strategy, market}

# P&L
polybot_pnl_total{strategy}
polybot_pnl_unrealized{strategy}
```

### Strategy Metrics

```
# Signals generated
polybot_signals_total{strategy, action}

# Scans performed
polybot_scans_total{strategy}

# Strategy running status
polybot_strategy_running{strategy}
```

### System Metrics

```
# Active WebSocket connections
polybot_websocket_connections

# NNG message queue depth
polybot_nng_queue_depth{channel}
```

## Prometheus Configuration

`deploy/prometheus/prometheus.yml`:

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'polybot'
    static_configs:
      - targets: ['polybot:8000']
    metrics_path: '/metrics'
    scrape_interval: 10s
```

## Grafana Dashboards

### Import Dashboard

1. Open Grafana (http://localhost:3000)
2. Go to Dashboards → Import
3. Upload `deploy/grafana/dashboards/polybot.json`

### Key Panels

- **P&L Overview**: Total and per-strategy P&L
- **Order Activity**: Orders by status and strategy
- **Position Summary**: Open positions and exposure
- **Signal Rate**: Signals per minute by strategy
- **API Performance**: Request latency and error rates

## Alerting

### Prometheus Alerts

```yaml
# deploy/prometheus/alerts.yml
groups:
  - name: polybot
    rules:
      - alert: HighErrorRate
        expr: rate(polybot_http_requests_total{status="5xx"}[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: High error rate detected

      - alert: DailyLossLimit
        expr: polybot_pnl_total < -500
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: Daily loss limit approaching
```

### Grafana Alerts

Configure alerts in Grafana:
1. Edit panel → Alert tab
2. Set conditions
3. Configure notification channels

## Health Checks

### Endpoints

```bash
# Liveness (is the process running?)
curl http://localhost:8000/health/live

# Readiness (is the service ready for traffic?)
curl http://localhost:8000/health/ready
```

### Docker Health Check

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health/live"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 60s
```

## Logging

### Structured Logging

Set `LOG_FORMAT=json` for structured logs:

```json
{
  "timestamp": "2026-01-01T12:00:00Z",
  "level": "INFO",
  "message": "Order filled",
  "order_id": "123",
  "strategy": "arbitrage",
  "fill_price": 0.45
}
```

### Log Aggregation

For centralized logging, configure:
- Loki (with Grafana)
- Elasticsearch (with Kibana)
- CloudWatch Logs

## Best Practices

1. **Set up alerts** for critical conditions
2. **Monitor P&L** daily
3. **Track error rates** for early warning
4. **Review dashboards** regularly
5. **Keep metrics retention** appropriate (15-30 days)
