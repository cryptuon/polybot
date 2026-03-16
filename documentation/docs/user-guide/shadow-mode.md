# Shadow Mode

Shadow mode lets you test strategies without executing real trades. Signals are generated and logged, but no orders are placed.

## Why Use Shadow Mode?

- **Test new strategies** - Verify logic before risking capital
- **Validate configuration** - Ensure settings work as expected
- **Learn the system** - Understand how PolyBot operates
- **Debug issues** - Troubleshoot without financial risk

## Enabling Shadow Mode

### Per Strategy

```bash
# Enable shadow mode for a specific strategy
polybot strategy shadow arbitrage --enable

# Disable shadow mode (go live)
polybot strategy shadow arbitrage --disable
```

### Check Status

```bash
# List strategies with shadow status
polybot strategy list
```

Output:
```
┌────────────┬─────────────────────────┬─────────┬────────┐
│ Name       │ Description             │ Enabled │ Shadow │
├────────────┼─────────────────────────┼─────────┼────────┤
│ arbitrage  │ YES+NO arbitrage        │ ✓       │ ✓      │
│ stat_arb   │ Statistical arbitrage   │ ✓       │ ✗      │
│ ai_model   │ AI model predictions    │ ✗       │ ✗      │
└────────────┴─────────────────────────┴─────────┴────────┘
```

## How Shadow Mode Works

### Normal Mode

```
Price Update → Strategy Scan → Signal → Executor → Order Placed
```

### Shadow Mode

```
Price Update → Strategy Scan → Signal → Logged (no execution)
```

In shadow mode:
- Strategies receive real price data
- Signals are generated normally
- Signals are logged to the strategy logs database
- **No orders are sent to the exchange**

## Viewing Shadow Signals

### Dashboard

View shadow signals in the web UI:
```
http://localhost:8000/ui → Strategy Logs
```

### CLI

```bash
# View recent strategy logs
polybot logs strategy arbitrage --tail 50

# Filter by signal type
polybot logs strategy arbitrage --type signal
```

### API

```bash
curl http://localhost:8000/api/strategy-logs?strategy=arbitrage
```

## Analyzing Shadow Performance

Track hypothetical performance:

1. **Signal count** - How many opportunities found?
2. **Signal quality** - What prices were signaled?
3. **Timing** - When do signals occur?
4. **Strategy comparison** - Which strategies find more opportunities?

## Transitioning to Live

When you're ready to go live:

### 1. Review Shadow Results

```bash
# Check shadow performance
polybot logs strategy arbitrage --days 7
```

Look for:
- Consistent signal generation
- Reasonable prices
- No errors or anomalies

### 2. Start Small

```bash
# Set conservative limits
MAX_POSITION_SIZE_USD=50
MAX_TOTAL_EXPOSURE_USD=500
```

### 3. Disable Shadow Mode

```bash
polybot strategy shadow arbitrage --disable
```

### 4. Monitor Closely

Watch the first few trades carefully:
- Check execution prices
- Verify position tracking
- Monitor P&L

## Best Practices

1. **Run shadow for at least 24-48 hours** - See different market conditions
2. **Compare to expectations** - Are signals what you expected?
3. **Check error logs** - Any issues during shadow period?
4. **Test all strategies** - Shadow each before going live
5. **Keep some strategies in shadow** - Compare live vs shadow performance

## Troubleshooting

### No signals in shadow mode

- Check strategy is enabled: `polybot strategy list`
- Verify market conditions match strategy requirements
- Check for errors: `polybot logs --level ERROR`

### Too many signals

- Review strategy thresholds
- Check if parameters are too aggressive
- Verify data quality

### Shadow and live disagreement

- Execution slippage is normal
- Live has real market impact
- Timing differences matter
