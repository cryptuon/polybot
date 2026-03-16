# Trading Strategies

PolyBot implements 5 automated trading strategies for Polymarket. Each strategy operates independently and can be enabled/disabled via the dashboard or CLI.

## Strategy Overview

| Strategy | Risk Level | Complexity | Capital Requirement |
|----------|------------|------------|---------------------|
| Arbitrage | Low | Low | Medium |
| Statistical Arbitrage | Medium | High | High |
| AI Probability | Medium-High | Very High | Medium |
| Spread Farming | Low-Medium | Medium | Low |
| Copy Trading | Variable | Low | Variable |

---

## 1. Arbitrage Strategy

### Concept

Exploits pricing inefficiencies where YES + NO tokens sum to less than $1. In a binary market, YES and NO must mathematically sum to exactly $1 at resolution. If you can buy both for less than $1, you lock in guaranteed profit.

### How It Works

1. Scanner monitors all active markets every 1-3 seconds
2. Calculates: `total_cost = yes_price + no_price`
3. If `total_cost < (1 - min_profit_pct)`:
   - Buy YES tokens at current ask
   - Buy NO tokens at current ask
   - Guaranteed profit at resolution

### Configuration

```env
ARB_MIN_PROFIT_PCT=0.01        # Minimum 1% profit to trigger
ARB_POLL_INTERVAL_SEC=2        # Check prices every 2 seconds
ARB_MAX_POSITION_USD=500       # Maximum per-trade size
ARB_MARKET_FILTER=crypto       # Focus on specific categories
```

### Edge Cases

- **Slippage**: Large orders may not fill at expected prices
- **Resolution Risk**: Market may resolve before position closes
- **Liquidity**: Both sides need sufficient depth

### Expected Performance

- Win Rate: ~95%+ (when opportunities exist)
- Typical Profit: 0.5-2% per trade
- Trade Frequency: Low (opportunities are rare)

---

## 2. Statistical Arbitrage Strategy

### Concept

Identifies markets with high correlation (e.g., "Will Biden win?" and "Will Democrats win?") and trades the spread when they diverge beyond historical norms.

### How It Works

1. Computes correlation matrix using **price returns** (not raw prices)
2. Monitors spread between correlated pairs in real-time
3. When spread exceeds threshold:
   - **Long leg**: Buy YES token on the cheap market
   - **Short leg**: Buy NO token on the expensive market (Polymarket short proxy)
4. Exit conditions:
   - Spread converges below exit threshold (profit)
   - Spread doubles from entry (stop-loss)
   - Position open > 24 hours (timeout)

### Configuration

```env
STAT_ARB_ENABLED=true
STAT_ARB_MIN_CORRELATION=0.7   # Minimum correlation to track
STAT_ARB_SPREAD_THRESHOLD=0.04 # 4% spread triggers trade
STAT_ARB_LOOKBACK_HOURS=48     # Historical window for correlation
STAT_ARB_EXIT_THRESHOLD=0.01   # Exit when spread < 1%
STAT_ARB_MAX_PAIRS=5           # Maximum concurrent pair trades
```

### Correlation Calculation

Uses Pearson correlation on **price returns** (percentage changes) rather than raw prices to avoid spurious correlations:

```python
# Convert prices to returns
returns_a = [(p[i] - p[i-1]) / p[i-1] for i in range(1, len(prices_a))]
returns_b = [(p[i] - p[i-1]) / p[i-1] for i in range(1, len(prices_b))]

# Compute correlation on returns
correlation = np.corrcoef(returns_a, returns_b)[0, 1]
```

### CLI Commands

```bash
# Show computed correlations
polybot statarb correlations --min-corr 0.7

# Manually compute correlations
polybot statarb compute --hours 48

# Show current opportunities
polybot statarb opportunities --spread 0.04 --min-corr 0.7

# Show price history summary
polybot statarb prices
```

### API Endpoints

```
GET /api/strategies/stat_arb/correlations
GET /api/strategies/stat_arb/pairs/{market_id}
GET /api/strategies/stat_arb/opportunities
GET /api/strategies/stat_arb/price_history?market_a=...&market_b=...
```

### Risk Factors

- **Correlation Breakdown**: Historical correlation may not persist
- **Directional Risk**: Both legs may move against you
- **Timing**: Mean reversion may take longer than expected
- **Liquidity**: Need sufficient depth on both sides

### Expected Performance

- Win Rate: 60-70%
- Typical Profit: 2-5% per pair
- Trade Frequency: Medium

---

## 3. AI Probability Model Strategy

### Concept

Uses machine learning models to estimate the "true" probability of an event, then trades when the market price significantly differs from the model's prediction.

### How It Works

1. Load AI model plugin (configurable)
2. For each market, model predicts probability
3. Calculate edge: `edge = predicted_prob - market_price`
4. If `edge > min_edge` and `confidence > min_confidence`:
   - Buy YES if edge is positive
   - Buy NO if edge is negative

### Built-in Plugins

| Plugin | Description |
|--------|-------------|
| `simple_heuristic` | Rule-based mean reversion (default) |
| `market_price` | Returns market price (baseline) |
| `random_baseline` | Random predictions (testing) |
| `llm` | Claude/OpenAI powered analysis |

### Configuration

```env
AI_MODEL_ENABLED=true
AI_MODEL_PLUGIN=llm               # Plugin name
AI_MODEL_CONFIG={"provider": "anthropic", "api_key": "sk-..."}
AI_MIN_CONFIDENCE=0.7             # Minimum model confidence
AI_MIN_EDGE=0.05                  # Minimum 5% edge to trade
AI_MAX_POSITION_USD=200           # Smaller size due to uncertainty
```

### CLI Commands

```bash
# List available plugins
polybot ai plugins

# Test prediction on a market
polybot ai predict <market-id> --plugin llm

# Scan markets for opportunities
polybot ai scan --plugin simple_heuristic --min-edge 0.05
```

### API Endpoints

```
GET  /api/strategies/ai_model/plugins
GET  /api/strategies/ai_model/plugin/{name}
POST /api/strategies/ai_model/predict/{market_id}
POST /api/strategies/ai_model/batch_predict
```

### Plugin Interface

Models implement the `AIModelPlugin` interface:

```python
class MyModel(AIModelPlugin):
    async def predict(self, context: MarketContext) -> Prediction:
        # Your prediction logic
        return Prediction(
            yes_probability=0.65,
            confidence=0.8,
            reasoning="Based on polling data..."
        )
```

See [AI Plugin Guide](ai-plugin-guide.md) for detailed implementation instructions.

### Risk Factors

- **Model Error**: Predictions may be systematically wrong
- **Overconfidence**: Model confidence may not reflect true uncertainty
- **Data Quality**: Garbage in, garbage out

### Expected Performance

- Win Rate: Highly variable (target: 55%+)
- Typical Profit: Variable
- Trade Frequency: Medium-High

---

## 4. Spread Farming Strategy

### Concept

Market making strategy that places limit orders on both sides of the book to capture the bid-ask spread. Profits from the difference between buying at the bid and selling at the ask.

### How It Works

1. Analyze orderbook depth and spread
2. Place bid slightly above best bid
3. Place ask slightly below best ask
4. When bid fills, place corresponding ask (and vice versa)
5. Manage inventory to avoid directional exposure

### Configuration

```env
SPREAD_FARM_MIN_SPREAD=0.02    # Minimum 2% spread to participate
SPREAD_FARM_MAX_INVENTORY=1000 # Maximum position in any direction
SPREAD_FARM_ORDER_SIZE=50      # Size per order
SPREAD_FARM_PRICE_OFFSET=0.005 # Offset from best bid/ask
```

### Inventory Management

The strategy maintains neutral inventory by:
- Widening quotes when inventory builds up
- Skewing prices to encourage offsetting trades
- Hard limits on maximum directional exposure

### Risk Factors

- **Adverse Selection**: Informed traders may pick off your quotes
- **Inventory Risk**: Prices may move against your position
- **Competition**: Other market makers may squeeze spreads

### Expected Performance

- Win Rate: N/A (continuous P&L)
- Typical Profit: Small per trade, volume-dependent
- Trade Frequency: Very High

---

## 5. Copy Trading Strategy

### Concept

Identifies successful traders ("whales") on Polymarket and mirrors their trades proportionally.

### How It Works

1. Track wallets with high historical returns
2. Monitor their positions via on-chain data
3. When whale opens position:
   - Calculate proportional size based on our capital
   - Execute same trade (with delay)
4. Exit when whale exits

### Configuration

```env
COPY_TRADE_MIN_WHALE_BALANCE=100000  # $100k minimum to track
COPY_TRADE_COPY_PCT=0.1              # Copy 10% of whale's size
COPY_TRADE_MAX_POSITION=500          # Maximum per position
COPY_TRADE_FOLLOW_DELAY_SEC=60       # Wait before copying
COPY_TRADE_WALLETS=0x...,0x...       # Specific wallets to follow
```

### Whale Detection

Whales are identified by:
- Historical PnL > threshold
- Win rate > threshold
- Consistent trading activity
- Large position sizes

### Risk Factors

- **Front-Running**: Others may copy the same whales
- **Changed Behavior**: Past performance doesn't guarantee future results
- **Execution Gap**: Prices may move between whale's trade and ours
- **Exit Timing**: May not detect whale exits promptly

### Expected Performance

- Win Rate: Mirrors whale's performance
- Typical Profit: Variable
- Trade Frequency: Low-Medium

---

## Strategy Interaction

Strategies operate independently but share:
- Rate limiter (prevents API overuse)
- Risk manager (enforces position limits)
- Executor service (handles order submission)

### Position Limits

Global limits apply across all strategies:
- `MAX_POSITION_SIZE_USD`: Per-market limit
- `MAX_TOTAL_EXPOSURE_USD`: Total portfolio limit
- `DAILY_LOSS_LIMIT_USD`: Stop-loss trigger

### Conflict Resolution

When strategies generate conflicting signals:
1. Risk manager evaluates combined exposure
2. Earlier signal has priority (FIFO)
3. Position limits may block later signals

## Backtesting

Each strategy supports backtesting mode:

```bash
# Backtest arbitrage strategy
uv run polybot strategy backtest arbitrage --start 2024-01-01 --end 2024-06-01
```

Note: Backtest results use historical data and may not reflect live performance due to:
- Slippage not modeled
- Liquidity constraints
- Market impact of trades
