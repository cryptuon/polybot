# Architecture

## Overview

PolyBot is built as a multi-service architecture using NNG (nanomsg-next-gen) for high-performance internal communication and FastAPI for external API access.

## System Components

### Services

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend (Vue.js)                        │
│                    http://localhost:5173                         │
└─────────────────────────────────────────────────────────────────┘
                                │
                                │ HTTP/WebSocket
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      API Service (FastAPI)                       │
│                    http://localhost:8000                         │
│              NNG PUB: ipc:///tmp/polybot/api.pub                │
│              NNG SUB: ipc:///tmp/polybot/events.pub             │
└─────────────────────────────────────────────────────────────────┘
            │                    │                    │
            │ NNG REQ/REP        │ NNG PUB/SUB       │
            ▼                    ▼                    ▼
┌───────────────────┐  ┌───────────────────┐  ┌───────────────────┐
│   Scanner Service │  │  Executor Service │  │  Analytics Service│
│                   │  │                   │  │                   │
│ - Market polling  │  │ - Order execution │  │ - DuckDB queries  │
│ - Price tracking  │  │ - Position mgmt   │  │ - Performance     │
│ - WebSocket feed  │  │ - Risk checks     │  │ - Reporting       │
└───────────────────┘  └───────────────────┘  └───────────────────┘
            │                    │                    │
            │ NNG PUB/SUB        │ NNG PUB/SUB       │
            ▼                    ▼                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Strategy Services (multiple)                 │
│                                                                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ │
│  │ Arbitrage│ │ Stat Arb │ │ AI Model │ │  Spread  │ │  Copy  │ │
│  │ Service  │ │ Service  │ │ Service  │ │  Farm    │ │ Trade  │ │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Service Descriptions

| Service | Responsibility |
|---------|---------------|
| **Scanner** | Polls Polymarket APIs for market data, maintains price snapshots, bridges WebSocket feeds |
| **Executor** | Handles order creation, signing, submission, position tracking, and risk management |
| **Analytics** | Computes performance metrics, correlations, and maintains DuckDB analytics data |
| **API** | REST/WebSocket gateway for frontend, bridges NNG messages to WebSocket clients |
| **Strategies** | Independent strategy implementations that generate trading signals |

## NNG Communication

### Patterns

| Pattern | Address | Purpose |
|---------|---------|---------|
| PUB/SUB | `ipc:///tmp/polybot/prices.pub` | Price updates from scanner to strategies |
| PUB/SUB | `ipc:///tmp/polybot/events.pub` | System events (orders, trades, alerts) |
| REQ/REP | `ipc:///tmp/polybot/executor.req` | Order submission requests |
| PUSH/PULL | `ipc:///tmp/polybot/signals.push` | Strategy signals to executor |

### Message Format

All messages are msgpack-serialized Python dictionaries:

```python
# Price Update
{
    "type": "price_update",
    "market_id": "0x...",
    "token_id": "12345",
    "bid": 0.45,
    "ask": 0.46,
    "mid": 0.455,
    "timestamp": 1703001234567
}

# Trading Signal
{
    "type": "signal",
    "strategy": "arbitrage",
    "market_id": "0x...",
    "action": "BUY",
    "token_id": "12345",
    "price": 0.45,
    "size": 100.0,
    "reason": "Arbitrage opportunity detected"
}

# System Event
{
    "type": "event",
    "source": "executor",
    "event_type": "order_filled",
    "data": {"order_id": "...", "fill_price": 0.45},
    "timestamp": 1703001234567
}
```

## Data Flow

### Market Data Flow

```
Polymarket APIs → Scanner Service → NNG PUB → Strategy Services
                      │                           │
                      ▼                           ▼
                  DuckDB                     Trading Signals
               (price_history)                    │
                                                  ▼
                                          Executor Service
                                                  │
                                                  ▼
                                           Polymarket CLOB
```

### Order Flow

```
Strategy → Signal → Executor → Risk Check → Order Creation → CLOB API
                                   │              │
                                   ▼              ▼
                              Reject         SQLite (orders)
                                                  │
                                                  ▼
                                          Order Status Updates
                                                  │
                                                  ▼
                                        NNG PUB (events)
```

## Database Schema

### SQLite (Operational Data)

- **markets**: Market definitions and metadata
- **orders**: Order records with status tracking
- **positions**: Open and closed positions
- **trades**: Executed trade records
- **strategy_configs**: Per-strategy configuration
- **wallets**: Tracked whale wallets

### DuckDB (Analytics)

- **price_history**: Time-series price data
- **trade_history**: Historical trade records for analysis
- **strategy_stats**: Daily strategy performance
- **market_correlations**: Computed correlation matrix

## Authentication

### L1 Authentication (Wallet)

Used for:
- API key derivation/creation
- Order signing (EIP-712)

```python
from polybot.core.auth import L1Auth

auth = L1Auth(private_key)
signature = auth.sign_order(order_data)
```

### L2 Authentication (API)

Used for:
- All CLOB API requests
- Order submission
- Position queries

```python
from polybot.core.auth import L2Auth

auth = L2Auth(api_key, secret, passphrase)
headers = auth.get_headers(method, path, body)
```

## Rate Limiting

The `RateLimiter` class implements token bucket rate limiting:

```python
from polybot.core.rate_limiter import RateLimiter

limiter = RateLimiter()

# Acquire permission before making request
await limiter.acquire("clob_order_post")
response = await client.post("/order", ...)
```

### Limits (per 10 seconds)

| Endpoint Type | Limit |
|--------------|-------|
| CLOB General | 9,000 |
| CLOB Book/Price | 1,500 |
| CLOB Order POST | 3,500 |
| CLOB Order DELETE | 3,000 |
| Gamma General | 4,000 |
| Gamma Events | 300 |
| Data API | 1,000 |
| Data Trades | 200 |

## Error Handling

### Retry Strategy

- Exponential backoff for transient errors
- Circuit breaker for persistent failures
- Dead letter queue for unprocessable signals

### Graceful Shutdown

Services handle SIGTERM/SIGINT:

1. Stop accepting new signals
2. Complete in-flight operations
3. Close NNG sockets
4. Persist state to database
5. Exit cleanly
