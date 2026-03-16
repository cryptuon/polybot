# Arbitrage Strategy

The Arbitrage strategy exploits pricing inefficiencies when the combined price of YES and NO tokens is less than $1.

## How It Works

In a binary prediction market:
- YES + NO should equal $1 (minus fees)
- When YES + NO < $1, buy both for guaranteed profit
- Profit = $1 - (YES price + NO price) - fees

## Example

```
Market: "Will X happen?"
YES price: $0.45
NO price:  $0.52
Total:     $0.97

Buy $100 of YES ($0.45) = 222.22 shares
Buy $100 of NO  ($0.52) = 192.31 shares

Outcome if YES: 222.22 × $1 = $222.22
Outcome if NO:  192.31 × $1 = $192.31

Either way: ~$200 + profit - fees
Guaranteed profit: ~$3 (1.5%)
```

## Configuration

```bash
# Minimum profit percentage to trigger
ARB_MIN_PROFIT_PCT=0.01

# How often to scan (seconds)
ARB_POLL_INTERVAL_SEC=2

# Maximum position size
ARB_MAX_POSITION_SIZE=100
```

## Risk Level

**Low** - This is theoretically risk-free arbitrage, but consider:

- Execution risk (prices may move)
- Fee impact
- Liquidity constraints
- Market settlement risk

## When to Use

- Markets with low spreads
- Sufficient liquidity on both sides
- When combined prices are below $0.99

## CLI Commands

```bash
# Enable the strategy
polybot strategy enable arbitrage

# Run in shadow mode first
polybot strategy shadow arbitrage --enable

# Check for opportunities
polybot strategy run arbitrage
```

## Monitoring

Watch for:
- Number of opportunities found
- Execution success rate
- Average profit per trade
- Slippage impact
