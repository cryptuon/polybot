# API Reference

PolyBot provides a REST API and WebSocket interface for integration.

## Base URL

```
http://localhost:8000
```

## Authentication

When `AUTH_ENABLED=true`, requests require authentication:

### JWT Token

```bash
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/positions
```

### API Key

```bash
curl -H "X-API-Key: <api_key>" \
  http://localhost:8000/api/positions
```

## Endpoints

### Markets

#### List Markets

```http
GET /api/markets
```

Query parameters:
- `limit` (int): Max results (default: 100)
- `active` (bool): Filter active only

Response:
```json
{
  "markets": [
    {
      "id": "0x...",
      "question": "Will X happen?",
      "yes_price": 0.45,
      "no_price": 0.55,
      "volume_24h": 10000,
      "liquidity": 50000,
      "end_date": "2026-12-31T00:00:00Z"
    }
  ]
}
```

#### Get Market

```http
GET /api/markets/{market_id}
```

### Strategies

#### List Strategies

```http
GET /api/strategies
```

Response:
```json
{
  "strategies": [
    {
      "name": "arbitrage",
      "description": "YES+NO arbitrage",
      "enabled": true,
      "shadow": false,
      "stats": {
        "scans": 1000,
        "signals": 5,
        "positions": 2
      }
    }
  ]
}
```

#### Toggle Strategy

```http
POST /api/strategies/{name}/toggle
```

Body:
```json
{
  "enabled": true,
  "shadow": false
}
```

### Orders

#### List Orders

```http
GET /api/orders
```

Query parameters:
- `status`: Filter by status (open, filled, cancelled)
- `strategy`: Filter by strategy
- `limit`: Max results

#### Create Order

```http
POST /api/orders
```

Body:
```json
{
  "market_id": "0x...",
  "token_id": "12345",
  "side": "BUY",
  "size": 100,
  "price": 0.45
}
```

#### Cancel Order

```http
DELETE /api/orders/{order_id}
```

### Positions

#### List Positions

```http
GET /api/positions
```

Query parameters:
- `strategy`: Filter by strategy
- `status`: open or closed

Response:
```json
{
  "positions": [
    {
      "id": 1,
      "market_id": "0x...",
      "strategy": "arbitrage",
      "side": "YES",
      "size": 100,
      "entry_price": 0.45,
      "current_price": 0.50,
      "unrealized_pnl": 5.0,
      "created_at": "2026-01-01T00:00:00Z"
    }
  ]
}
```

### Analytics

#### Performance Summary

```http
GET /api/analytics/summary
```

Query parameters:
- `days`: Lookback period (default: 30)

Response:
```json
{
  "total_trades": 100,
  "win_rate": 0.65,
  "total_pnl": 500.0,
  "total_volume": 10000.0,
  "total_fees": 50.0,
  "by_strategy": {
    "arbitrage": {"trades": 50, "pnl": 300}
  }
}
```

### Strategy Logs

#### List Logs

```http
GET /api/strategy-logs
```

Query parameters:
- `strategy`: Filter by strategy
- `log_type`: signal, scan, error
- `limit`: Max results
- `offset`: Pagination offset

### Settings

#### Get Settings

```http
GET /api/settings
```

#### Update Settings

```http
PUT /api/settings
```

Body:
```json
{
  "max_position_size_usd": 1000,
  "daily_loss_limit_usd": 500
}
```

### Health

#### Liveness

```http
GET /health/live
```

#### Readiness

```http
GET /health/ready
```

### Metrics

```http
GET /metrics
```

Returns Prometheus-format metrics.

## WebSocket

### Connect

```javascript
const ws = new WebSocket('ws://localhost:8000/ws');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(data);
};
```

### Message Types

#### Price Update

```json
{
  "type": "price",
  "market_id": "0x...",
  "token_id": "12345",
  "bid": 0.45,
  "ask": 0.46,
  "mid": 0.455,
  "timestamp": 1703001234567
}
```

#### Signal

```json
{
  "type": "signal",
  "strategy": "arbitrage",
  "market_id": "0x...",
  "action": "BUY_YES",
  "price": 0.45,
  "size": 100
}
```

#### Order Update

```json
{
  "type": "order_update",
  "order_id": "123",
  "status": "filled",
  "fill_price": 0.45
}
```

## Error Responses

```json
{
  "detail": "Error message",
  "code": "ERROR_CODE"
}
```

Common codes:
- `VALIDATION_ERROR`: Invalid request
- `NOT_FOUND`: Resource not found
- `UNAUTHORIZED`: Authentication required
- `RATE_LIMITED`: Too many requests

## OpenAPI Docs

Interactive API documentation:

```
http://localhost:8000/docs
```

ReDoc format:

```
http://localhost:8000/redoc
```
