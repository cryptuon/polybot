# Configuration

PolyBot is configured primarily through environment variables. Copy `.env.example` to `.env` and modify as needed.

## Environment Variables

### Polymarket Credentials

```env
# Required: Your wallet private key (without 0x prefix)
POLYMARKET_PRIVATE_KEY=

# Required: Your proxy wallet address from polymarket.com
POLYMARKET_PROXY_ADDRESS=

# Optional: API credentials (will be derived if not provided)
POLYMARKET_API_KEY=
POLYMARKET_API_SECRET=
POLYMARKET_API_PASSPHRASE=

# Chain ID (default: 137 for Polygon mainnet)
POLYMARKET_CHAIN_ID=137
```

### API URLs

```env
# Polymarket API endpoints (defaults shown)
CLOB_BASE_URL=https://clob.polymarket.com
GAMMA_BASE_URL=https://gamma-api.polymarket.com
DATA_BASE_URL=https://data-api.polymarket.com
WS_URL=wss://ws-subscriptions-clob.polymarket.com/ws/
```

### Risk Management

```env
# Maximum position size for a single market (USD)
MAX_POSITION_SIZE_USD=1000

# Maximum total exposure across all positions (USD)
MAX_TOTAL_EXPOSURE_USD=10000

# Daily loss limit - stop trading after this loss (USD)
DAILY_LOSS_LIMIT_USD=500

# Maximum number of open orders
MAX_OPEN_ORDERS=20

# Minimum balance to maintain (USD)
MIN_BALANCE_USD=100
```

### Database

```env
# SQLite database path (operational data)
SQLITE_PATH=./data/polybot.db

# DuckDB database path (analytics)
DUCKDB_PATH=./data/analytics.duckdb
```

### API Server

```env
# API server configuration
API_HOST=127.0.0.1
API_PORT=8000
API_RELOAD=false
```

### NNG Messaging

```env
# NNG socket addresses
NNG_PRICES_ADDRESS=ipc:///tmp/polybot/prices.pub
NNG_EVENTS_ADDRESS=ipc:///tmp/polybot/events.pub
NNG_SIGNALS_ADDRESS=ipc:///tmp/polybot/signals.push
NNG_EXECUTOR_ADDRESS=ipc:///tmp/polybot/executor.req
```

---

## Strategy Configuration

### Arbitrage

```env
# Minimum profit percentage to trigger (0.01 = 1%)
ARB_MIN_PROFIT_PCT=0.01

# Price polling interval in seconds
ARB_POLL_INTERVAL_SEC=2

# Maximum position size per arbitrage trade
ARB_MAX_POSITION_USD=500

# Enable/disable the strategy
ARB_ENABLED=true
```

### Statistical Arbitrage

```env
# Minimum correlation to track market pairs
STAT_ARB_MIN_CORRELATION=0.8

# Spread threshold to trigger trades (0.05 = 5%)
STAT_ARB_SPREAD_THRESHOLD=0.05

# Historical lookback period for correlation
STAT_ARB_LOOKBACK_DAYS=30

# Exit when spread narrows to this level
STAT_ARB_EXIT_THRESHOLD=0.02

# Enable/disable
STAT_ARB_ENABLED=true
```

### AI Probability Model

```env
# Plugin to use (see ai-plugin-guide.md)
AI_MODEL_PLUGIN=example

# Plugin configuration as JSON
AI_MODEL_CONFIG={"seed": 42}

# Minimum model confidence to act (0-1)
AI_MIN_CONFIDENCE=0.7

# Minimum edge (predicted - market) to trade
AI_MIN_EDGE=0.05

# Maximum position per prediction
AI_MAX_POSITION_USD=200

# Enable/disable
AI_MODEL_ENABLED=false
```

### Spread Farming

```env
# Minimum spread to participate (0.02 = 2%)
SPREAD_FARM_MIN_SPREAD=0.02

# Maximum inventory in either direction
SPREAD_FARM_MAX_INVENTORY=1000

# Order size
SPREAD_FARM_ORDER_SIZE=50

# Price offset from best bid/ask
SPREAD_FARM_PRICE_OFFSET=0.005

# Enable/disable
SPREAD_FARM_ENABLED=false
```

### Copy Trading

```env
# Minimum whale balance to track (USD)
COPY_TRADE_MIN_WHALE_BALANCE=100000

# Percentage of whale's position to copy
COPY_TRADE_COPY_PCT=0.1

# Maximum position size when copying
COPY_TRADE_MAX_POSITION=500

# Delay before copying (seconds)
COPY_TRADE_FOLLOW_DELAY_SEC=60

# Specific wallets to track (comma-separated)
COPY_TRADE_WALLETS=

# Enable/disable
COPY_TRADE_ENABLED=false
```

---

## Configuration File

For more complex configurations, you can use a YAML or JSON config file:

```yaml
# config.yaml
polymarket:
  chain_id: 137

risk:
  max_position_size_usd: 1000
  max_total_exposure_usd: 10000
  daily_loss_limit_usd: 500

strategies:
  arbitrage:
    enabled: true
    min_profit_pct: 0.01
    poll_interval_sec: 2

  stat_arb:
    enabled: true
    min_correlation: 0.8
    spread_threshold: 0.05
```

Load with:
```bash
uv run polybot --config config.yaml start
```

---

## Runtime Configuration

Some settings can be modified at runtime via the API:

### Update Strategy Config
```bash
curl -X PUT http://localhost:8000/api/strategies/arbitrage \
  -H "Content-Type: application/json" \
  -d '{"enabled": false, "config": {"min_profit_pct": 0.02}}'
```

### Reload Configuration
```bash
curl -X POST http://localhost:8000/api/settings/reload
```

Note: Not all settings support hot-reloading. Risk limits require service restart.

---

## Secrets Management

For production deployments:

1. **Never commit `.env` files**
2. Use secret management services (AWS Secrets Manager, HashiCorp Vault)
3. Set environment variables directly in your deployment platform

### Docker Secrets

```yaml
# docker-compose.yml
services:
  polybot:
    secrets:
      - polymarket_private_key
    environment:
      - POLYMARKET_PRIVATE_KEY_FILE=/run/secrets/polymarket_private_key

secrets:
  polymarket_private_key:
    external: true
```

### Kubernetes Secrets

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: polybot-secrets
type: Opaque
stringData:
  POLYMARKET_PRIVATE_KEY: "your-private-key"
```

---

## Validation

Configuration is validated on startup. Common errors:

| Error | Cause | Solution |
|-------|-------|----------|
| `Invalid private key` | Key format wrong | Remove 0x prefix, ensure 64 hex chars |
| `Missing proxy address` | Not configured | Get from polymarket.com settings |
| `Invalid risk limits` | Negative values | Ensure all limits are positive |
| `Database path not writable` | Permission issue | Check directory permissions |

Run validation manually:
```bash
uv run polybot config
```
