# Your First Trade

A complete walkthrough of making your first trade with PolyBot.

## Prerequisites

Before starting, ensure you have:

- [ ] PolyBot installed (`pip install polybot-trader`)
- [ ] Polymarket account with USDC deposited
- [ ] Configuration file (`.env`) with credentials
- [ ] Databases initialized (`polybot db init`)

## Step 1: Verify Configuration

Check your setup:

```bash
polybot config
```

You should see your API endpoints and risk settings (credentials are masked).

## Step 2: Start in Shadow Mode

Always test with shadow mode first:

```bash
# Enable arbitrage strategy
polybot strategy enable arbitrage

# Enable shadow mode
polybot strategy shadow arbitrage --enable

# Verify status
polybot strategy list
```

Output should show:
```
arbitrage | Enabled: ✓ | Shadow: ✓
```

## Step 3: Start Services

```bash
polybot start
```

This starts:
- Scanner (fetches market data)
- Executor (handles orders)
- Analytics (tracks performance)
- API (dashboard and REST)

## Step 4: Monitor Shadow Activity

### Option A: Dashboard

Open http://localhost:8000/ui and navigate to "Strategy Logs".

### Option B: CLI

```bash
# Watch logs in real-time
polybot logs strategy arbitrage --follow
```

You should see signals being generated (but not executed).

## Step 5: Review Shadow Performance

After running shadow mode for a while (24-48 hours recommended):

```bash
# Check signal count
polybot logs strategy arbitrage --type signal --count

# View recent signals
polybot logs strategy arbitrage --tail 20
```

Questions to ask:
- Are signals being generated?
- Do the prices look reasonable?
- Any errors or warnings?

## Step 6: Set Conservative Limits

Before going live, set safe limits:

```bash
# Edit .env
MAX_POSITION_SIZE_USD=50
MAX_TOTAL_EXPOSURE_USD=200
DAILY_LOSS_LIMIT_USD=25
```

Restart to apply:
```bash
# Ctrl+C to stop, then:
polybot start
```

## Step 7: Go Live

When you're confident:

```bash
# Disable shadow mode
polybot strategy shadow arbitrage --disable

# Verify
polybot strategy list
```

Output should show:
```
arbitrage | Enabled: ✓ | Shadow: ✗
```

## Step 8: Monitor Your First Trade

Watch closely for your first real trade:

### Dashboard
- Check "Positions" for new positions
- Check "Orders" for order status

### CLI
```bash
# Watch for fills
polybot logs --follow --level INFO
```

### What to Expect

1. **Signal generated** - Strategy finds opportunity
2. **Order placed** - Executor submits to Polymarket
3. **Order filled** - Trade executed
4. **Position created** - Now tracking the position

## Step 9: Managing Positions

View your positions:

```bash
polybot positions
```

The dashboard shows:
- Entry price
- Current price
- Unrealized P&L

## Step 10: Reviewing Results

After your first day:

```bash
# Performance summary
polybot db stats

# Detailed analytics
# Open dashboard → Analytics
```

## Common First Trade Issues

### No Signals Generated

- Market conditions may not match strategy requirements
- Check if markets have sufficient liquidity
- Verify scanner is running: check logs for "price update" messages

### Order Rejected

- Insufficient balance on Polymarket
- Risk limits exceeded
- Market may have moved

### Unexpected Position Size

- Check `MAX_POSITION_SIZE_USD` setting
- Review strategy-specific limits

## Next Steps

Congratulations on your first trade! Now:

1. **Gradually increase limits** - As you gain confidence
2. **Try other strategies** - Each has different risk/reward
3. **Add more strategies** - Diversify your approach
4. **Review regularly** - Check performance daily

## Safety Checklist

Before each trading session:

- [ ] Sufficient balance on Polymarket
- [ ] Risk limits set appropriately
- [ ] Monitoring dashboard open
- [ ] Know how to emergency stop

Emergency stop:
```bash
# Disable all strategies
polybot strategy disable arbitrage
polybot strategy disable stat_arb
# ... or Ctrl+C to stop all services
```
