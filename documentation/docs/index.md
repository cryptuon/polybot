# PolyBot

**Open-source automated trading system for prediction markets**

Trade smarter on Polymarket, Kalshi, and other prediction markets with 10 battle-tested strategies, real-time analytics, and a plugin system for your own AI models.

## Quick Install

```bash
pip install polybot-trader
polybot db init
polybot start
```

Access the dashboard at [http://localhost:8000/ui](http://localhost:8000/ui)

## Key Features

<div class="grid cards" markdown>

-   :material-strategy:{ .lg .middle } __10 Trading Strategies__

    ---

    From simple arbitrage to AI-powered predictions. Enable strategies with a single command.

    [:octicons-arrow-right-24: View Strategies](user-guide/strategies/index.md)

-   :material-web:{ .lg .middle } __Multi-Venue Trading__

    ---

    Trade on Polymarket, Kalshi, and hedge on Binance - all from one platform.

    [:octicons-arrow-right-24: Venue Guide](user-guide/venues/index.md)

-   :material-brain:{ .lg .middle } __AI Plugin System__

    ---

    Integrate GPT-4, Claude, or your own ML models for probability prediction.

    [:octicons-arrow-right-24: AI Plugins](developer-guide/extending/ai-plugins.md)

-   :material-monitor-dashboard:{ .lg .middle } __Real-time Dashboard__

    ---

    Vue.js web interface with live P&L, positions, and strategy monitoring.

    [:octicons-arrow-right-24: Dashboard Guide](user-guide/dashboard.md)

</div>

## Who is PolyBot For?

### Traders

- Test strategies in **shadow mode** before risking real capital
- Configure **risk controls**: position limits, daily loss limits, exposure caps
- Track **real-time P&L** across all positions
- **Copy successful traders** automatically

### Developers

- Extend with **custom strategies** using clean abstractions
- Build **AI plugins** for probability prediction
- Add **new venues** with the BaseVenue interface
- **Type-safe** codebase with full type hints and Pydantic models

### Quants

- Access **statistical arbitrage** between correlated markets
- Implement **custom models** via the plugin system
- **DuckDB analytics** for performance analysis
- Export data for **backtesting**

## Getting Started

1. **[Install PolyBot](getting-started/installation.md)** - pip, Docker, or from source
2. **[Configure credentials](getting-started/configuration.md)** - Set up your wallet
3. **[Run in shadow mode](getting-started/first-trade.md)** - Test without real trades
4. **[Enable strategies](user-guide/strategies/index.md)** - Start trading

## Architecture Overview

```
                    Vue.js Dashboard
                          |
                          v
        +-----------------------------------+
        |    FastAPI + WebSocket Gateway    |
        +-----------------------------------+
               |         |         |
               v         v         v
        +---------+ +---------+ +---------+
        | Scanner | |Executor | |Analytics|
        +---------+ +---------+ +---------+
                         |
                         v
        +-----------------------------------+
        |        Strategy Services          |
        |   (10 strategies, AI plugins)     |
        +-----------------------------------+
```

[Full architecture documentation](developer-guide/architecture.md)

## Why Choose PolyBot?

| Feature | PolyBot | Typical Alternatives |
|---------|---------|---------------------|
| Strategies | 10 built-in | 1-3 |
| Multi-venue | Polymarket, Kalshi, Binance | Single venue |
| AI integration | Plugin system for any model | Hardcoded or none |
| Dashboard | Vue.js real-time UI | Terminal or none |
| License | MIT | Often GPL or closed |

[Detailed comparison](comparison.md)

## Community

- **GitHub**: [cryptuon/polybot](https://github.com/cryptuon/polybot)
- **Discord**: [Join our server](https://discord.gg/cryptuon)
- **Issues**: [Report bugs](https://github.com/cryptuon/polybot/issues)

## License

PolyBot is open-source software licensed under the [MIT License](https://github.com/cryptuon/polybot/blob/main/LICENSE).

!!! warning "Disclaimer"
    This software is for educational and research purposes. Trading on prediction markets involves financial risk. Use at your own discretion. Not financial advice.
