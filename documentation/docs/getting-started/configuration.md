# Configuration Reference

PolyBot is configured via environment variables, typically stored in a `.env` file.

## Quick Setup

```bash
# Copy template
cp .env.example .env

# Edit with your credentials
nano .env
```

## Required Settings

### Polymarket Credentials

```bash
# Your Ethereum wallet private key (without 0x prefix)
POLYMARKET_PRIVATE_KEY=your_private_key_here

# Your Polymarket proxy address (with 0x prefix)
POLYMARKET_PROXY_ADDRESS=0x...
```

!!! warning "Security"
    Never commit your private key to version control. Use environment variables or secrets management in production.

## Strategy Configuration

### Arbitrage

```bash
ARB_MIN_PROFIT_PCT=0.01      # Minimum profit percentage (1%)
ARB_POLL_INTERVAL_SEC=2      # Polling interval in seconds
ARB_MAX_POSITION_SIZE=100    # Max position size in USD
```

### Statistical Arbitrage

```bash
STAT_ARB_SPREAD_THRESHOLD=0.04   # Min spread to trigger (4%)
STAT_ARB_LOOKBACK_HOURS=24       # Correlation lookback period
STAT_ARB_MIN_CORRELATION=0.7     # Minimum correlation coefficient
```

### AI Model

```bash
AI_MODEL_PLUGIN=simple_heuristic  # Plugin to use
AI_MODEL_CONFIG={}                # Plugin config (JSON)
AI_MIN_CONFIDENCE=0.7             # Minimum model confidence
AI_MIN_EDGE=0.05                  # Minimum edge vs market (5%)
```

### Spread Farming

```bash
SPREAD_FARM_MIN_SPREAD=0.02   # Minimum spread to farm (2%)
SPREAD_FARM_ORDER_SIZE=10     # Order size in USD
```

### Copy Trading

```bash
COPY_TRADE_MIN_WHALE_BALANCE=100000   # Min whale balance to track
COPY_TRADE_PROPORTIONAL_SIZE=0.01     # Proportion of whale trade
```

## Risk Management

```bash
# Position limits
MAX_POSITION_SIZE_USD=1000    # Max per position
MAX_TOTAL_EXPOSURE_USD=10000  # Total capital at risk
DAILY_LOSS_LIMIT_USD=500      # Stop after this loss
MAX_OPEN_ORDERS=50            # Maximum concurrent orders

# Multi-venue limits
RISK_MAX_VENUE_EXPOSURE_USD=5000   # Max per venue
RISK_MAX_VENUE_CONCENTRATION=0.7   # Max % in one venue
```

## Database

```bash
SQLITE_PATH=./data/polybot.db           # Operational data
DUCKDB_PATH=./data/analytics.duckdb     # Analytics data
STRATEGY_LOGS_PATH=./data/strategy_logs.duckdb
```

## API Server

```bash
API_HOST=127.0.0.1    # Bind address
API_PORT=8000         # Port number
API_RELOAD=false      # Auto-reload (development)
```

## Authentication

```bash
# Enable for production
AUTH_ENABLED=false

# JWT configuration
AUTH_JWT_SECRET=           # Required when AUTH_ENABLED=true
AUTH_JWT_ALGORITHM=HS256
AUTH_JWT_EXPIRE_MINUTES=60

# API keys (comma-separated SHA256 hashes)
AUTH_API_KEYS_HASH=
```

## CORS

```bash
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173
CORS_ALLOW_CREDENTIALS=true
CORS_ALLOW_METHODS=GET,POST,PUT,DELETE,OPTIONS
CORS_ALLOW_HEADERS=Authorization,X-API-Key,Content-Type,Accept
```

## Logging

```bash
LOG_LEVEL=INFO    # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FORMAT=json   # json or text
```

## NNG Messaging

```bash
NNG_IPC_PATH=/tmp/polybot     # IPC socket directory
NNG_RECV_TIMEOUT_MS=1000      # Receive timeout
```

## External APIs (Optional)

```bash
# For AI plugins
PERPLEXITY_API_KEY=
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
```

## Multi-Venue Configuration

### Binance (for hedging)

```bash
BINANCE_API_KEY=
BINANCE_API_SECRET=
BINANCE_TESTNET=true         # Use testnet for safety
BINANCE_SPOT_ENABLED=true
BINANCE_FUTURES_ENABLED=false
BINANCE_OPTIONS_ENABLED=false
```

### Kalshi

```bash
KALSHI_API_KEY=
KALSHI_API_SECRET=
KALSHI_ENVIRONMENT=demo      # demo or prod
KALSHI_COMPLIANCE_APPROVED=false
```

## Environment-Specific

### Development

```bash
LOG_LEVEL=DEBUG
API_RELOAD=true
AUTH_ENABLED=false
```

### Production

```bash
LOG_LEVEL=INFO
LOG_FORMAT=json
API_RELOAD=false
AUTH_ENABLED=true
AUTH_JWT_SECRET=your-secure-secret-here
```

## Docker Overrides

When using Docker, some settings are overridden:

```bash
API_HOST=0.0.0.0        # Bind to all interfaces
SQLITE_PATH=/app/data/polybot.db
DUCKDB_PATH=/app/data/analytics.duckdb
```

## Validation

Check your configuration:

```bash
polybot config
```

This shows the current effective configuration (with secrets masked).
