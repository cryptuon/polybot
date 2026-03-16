# Trading Venues

PolyBot supports multiple prediction market venues, allowing you to trade across platforms and implement cross-venue strategies.

## Supported Venues

| Venue | Status | Type | Notes |
|-------|--------|------|-------|
| [Polymarket](polymarket.md) | Full Support | Crypto | Primary focus |
| [Kalshi](kalshi.md) | Supported | Regulated | CFTC-regulated |
| Binance | Hedging | Crypto Exchange | Futures/options |

## Multi-Venue Architecture

```
┌─────────────────────────────────────────┐
│            PolyBot Core                  │
├─────────────────────────────────────────┤
│  ┌─────────┐ ┌─────────┐ ┌─────────┐   │
│  │Polymarket│ │ Kalshi  │ │ Binance │   │
│  └─────────┘ └─────────┘ └─────────┘   │
└─────────────────────────────────────────┘
```

## Configuration

Enable/disable venues in `.env`:

```bash
VENUES_POLYMARKET_ENABLED=true
VENUES_KALSHI_ENABLED=false
VENUES_BINANCE_ENABLED=false
```

## Risk Management

Per-venue risk limits:

```bash
RISK_MAX_VENUE_EXPOSURE_USD=5000
RISK_MAX_VENUE_CONCENTRATION=0.7
```

## Cross-Venue Strategies

Some strategies work across venues:

- **Arbitrage**: Same event, different venues
- **Hedging**: Prediction market + derivatives
- **Diversification**: Spread risk across platforms

## Adding New Venues

Developers can add new venues by implementing the `BaseVenue` interface.

See [Custom Venue Guide](../../developer-guide/extending/custom-venue.md).
