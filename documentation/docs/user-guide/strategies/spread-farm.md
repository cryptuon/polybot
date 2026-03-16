# Spread Farming Strategy

The Spread Farming strategy provides liquidity to prediction markets by placing orders on both sides of the order book, capturing the bid-ask spread.

## How It Works

1. **Identify wide spreads** - Find markets with spreads above threshold
2. **Place limit orders** - Post bids and asks around mid price
3. **Capture spread** - Profit when both sides fill
4. **Manage inventory** - Balance YES/NO holdings

## Example

```
Market: "Will X happen?"
Best Bid: $0.48
Best Ask: $0.52
Spread: $0.04 (4%)

Strategy places:
- Bid at $0.49 (buy YES)
- Ask at $0.51 (sell YES)

If both fill:
- Buy at $0.49, sell at $0.51
- Profit: $0.02 per share (4% round-trip)
```

## Configuration

```bash
# Minimum spread to farm
SPREAD_FARM_MIN_SPREAD=0.02

# Order size in USD
SPREAD_FARM_ORDER_SIZE=10
```

## Risk Level

**Low** - But requires active inventory management.

Risks:
- Inventory risk (holding unwanted positions)
- Adverse selection (informed traders pick you off)
- Market moves while orders are open
- Fill rate may be low

## When to Use

- Markets with wide spreads (>2%)
- Stable, range-bound markets
- Markets with consistent two-way flow
- When you have capital for inventory

## Inventory Management

The strategy tracks inventory to avoid excessive exposure:

- **Max inventory**: Limits total YES or NO held
- **Skewing**: Adjusts quotes based on current inventory
- **Rebalancing**: Reduces position when limits approached

## CLI Commands

```bash
# Enable the strategy
polybot strategy enable spread_farm

# Monitor in shadow mode first
polybot strategy shadow spread_farm --enable

# Check current positions
polybot positions
```

## Best Practices

1. **Start with small sizes** - Build up as you learn market dynamics
2. **Monitor fill rates** - Adjust pricing if fills are too low/high
3. **Watch for adverse selection** - Wide spreads may indicate risk
4. **Set inventory limits** - Don't accumulate too much directional risk
5. **Consider market events** - Reduce activity before major news
