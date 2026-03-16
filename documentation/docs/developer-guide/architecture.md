# Architecture

PolyBot uses a multi-service architecture with NNG (nanomsg-next-gen) for high-performance internal communication.

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend (Vue.js)                        │
│                    http://localhost:5173 (dev)                   │
│                    http://localhost:8000/ui (prod)               │
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
│ - WebSocket feed  │  │ - Risk checks     │  │ - Correlations    │
└───────────────────┘  └───────────────────┘  └───────────────────┘
            │                    │                    │
            │ NNG PUB/SUB        │ NNG PUSH/PULL     │
            ▼                    ▼                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Strategy Services (multiple)                 │
│                                                                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐           │
│  │ Arbitrage│ │ Stat Arb │ │ AI Model │ │ Spread   │  ...      │
│  │ Strategy │ │ Strategy │ │ Strategy │ │ Farm     │           │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘           │
└─────────────────────────────────────────────────────────────────┘
```

## Services

### Scanner Service

**Responsibility**: Fetch and distribute market data.

- Polls Polymarket APIs for market information
- Maintains price snapshots in DuckDB
- Publishes price updates via NNG PUB/SUB
- Bridges WebSocket feeds for real-time data

### Executor Service

**Responsibility**: Execute trades and manage positions.

- Receives signals from strategies via NNG PUSH/PULL
- Performs risk checks before execution
- Submits orders to venue APIs
- Tracks order status and fills
- Manages position lifecycle

### Analytics Service

**Responsibility**: Performance tracking and analysis.

- Computes market correlations
- Calculates performance metrics
- Maintains historical data in DuckDB
- Provides analytics API

### API Service

**Responsibility**: External interface for dashboard and clients.

- REST API for CRUD operations
- WebSocket for real-time updates
- Bridges NNG messages to WebSocket clients
- Serves bundled Vue.js dashboard

### Strategy Services

**Responsibility**: Generate trading signals.

- Subscribe to price updates
- Implement trading logic
- Generate signals when opportunities found
- Track strategy-specific state

## Communication

### NNG Patterns

| Pattern | Address | Purpose |
|---------|---------|---------|
| PUB/SUB | `ipc:///tmp/polybot/prices.pub` | Price updates |
| PUB/SUB | `ipc:///tmp/polybot/events.pub` | System events |
| REQ/REP | `ipc:///tmp/polybot/state.req` | State queries |
| PUSH/PULL | `ipc:///tmp/polybot/signals.push` | Trading signals |

### Message Format

All messages are msgpack-serialized Python dictionaries:

```python
# Price Update
{
    "type": "price",
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
    "action": "BUY_YES",
    "token_id": "12345",
    "price": 0.45,
    "size": 100.0,
    "reason": "Arbitrage opportunity",
    "confidence": 0.95
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
Polymarket APIs → Scanner → NNG PUB → Strategies
                    │                      │
                    ▼                      ▼
                 DuckDB              Trading Signals
              (price_history)              │
                                          ▼
                                    Executor → Polymarket
```

### Order Flow

```
Strategy → Signal → Executor → Risk Check → Order → CLOB API
                                   │           │
                                   ▼           ▼
                               Reject      SQLite
                                          (orders)
                                              │
                                              ▼
                                      Status Updates
                                              │
                                              ▼
                                    NNG PUB (events)
```

## Databases

### SQLite (Operational)

Path: `./data/polybot.db`

Tables:
- `markets` - Market definitions
- `orders` - Order records
- `positions` - Position tracking
- `trades` - Executed trades
- `strategy_configs` - Strategy settings
- `wallets` - Tracked whale wallets

### DuckDB (Analytics)

Path: `./data/analytics.duckdb`

Tables:
- `price_history` - Time-series prices
- `trade_history` - Historical trades
- `strategy_stats` - Performance metrics
- `market_correlations` - Correlation matrix

### Strategy Logs DuckDB

Path: `./data/strategy_logs.duckdb`

Tables:
- `strategy_runs` - Run sessions
- `strategy_logs` - Detailed logs

## Authentication

### L1 (Wallet)

Used for:
- API key derivation
- Order signing (EIP-712)

### L2 (API)

Used for:
- CLOB API requests
- Order submission
- Position queries

## Rate Limiting

PolyBot implements token bucket rate limiting:

| Endpoint | Limit (per 10s) |
|----------|-----------------|
| CLOB General | 9,000 |
| CLOB Orders | 3,500 |
| Gamma API | 4,000 |
| Data API | 1,000 |

## Error Handling

- **Retry**: Exponential backoff for transient errors
- **Circuit breaker**: Stops after repeated failures
- **Dead letter**: Unprocessable signals logged

## Graceful Shutdown

On SIGTERM/SIGINT:

1. Stop accepting new signals
2. Complete in-flight operations
3. Close NNG sockets
4. Persist state
5. Exit cleanly
