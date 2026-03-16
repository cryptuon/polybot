# Comparison with Alternatives

How does PolyBot compare to other prediction market trading tools?

## Feature Comparison

| Feature | PolyBot | Fully-Autonomous AI Bot | OctoBot Prediction | Poly-Maker | Polymarket/agents |
|---------|---------|------------------------|-------------------|------------|-------------------|
| **Strategies** | 10 built-in | AI-only | Copy + Arb | Market Making | AI Agents |
| **Multi-venue** | Polymarket, Kalshi, Binance | Polymarket only | Polymarket only | Polymarket only | Polymarket only |
| **AI Support** | Plugin system (any model) | GPT-4o, Claude, Gemini | Via OctoBot | None | LangChain |
| **Dashboard** | Vue.js web UI | 9-tab terminal | OctoBot UI | Google Sheets | None |
| **Shadow Mode** | Yes | Yes (default) | Yes | No | No |
| **Risk Management** | Position limits, loss limits | 15+ risk checks | Basic | None | None |
| **License** | MIT | MIT | GPL-3.0 | MIT | Apache-2.0 |
| **Language** | Python | Python | Python | Python | TypeScript |

## Detailed Comparisons

### vs. Fully-Autonomous Polymarket AI Trading Bot

[GitHub](https://github.com/dylanpersonguy/Fully-Autonomous-Polymarket-AI-Trading-Bot)

**Their strengths:**

- Multi-model ensemble (GPT-4o, Claude, Gemini)
- Automated research engine
- Comprehensive risk checks
- Fractional Kelly sizing

**PolyBot advantages:**

- **10 strategies** vs AI-only approach
- **Multi-venue** trading (Polymarket, Kalshi, Binance)
- **Modular architecture** - swap components easily
- **Web dashboard** instead of terminal-only
- **Plugin system** for any AI model, not just preset ones

**Best for:** Choose PolyBot if you want strategy variety and multi-venue support. Choose theirs if you want pure AI-driven trading with a terminal interface.

---

### vs. OctoBot Prediction Market

[GitHub](https://github.com/Drakkar-Software/OctoBot-Prediction-Market)

**Their strengths:**

- Built on mature OctoBot ecosystem
- Existing community and plugins
- Multiple backtesting tools

**PolyBot advantages:**

- **Native prediction market design** - not adapted from crypto trading
- **More strategies** - 10 vs 2 (copy + arb)
- **MIT license** - more permissive than GPL-3.0
- **Simpler deployment** - single Python package, no OctoBot dependency
- **Lower resource usage** - lighter weight architecture

**Best for:** Choose PolyBot for a focused prediction market tool. Choose OctoBot if you're already in their ecosystem.

---

### vs. Poly-Maker

[GitHub](https://github.com/warproxxx/poly-maker)

**Their strengths:**

- Simple market making focus
- Google Sheets configuration
- Lightweight

**PolyBot advantages:**

- **Full trading system** - not just market making
- **Professional dashboard** - real-time Vue.js UI
- **Risk management** - position limits, loss controls
- **AI integration** - plugin system for ML models
- **Multi-strategy** - combine market making with other strategies

**Best for:** Choose PolyBot for a complete trading platform. Choose Poly-Maker for simple market making only.

---

### vs. Polymarket/agents

[GitHub](https://github.com/Polymarket/agents)

**Their strengths:**

- Official Polymarket project
- LangChain integration
- Research-focused

**PolyBot advantages:**

- **Production ready** - not just a demo/research project
- **Multiple strategies** - systematic approaches beyond AI
- **Web interface** - full management dashboard
- **Self-hostable** - complete solution vs framework
- **Risk controls** - built-in position management

**Best for:** Choose PolyBot for production trading. Choose Polymarket/agents for research and experimentation.

---

## Why Choose PolyBot?

### For Traders

1. **Test before risking capital** - Shadow mode for paper trading
2. **Manage risk** - Position limits, daily loss limits, exposure caps
3. **Multiple strategies** - Diversify your approach
4. **Real-time monitoring** - Vue.js dashboard with live updates

### For Developers

1. **Clean abstractions** - BaseStrategy, BaseVenue, AIModelPlugin
2. **Type-safe** - Full type hints, Pydantic models, mypy strict
3. **Extensible** - Add strategies, venues, or AI models
4. **Well documented** - Comprehensive guides and API reference

### For Quants

1. **Statistical arbitrage** - Built-in correlation analysis
2. **Custom models** - Plugin system for any ML model
3. **Analytics** - DuckDB for performance analysis
4. **Data export** - Access historical data for backtesting

## Migration Guides

### From Other Tools

If you're migrating from another tool, key differences:

**Configuration:**

- PolyBot uses `.env` files for configuration
- Strategy settings are environment variables
- Database state (enable/disable) managed separately

**Strategy Development:**

- Inherit from `BaseStrategy`
- Implement `scan()` and `should_exit()`
- Register in `STRATEGY_REGISTRY`

**AI Models:**

- Inherit from `AIModelPlugin`
- Implement `initialize()`, `predict()`, `should_update()`
- Configure via `AI_MODEL_PLUGIN` and `AI_MODEL_CONFIG`

## Contributing

Found a bug or want to improve PolyBot? We welcome contributions!

- [GitHub Issues](https://github.com/cryptuon/polybot/issues)
- [Contributing Guide](developer-guide/contributing.md)
- [Discord Community](https://discord.gg/cryptuon)
