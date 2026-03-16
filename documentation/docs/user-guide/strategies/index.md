# Trading Strategies

PolyBot includes 10 trading strategies for prediction markets, ranging from low-risk arbitrage to AI-powered prediction.

## Strategy Overview

| Strategy | Risk | Description | Best For |
|----------|------|-------------|----------|
| [Arbitrage](arbitrage.md) | Low | YES + NO < $1 | Risk-free profits |
| [Statistical Arbitrage](stat-arb.md) | Medium | Correlated market divergence | Pairs trading |
| [AI Model](ai-model.md) | Medium | ML-predicted mispricing | Alpha generation |
| [Spread Farming](spread-farm.md) | Low | Market making | Consistent income |
| [Copy Trading](copy-trade.md) | Medium | Follow whale traders | Passive strategy |
| Resolution Arb | Low | Near-expiry opportunities | Quick profits |
| Calendar Spread | Medium | Time-based discrepancies | Event trading |
| Momentum | High | Trend following | Volatile markets |
| Poll Divergence | Medium | Poll vs price divergence | Political markets |
| Volume Spike | High | Unusual volume patterns | Breakout trading |

## Managing Strategies

### List Available Strategies

```bash
polybot strategy list
```

### Enable/Disable

```bash
# Enable a strategy
polybot strategy enable arbitrage

# Disable a strategy
polybot strategy disable arbitrage
```

### Shadow Mode

Test strategies without real trades:

```bash
# Enable shadow mode
polybot strategy shadow arbitrage --enable

# Disable shadow mode (go live)
polybot strategy shadow arbitrage --disable
```

### Run Single Strategy

```bash
polybot strategy run arbitrage
```

## Strategy Selection Guide

### Low Risk, Steady Returns

- **Arbitrage**: Pure risk-free when YES + NO < $1
- **Spread Farming**: Market making with inventory management

### Medium Risk, Higher Potential

- **Statistical Arbitrage**: Requires market correlation analysis
- **AI Model**: Depends on model quality
- **Copy Trading**: Depends on whale selection

### High Risk, High Reward

- **Momentum**: Works in trending markets
- **Volume Spike**: Requires quick execution

## Configuration

Each strategy has specific configuration options. See individual strategy pages for details.

Common settings in `.env`:

```bash
# Risk limits apply to all strategies
MAX_POSITION_SIZE_USD=1000
MAX_TOTAL_EXPOSURE_USD=10000
DAILY_LOSS_LIMIT_USD=500
```

## Strategy Development

Want to build your own strategy? See the [Custom Strategy Guide](../../developer-guide/extending/custom-strategy.md).
