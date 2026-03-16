# Quick Start

Get PolyBot running in 5 minutes.

## 1. Install

```bash
pip install polybot-trader
```

## 2. Configure

Create a `.env` file with your Polymarket credentials:

```bash
# Required
POLYMARKET_PRIVATE_KEY=your_private_key_here
POLYMARKET_PROXY_ADDRESS=0x_your_proxy_address

# Optional - will be derived if not provided
POLYMARKET_API_KEY=
POLYMARKET_API_SECRET=
POLYMARKET_API_PASSPHRASE=
```

!!! tip "Finding Your Proxy Address"
    Your proxy address is shown in your Polymarket profile at [polymarket.com](https://polymarket.com). It's different from your main wallet address.

## 3. Initialize

```bash
# Initialize databases
polybot db init

# Generate API credentials (if not provided)
polybot auth --derive
```

## 4. Enable a Strategy

Start with arbitrage in shadow mode (no real trades):

```bash
# Enable the strategy
polybot strategy enable arbitrage

# Turn on shadow mode for safety
polybot strategy shadow arbitrage --enable
```

## 5. Start Trading

```bash
polybot start
```

## 6. Monitor

Open the dashboard:
```
http://localhost:8000/ui
```

You should see:
- Strategy status showing "arbitrage" enabled
- Scanner service fetching market data
- Signals appearing in strategy logs (shadow mode)

## What's Next?

### Test More Strategies

```bash
# Enable statistical arbitrage
polybot strategy enable stat_arb
polybot strategy shadow stat_arb --enable

# Check for opportunities
polybot statarb opportunities
```

### Go Live

When you're confident:

```bash
# Disable shadow mode
polybot strategy shadow arbitrage --disable

# Monitor closely!
```

### Explore the Docs

- [Configuration Reference](configuration.md) - All settings explained
- [Strategy Guide](../user-guide/strategies/index.md) - Learn each strategy
- [Risk Management](../user-guide/risk-management.md) - Protect your capital

## Troubleshooting

### "No module named polybot"

```bash
# Make sure it's installed
pip install polybot-trader

# Or activate your virtual environment
source .venv/bin/activate
```

### "Invalid credentials"

```bash
# Regenerate API credentials
polybot auth --derive
```

### "Connection refused"

```bash
# Check if services are running
polybot start

# Verify API is accessible
curl http://localhost:8000/
```

### Need Help?

- [FAQ](../faq.md)
- [Discord](https://discord.gg/cryptuon)
- [GitHub Issues](https://github.com/cryptuon/polybot/issues)
