# CLI Reference

Complete reference for the `polybot` command-line interface.

## Global Options

```bash
polybot [OPTIONS] COMMAND

Options:
  --version      Show version and exit
  --log-level    Set logging level (DEBUG, INFO, WARNING, ERROR)
  --help         Show help message
```

## Service Commands

### start

Start all services:

```bash
polybot start [OPTIONS]

Options:
  -s, --services  Specific services to start (can be repeated)
  --no-api        Don't start the API server

Examples:
  polybot start                    # Start all services
  polybot start -s scanner -s executor
  polybot start --no-api
```

### api

Run the API server:

```bash
polybot api [OPTIONS]

Options:
  --host    Host to bind to (default: from config)
  --port    Port to bind to (default: from config)
  --reload  Enable auto-reload for development

Examples:
  polybot api
  polybot api --host 0.0.0.0 --port 8080
  polybot api --reload
```

### scanner / executor / analytics

Run individual services:

```bash
polybot scanner    # Run scanner service
polybot executor   # Run executor service
polybot analytics  # Run analytics service
```

## Strategy Commands

### strategy list

List all strategies:

```bash
polybot strategy list
```

### strategy run

Run a single strategy:

```bash
polybot strategy run NAME

Examples:
  polybot strategy run arbitrage
  polybot strategy run stat_arb
```

### strategy enable / disable

Enable or disable a strategy:

```bash
polybot strategy enable NAME
polybot strategy disable NAME

Examples:
  polybot strategy enable arbitrage
  polybot strategy disable spread_farm
```

### strategy shadow

Toggle shadow mode:

```bash
polybot strategy shadow NAME [OPTIONS]

Options:
  --enable   Enable shadow mode
  --disable  Disable shadow mode

Examples:
  polybot strategy shadow arbitrage --enable
  polybot strategy shadow stat_arb --disable
```

## Database Commands

### db init

Initialize databases:

```bash
polybot db init
```

### db stats

Show performance statistics:

```bash
polybot db stats
```

## Configuration Commands

### config

Show current configuration:

```bash
polybot config
```

### auth

Manage API authentication:

```bash
polybot auth [OPTIONS]

Options:
  --create  Create new API credentials
  --derive  Derive existing credentials

Examples:
  polybot auth --derive
  polybot auth --create
```

## Statistical Arbitrage Commands

### statarb correlations

Show computed correlations:

```bash
polybot statarb correlations [OPTIONS]

Options:
  --min-corr  Minimum correlation to show (default: 0.5)
  --limit     Maximum pairs to show (default: 20)

Examples:
  polybot statarb correlations --min-corr 0.7
```

### statarb compute

Manually compute correlations:

```bash
polybot statarb compute [OPTIONS]

Options:
  --hours  Lookback hours (default: 48)

Examples:
  polybot statarb compute --hours 72
```

### statarb opportunities

Show current opportunities:

```bash
polybot statarb opportunities [OPTIONS]

Options:
  --spread    Minimum spread threshold (default: 0.04)
  --min-corr  Minimum correlation (default: 0.7)

Examples:
  polybot statarb opportunities --spread 0.05
```

### statarb prices

Show price snapshot summary:

```bash
polybot statarb prices [OPTIONS]

Options:
  --limit  Number of markets to show (default: 20)
```

## AI Model Commands

### ai plugins

List available AI plugins:

```bash
polybot ai plugins
```

### ai info

Show plugin information:

```bash
polybot ai info PLUGIN_NAME

Examples:
  polybot ai info simple_heuristic
  polybot ai info perplexity
```

### ai predict

Test prediction on a market:

```bash
polybot ai predict MARKET_ID [OPTIONS]

Options:
  -p, --plugin  Plugin to use (default: simple_heuristic)
  -c, --config  Plugin config JSON (default: {})

Examples:
  polybot ai predict 0x123... --plugin claude
```

### ai scan

Scan markets for opportunities:

```bash
polybot ai scan [OPTIONS]

Options:
  -p, --plugin    Plugin to use (default: simple_heuristic)
  --min-edge      Minimum edge threshold (default: 0.05)
  --limit         Number of markets to scan (default: 20)

Examples:
  polybot ai scan --plugin claude --min-edge 0.10
```

## Environment Variables

Key environment variables:

| Variable | Description |
|----------|-------------|
| `POLYMARKET_PRIVATE_KEY` | Wallet private key |
| `POLYMARKET_PROXY_ADDRESS` | Proxy wallet address |
| `LOG_LEVEL` | Logging level |
| `API_HOST` | API bind address |
| `API_PORT` | API port |

See [Configuration Reference](../getting-started/configuration.md) for full list.

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Configuration error |
| 130 | Interrupted (Ctrl+C) |
