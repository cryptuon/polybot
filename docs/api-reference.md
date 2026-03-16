# API Reference

PolyBot exposes a REST API and WebSocket endpoint for the frontend dashboard and external integrations.

## Base URL

```
http://localhost:8000
```

## Authentication

The internal API does not require authentication by default. For production deployments, configure API key authentication in settings.

---

## REST Endpoints

### Markets

#### List Markets
```http
GET /api/markets
```

Query Parameters:
| Parameter | Type | Description |
|-----------|------|-------------|
| `active` | boolean | Filter by active status |
| `limit` | integer | Maximum results (default: 100) |
| `offset` | integer | Pagination offset |
| `search` | string | Search by question text |

Response:
```json
{
  "markets": [
    {
      "id": "0x123...",
      "condition_id": "0xabc...",
      "question": "Will Bitcoin reach $100k by 2024?",
      "slug": "bitcoin-100k-2024",
      "outcome_yes_token": "12345",
      "outcome_no_token": "12346",
      "end_date": "2024-12-31T23:59:59Z",
      "active": true,
      "yes_price": 0.45,
      "no_price": 0.55
    }
  ],
  "total": 150,
  "limit": 100,
  "offset": 0
}
```

#### Get Market
```http
GET /api/markets/{market_id}
```

#### Get Orderbook
```http
GET /api/markets/{market_id}/orderbook
```

Response:
```json
{
  "market_id": "0x123...",
  "bids": [
    {"price": 0.44, "size": 500.0},
    {"price": 0.43, "size": 1200.0}
  ],
  "asks": [
    {"price": 0.46, "size": 300.0},
    {"price": 0.47, "size": 800.0}
  ],
  "timestamp": "2024-01-15T10:30:00Z"
}
```

---

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
      "description": "YES+NO arbitrage when sum < $1",
      "enabled": true,
      "config": {
        "min_profit_pct": 0.01,
        "poll_interval_sec": 2
      },
      "stats": {
        "trades": 42,
        "win_rate": 0.95,
        "pnl": 156.78
      }
    }
  ]
}
```

#### Get Strategy
```http
GET /api/strategies/{name}
```

#### Update Strategy
```http
PUT /api/strategies/{name}
```

Request:
```json
{
  "enabled": true,
  "config": {
    "min_profit_pct": 0.02
  }
}
```

#### Toggle Strategy
```http
POST /api/strategies/{name}/toggle
```

Response:
```json
{
  "name": "arbitrage",
  "enabled": false,
  "message": "Strategy disabled"
}
```

---

### Orders

#### List Orders
```http
GET /api/orders
```

Query Parameters:
| Parameter | Type | Description |
|-----------|------|-------------|
| `status` | string | Filter by status (PENDING, OPEN, FILLED, CANCELLED) |
| `strategy` | string | Filter by strategy name |
| `market_id` | string | Filter by market |
| `limit` | integer | Maximum results |

Response:
```json
{
  "orders": [
    {
      "id": "order-123",
      "market_id": "0x123...",
      "strategy": "arbitrage",
      "side": "BUY",
      "token_id": "12345",
      "price": 0.45,
      "size": 100.0,
      "status": "FILLED",
      "order_hash": "0xdef...",
      "created_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-01-15T10:30:05Z"
    }
  ],
  "total": 50
}
```

#### Create Order
```http
POST /api/orders
```

Request:
```json
{
  "market_id": "0x123...",
  "token_id": "12345",
  "side": "BUY",
  "price": 0.45,
  "size": 100.0
}
```

#### Cancel Order
```http
DELETE /api/orders/{order_id}
```

---

### Positions

#### List Positions
```http
GET /api/positions
```

Query Parameters:
| Parameter | Type | Description |
|-----------|------|-------------|
| `open` | boolean | Filter open/closed positions |
| `strategy` | string | Filter by strategy |

Response:
```json
{
  "positions": [
    {
      "id": 1,
      "market_id": "0x123...",
      "token_id": "12345",
      "side": "YES",
      "entry_price": 0.45,
      "size": 100.0,
      "strategy": "arbitrage",
      "opened_at": "2024-01-15T10:30:00Z",
      "closed_at": null,
      "current_price": 0.48,
      "unrealized_pnl": 3.0
    }
  ]
}
```

#### Close Position
```http
POST /api/positions/{position_id}/close
```

---

### Analytics

#### Performance Summary
```http
GET /api/analytics/summary
```

Query Parameters:
| Parameter | Type | Description |
|-----------|------|-------------|
| `strategy` | string | Filter by strategy |
| `days` | integer | Lookback period (default: 30) |

Response:
```json
{
  "total_trades": 150,
  "total_wins": 120,
  "total_losses": 30,
  "win_rate": 0.8,
  "total_pnl": 1234.56,
  "total_volume": 15000.0,
  "total_fees": 45.0,
  "avg_daily_pnl": 41.15,
  "best_day": 250.0,
  "worst_day": -80.0
}
```

#### Analytics History
```http
GET /api/analytics/history
```

Response:
```json
{
  "days": [
    {
      "date": "2024-01-15",
      "strategy": "arbitrage",
      "trades": 5,
      "wins": 4,
      "losses": 1,
      "pnl": 45.67,
      "volume": 500.0,
      "fees": 1.5
    }
  ],
  "summary": { ... }
}
```

#### Price History
```http
GET /api/analytics/prices/{market_id}
```

Query Parameters:
| Parameter | Type | Description |
|-----------|------|-------------|
| `interval` | string | Candle interval (1m, 5m, 15m, 1h, 4h, 1d) |
| `limit` | integer | Number of candles |

#### Strategy Analytics
```http
GET /api/analytics/strategies
```

#### Market Correlations
```http
GET /api/analytics/correlations/{market_id}
```

---

### Settings

#### Get Settings
```http
GET /api/settings
```

Response:
```json
{
  "risk": {
    "max_position_size_usd": 1000,
    "max_total_exposure_usd": 10000,
    "daily_loss_limit_usd": 500,
    "max_open_orders": 20
  },
  "strategies": {
    "arbitrage": {
      "enabled": true,
      "config": { ... }
    }
  }
}
```

#### Update Settings
```http
PUT /api/settings
```

#### Risk Status
```http
GET /api/settings/risk
```

Response:
```json
{
  "daily_pnl": 125.50,
  "total_exposure": 2500.0,
  "open_orders": 5,
  "open_positions": 3,
  "risk_limits": {
    "daily_loss_limit": 500,
    "max_exposure": 10000,
    "max_position": 1000,
    "max_orders": 20
  }
}
```

#### System Status
```http
GET /api/settings/system
```

Response:
```json
{
  "services": [
    {"name": "scanner", "status": "running"},
    {"name": "executor", "status": "running"},
    {"name": "analytics", "status": "running"}
  ],
  "healthy": true,
  "uptime_seconds": 3600
}
```

#### Reload Configuration
```http
POST /api/settings/reload
```

---

## WebSocket API

### Connection
```javascript
const ws = new WebSocket('ws://localhost:8000/ws')
```

### Subscribe to Channels
```javascript
ws.send(JSON.stringify({
  type: 'subscribe',
  channels: ['prices', 'events']
}))
```

### Unsubscribe
```javascript
ws.send(JSON.stringify({
  type: 'unsubscribe',
  channels: ['prices']
}))
```

### Ping/Pong
```javascript
ws.send(JSON.stringify({ type: 'ping' }))
// Response: { type: 'pong' }
```

### Message Formats

#### Price Update
```json
{
  "channel": "prices",
  "data": {
    "market_id": "0x123...",
    "bid": 0.45,
    "ask": 0.46,
    "mid": 0.455,
    "timestamp": 1705312200000
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

#### Event
```json
{
  "channel": "events",
  "data": {
    "source": "executor",
    "event_type": "order_filled",
    "data": {
      "order_id": "order-123",
      "fill_price": 0.45,
      "fill_size": 100.0
    },
    "timestamp": 1705312200000
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

---

## Error Responses

All endpoints return errors in this format:

```json
{
  "detail": "Error message here"
}
```

### HTTP Status Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 201 | Created |
| 400 | Bad Request |
| 404 | Not Found |
| 422 | Validation Error |
| 500 | Internal Server Error |
| 503 | Service Unavailable |

---

## Rate Limiting

The internal API does not enforce rate limits. However, external Polymarket API calls are rate-limited. Monitor the `/api/settings/system` endpoint for rate limit status.
