# Copy Trading Strategy

The Copy Trading strategy identifies successful traders ("whales") and mirrors their trades proportionally.

## How It Works

1. **Identify whales** - Find wallets with large balances and good track records
2. **Monitor activity** - Watch for new trades from tracked wallets
3. **Mirror trades** - Execute similar trades at a configured proportion
4. **Follow exits** - Close positions when whale exits

## Example

```
Tracked whale: 0xabc...
Whale balance: $500,000
Your allocation: 1% of whale size

Whale buys:
- $10,000 of YES on "Will X happen?"

Your trade:
- $100 of YES (1% of $10,000)
```

## Configuration

```bash
# Minimum wallet balance to track (filters out small traders)
COPY_TRADE_MIN_WHALE_BALANCE=100000

# Proportion of whale trade to copy
COPY_TRADE_PROPORTIONAL_SIZE=0.01
```

## Risk Level

**Medium** - Your success depends on whale selection.

Risks:
- Whale may have different risk tolerance
- Execution delay (you trade after whale)
- Whale may have information you don't
- Whale strategy may not scale to smaller sizes

## Finding Good Whales

Look for wallets with:
- Consistent profitability over time
- Reasonable position sizes (not all-in bets)
- Diverse market selection
- Good timing (not just lucky on one event)

## Whale Database

PolyBot tracks whale wallets in the database:

```bash
# View tracked whales
polybot whales list

# Add a whale to track
polybot whales add 0xabc...

# Remove a whale
polybot whales remove 0xabc...

# Show whale performance
polybot whales stats 0xabc...
```

## CLI Commands

```bash
# Enable the strategy
polybot strategy enable copy_trade

# Run in shadow mode to test
polybot strategy shadow copy_trade --enable

# View recent whale activity
polybot whales activity
```

## Best Practices

1. **Diversify whales** - Don't copy just one trader
2. **Verify track record** - Check historical performance
3. **Use small proportions** - Start at 0.5-1%
4. **Monitor actively** - Whales can change strategies
5. **Set position limits** - Don't overexpose to any single whale
