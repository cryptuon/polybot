# User Guide

This section covers everything you need to use PolyBot effectively.

## Trading Strategies

PolyBot includes 10 trading strategies:

- **[Arbitrage](strategies/arbitrage.md)** - Risk-free when YES + NO < $1
- **[Statistical Arbitrage](strategies/stat-arb.md)** - Trade correlated markets
- **[AI Model](strategies/ai-model.md)** - ML-predicted mispricing
- **[Spread Farming](strategies/spread-farm.md)** - Market making
- **[Copy Trading](strategies/copy-trade.md)** - Follow whale traders

[View all strategies](strategies/index.md)

## Trading Venues

Trade across multiple prediction markets:

- **[Polymarket](venues/polymarket.md)** - Largest crypto prediction market
- **[Kalshi](venues/kalshi.md)** - CFTC-regulated US platform
- **Binance** - For hedging (futures/options)

[Venue configuration](venues/index.md)

## Risk Management

Protect your capital with built-in controls:

- Position size limits
- Daily loss limits
- Total exposure caps
- Per-strategy limits

[Risk management guide](risk-management.md)

## Shadow Mode

Test strategies without real money:

```bash
polybot strategy shadow arbitrage --enable
```

[Shadow mode guide](shadow-mode.md)

## Dashboard

Monitor your trading from the web interface:

- Real-time P&L
- Open positions
- Strategy status
- Order history

[Dashboard guide](dashboard.md)

## CLI Reference

Complete command reference:

```bash
polybot --help
```

[Full CLI reference](cli-reference.md)
