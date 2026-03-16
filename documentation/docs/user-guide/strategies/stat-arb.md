# Statistical Arbitrage Strategy

The Statistical Arbitrage (Stat Arb) strategy exploits price divergences between correlated prediction markets.

## How It Works

1. **Identify correlated markets** - Find markets that historically move together
2. **Monitor spread** - Track the price difference between correlated pairs
3. **Trade divergence** - When spread exceeds threshold, bet on convergence
4. **Exit on convergence** - Close positions when prices realign

## Example

```
Market A: "Will candidate X win state Y?" - YES at $0.60
Market B: "Will candidate X win state Z?" - YES at $0.45

Historical correlation: 0.85
Current spread: 15% (above 4% threshold)

Strategy:
- Buy YES on Market B (underpriced)
- Optionally sell YES on Market A (overpriced)
- Wait for convergence
```

## Configuration

```bash
# Minimum spread to trigger a trade
STAT_ARB_SPREAD_THRESHOLD=0.04

# Hours of price history for correlation
STAT_ARB_LOOKBACK_HOURS=24

# Minimum correlation coefficient
STAT_ARB_MIN_CORRELATION=0.7
```

## Risk Level

**Medium** - Correlation can break down, especially during major events.

Risks:
- Correlation breakdown
- Markets may diverge further before converging
- Liquidity differences between markets
- Event risk affecting one market but not the other

## CLI Commands

```bash
# View computed correlations
polybot statarb correlations --min-corr 0.7

# Manually compute correlations
polybot statarb compute --hours 48

# Show current opportunities
polybot statarb opportunities --spread 0.04

# Enable the strategy
polybot strategy enable stat_arb
```

## Finding Correlated Markets

PolyBot automatically computes correlations between active markets. Good candidates:

- Related political outcomes (same election, different states)
- Sequential events (quarters, months)
- Correlated economic indicators
- Related sports outcomes

## Best Practices

1. **Verify correlation logic** - Ensure markets should actually be correlated
2. **Check liquidity** - Both markets need sufficient volume
3. **Monitor actively** - Correlations can break during major news
4. **Use position limits** - Don't overexpose to correlation risk
