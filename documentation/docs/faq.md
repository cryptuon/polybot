# Frequently Asked Questions

## General

### What is PolyBot?

PolyBot is an open-source automated trading system for prediction markets like Polymarket and Kalshi. It provides 10 trading strategies, a web dashboard, and a plugin system for AI models.

### Is PolyBot free?

Yes, PolyBot is free and open-source under the MIT License. You can use it for personal or commercial purposes.

### What prediction markets does PolyBot support?

- **Polymarket** - Full support (primary focus)
- **Kalshi** - Supported (CFTC-regulated)
- **Binance** - For hedging (futures/options)

## Installation

### What are the system requirements?

- Python 3.11 or higher
- 2GB RAM minimum
- 500MB disk space
- Linux, macOS, or Windows (WSL recommended)

### How do I install PolyBot?

```bash
pip install polybot-trader
```

See [Installation Guide](getting-started/installation.md) for detailed instructions.

### Can I run PolyBot on Windows?

Yes, but we recommend using WSL2 (Windows Subsystem for Linux) for the best experience, particularly for NNG socket support.

## Configuration

### What credentials do I need?

For Polymarket:
- `POLYMARKET_PRIVATE_KEY` - Your Ethereum wallet private key
- `POLYMARKET_PROXY_ADDRESS` - Your Polymarket proxy address

### How do I get my Polymarket proxy address?

1. Go to [polymarket.com](https://polymarket.com)
2. Connect your wallet
3. Your proxy address is shown in your profile

### Is my private key safe?

PolyBot stores credentials in environment variables, never in code. For production:
- Use Docker secrets or a vault
- Never commit `.env` files
- Consider hardware wallets

## Trading

### What is shadow mode?

Shadow mode lets you test strategies without executing real trades. Signals are generated and logged, but no orders are placed.

```bash
polybot strategy shadow arbitrage --enable
```

### How do I start trading for real?

1. Test thoroughly in shadow mode first
2. Disable shadow mode: `polybot strategy shadow <strategy> --disable`
3. Start with small position sizes
4. Monitor closely

### What are the risk controls?

- **Position limits** - Max size per position
- **Daily loss limit** - Stop trading after losses
- **Total exposure cap** - Max capital at risk
- **Per-strategy limits** - Individual strategy controls

Configure in `.env`:
```bash
MAX_POSITION_SIZE_USD=1000
MAX_TOTAL_EXPOSURE_USD=10000
DAILY_LOSS_LIMIT_USD=500
```

### Which strategy should I start with?

For beginners:
1. **Arbitrage** - Lowest risk when YES + NO < $1
2. **Spread Farming** - Consistent but small returns

As you gain experience:
3. **Statistical Arbitrage** - Requires understanding correlations
4. **AI Model** - Depends on model quality

## Development

### How do I build a custom strategy?

```python
from polybot.strategies.base import BaseStrategy

class MyStrategy(BaseStrategy):
    name = "my_strategy"
    
    async def scan(self, update):
        # Your logic
        return []
    
    async def should_exit(self, position, update):
        return False
```

See [Custom Strategy Guide](developer-guide/extending/custom-strategy.md).

### How do I create an AI plugin?

```python
from polybot.plugins.base import AIModelPlugin

class MyPlugin(AIModelPlugin):
    name = "my_plugin"
    
    async def predict(self, context):
        # Your model
        return Prediction(yes_probability=0.5, confidence=0.5)
```

See [AI Plugin Guide](developer-guide/extending/ai-plugins.md).

### How do I add a new venue?

Inherit from `BaseVenue` and implement the required methods. See [Custom Venue Guide](developer-guide/extending/custom-venue.md).

## Troubleshooting

### Why are my orders not executing?

Check:
1. Shadow mode is disabled
2. Sufficient balance on Polymarket
3. Valid API credentials
4. Risk limits not exceeded
5. Market is active and tradeable

### Why do I get NNG socket errors?

On Linux/macOS:
```bash
mkdir -p /tmp/polybot
chmod 777 /tmp/polybot
```

On Windows, use WSL2.

### How do I view logs?

```bash
# CLI logs to console
polybot start --log-level DEBUG

# Docker logs
docker compose logs -f polybot
```

### My strategy isn't finding opportunities?

1. Check market conditions match strategy requirements
2. Review strategy parameters (thresholds, limits)
3. Enable debug logging
4. Verify price data is flowing

## Performance

### How much can I expect to make?

Returns vary based on:
- Market conditions
- Strategy selection
- Risk parameters
- Execution quality

**Important**: Past performance doesn't guarantee future results. Always start small and test thoroughly.

### What's the latency?

Typical latency components:
- Scanner polling: 1-2 seconds
- Signal processing: <100ms
- Order submission: 200-500ms
- Execution: Market dependent

### Can I run multiple strategies?

Yes! Enable multiple strategies:
```bash
polybot strategy enable arbitrage
polybot strategy enable spread_farm
polybot strategy enable stat_arb
```

They run concurrently and share risk limits.

## Support

### Where can I get help?

- **Documentation**: [docs.cryptuon.com/polybot](https://docs.cryptuon.com/polybot)
- **Discord**: [discord.gg/cryptuon](https://discord.gg/cryptuon)
- **GitHub Issues**: [github.com/cryptuon/polybot/issues](https://github.com/cryptuon/polybot/issues)

### How do I report a bug?

1. Search existing issues first
2. Create a new issue with:
   - Clear description
   - Steps to reproduce
   - Expected vs actual behavior
   - Environment details

### How do I contribute?

See [Contributing Guide](CONTRIBUTING.md). We welcome:
- Bug fixes
- New strategies
- Documentation improvements
- AI plugins
