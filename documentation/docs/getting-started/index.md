# Getting Started

Welcome to PolyBot! This guide will help you get up and running with automated trading on prediction markets.

## Prerequisites

- Python 3.11 or higher
- Node.js 18+ (for dashboard development)
- A Polymarket wallet with some USDC

## Installation Options

Choose your preferred installation method:

=== "PyPI (Recommended)"

    ```bash
    pip install polybot-trader
    ```

=== "Docker"

    ```bash
    git clone https://github.com/cryptuon/polybot
    cd polybot
    docker compose up -d
    ```

=== "From Source"

    ```bash
    git clone https://github.com/cryptuon/polybot
    cd polybot
    uv sync
    uv run polybot --help
    ```

## Quick Setup

### 1. Configure Credentials

```bash
# Create your configuration file
cp .env.example .env

# Edit with your credentials
nano .env
```

Required settings:
```
POLYMARKET_PRIVATE_KEY=your_wallet_private_key
POLYMARKET_PROXY_ADDRESS=your_proxy_address
```

### 2. Initialize Databases

```bash
polybot db init
```

### 3. Start in Shadow Mode

Shadow mode lets you test strategies without executing real trades:

```bash
# Enable a strategy
polybot strategy enable arbitrage

# Turn on shadow mode
polybot strategy shadow arbitrage --enable

# Start all services
polybot start
```

### 4. Access the Dashboard

Open [http://localhost:8000/ui](http://localhost:8000/ui) in your browser.

## Next Steps

- [Installation Details](installation.md) - Detailed installation instructions
- [Configuration Reference](configuration.md) - All configuration options
- [First Trade Guide](first-trade.md) - Complete walkthrough of your first trade
- [Strategy Overview](../user-guide/strategies/index.md) - Learn about available strategies
