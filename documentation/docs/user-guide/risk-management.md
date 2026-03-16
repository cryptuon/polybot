# Risk Management

PolyBot includes comprehensive risk management controls to protect your capital.

## Risk Limits

### Position Limits

```bash
# Maximum size for any single position
MAX_POSITION_SIZE_USD=1000

# Maximum number of open orders
MAX_OPEN_ORDERS=50
```

### Exposure Limits

```bash
# Maximum total capital at risk
MAX_TOTAL_EXPOSURE_USD=10000

# Maximum exposure per venue
RISK_MAX_VENUE_EXPOSURE_USD=5000

# Maximum concentration in one venue
RISK_MAX_VENUE_CONCENTRATION=0.7
```

### Loss Limits

```bash
# Stop trading after this daily loss
DAILY_LOSS_LIMIT_USD=500
```

## How Limits Work

### Pre-Trade Checks

Before every trade, PolyBot checks:

1. **Position size** - Is order within limits?
2. **Total exposure** - Will this exceed max exposure?
3. **Daily P&L** - Have we hit loss limit?
4. **Open orders** - Are we at max orders?

If any check fails, the signal is rejected.

### Real-Time Monitoring

The executor service continuously monitors:

- Current exposure across all positions
- Unrealized P&L
- Daily realized P&L
- Per-venue concentration

## Risk Dashboard

View risk metrics in the dashboard:

```
http://localhost:8000/ui
```

Or via CLI:

```bash
polybot risk status
```

Shows:
- Current exposure vs limits
- P&L for the day
- Position breakdown by strategy
- Alerts and warnings

## Per-Strategy Limits

Each strategy has its own limits:

```python
class MyStrategy(BaseStrategy):
    def _get_config(self) -> StrategyConfig:
        return StrategyConfig(
            max_position_size=100.0,  # USD
            max_positions=5,           # count
        )
```

## Delta Management

For multi-venue trading:

```bash
# Maximum net delta (directional exposure)
RISK_MAX_DELTA=500

# Trigger auto-hedge at this delta
RISK_HEDGE_DELTA_THRESHOLD=100

# Enable automatic hedging
RISK_AUTO_HEDGE_ENABLED=false
```

## Alerts

PolyBot generates alerts when:

- Exposure exceeds 80% of limit
- Daily loss exceeds 50% of limit
- Position concentration too high
- Unusual activity detected

View alerts:
```bash
polybot alerts list
```

## Best Practices

### Starting Out

1. **Use conservative limits** - Start small
2. **Enable shadow mode** - Test without real risk
3. **Monitor actively** - Watch the dashboard
4. **Review daily** - Check P&L and positions

### Scaling Up

1. **Increase gradually** - 20-50% at a time
2. **Track metrics** - Win rate, average P&L
3. **Adjust per strategy** - Different strategies, different limits
4. **Keep reserves** - Don't deploy 100% of capital

### Emergency Procedures

If something goes wrong:

```bash
# Disable all strategies immediately
polybot strategy disable --all

# Cancel all open orders
polybot orders cancel --all

# Check positions
polybot positions

# Review recent activity
polybot logs --tail 100
```

## Configuration Examples

### Conservative

```bash
MAX_POSITION_SIZE_USD=100
MAX_TOTAL_EXPOSURE_USD=1000
DAILY_LOSS_LIMIT_USD=50
```

### Moderate

```bash
MAX_POSITION_SIZE_USD=500
MAX_TOTAL_EXPOSURE_USD=5000
DAILY_LOSS_LIMIT_USD=250
```

### Aggressive

```bash
MAX_POSITION_SIZE_USD=2000
MAX_TOTAL_EXPOSURE_USD=20000
DAILY_LOSS_LIMIT_USD=1000
```

!!! warning
    Higher limits mean higher potential losses. Only use aggressive settings if you fully understand the risks.
