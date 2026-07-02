<div align="center">

# PolyBot

**Open-source automated trading system for prediction markets**

[![PyPI](https://img.shields.io/pypi/v/polybot-trader?color=blue)](https://pypi.org/project/polybot-trader/)
[![Python](https://img.shields.io/pypi/pyversions/polybot-trader)](https://pypi.org/project/polybot-trader/)
[![CI](https://github.com/cryptuon/polybot/actions/workflows/ci.yml/badge.svg)](https://github.com/cryptuon/polybot/actions)
[![codecov](https://codecov.io/gh/cryptuon/polybot/branch/main/graph/badge.svg)](https://codecov.io/gh/cryptuon/polybot)
[![Docs](https://img.shields.io/badge/docs-cryptuon.com-blue)](https://docs.cryptuon.com/polybot)
[![License](https://img.shields.io/github/license/cryptuon/polybot)](LICENSE)

[Documentation](https://docs.cryptuon.com/polybot) |
[Quick Start](#quick-start) |
[Strategies](#strategies) |
[Discord](https://discord.gg/cryptuon)

**[🌐 Site](https://polybot.cryptuon.com/) · [📚 Docs](https://docs.cryptuon.com/polybot/) · [📦 PyPI package](https://pypi.org/project/polybot-trader/) · [🔬 Cryptuon Research](https://github.com/cryptuon)**

</div>

---

Trade smarter on **Polymarket**, **Kalshi**, and other prediction markets with 10 battle-tested strategies, real-time analytics, and a plugin system for your own AI models.

> **New: AI Agent Integration** - PolyBot now includes an MCP server for AI agents, a Claude Code skill (`/polybot`), and strategy assessment tools. Let AI analyze your strategies and execute trades with full safety controls.

## Why PolyBot?

| Feature | PolyBot | Others |
|---------|---------|--------|
| **Strategies** | 10 built-in | 1-3 typically |
| **Multi-Venue** | Polymarket, Kalshi, Binance | Single venue |
| **AI Integration** | Plugin system for any model | Hardcoded or none |
| **MCP Server** | Full AI agent integration | None |
| **Claude Code Skill** | `/polybot` commands | None |
| **Dashboard** | Vue.js real-time UI | Terminal or none |
| **License** | MIT | Often GPL or closed |

### Built for Traders

- **Shadow Mode**: Test strategies without risking capital
- **Risk Controls**: Position limits, daily loss limits, exposure caps
- **Real-time P&L**: Track performance across all positions
- **Whale Tracking**: Follow successful traders automatically

### Built for Developers

- **Clean Abstractions**: Extend with custom strategies, venues, or AI models
- **Type-Safe**: Full type hints, Pydantic models, mypy strict
- **Well Documented**: Comprehensive guides and API reference
- **Production Ready**: Docker, Prometheus metrics, structured logging

## Quick Start

### Install from PyPI

```bash
pip install polybot-trader
```

### Configure Credentials

```bash
# Copy the environment template
cp .env.example .env

# Edit .env with your Polymarket wallet credentials
# Required: POLYMARKET_PRIVATE_KEY, POLYMARKET_PROXY_ADDRESS
```

### Start Trading (Shadow Mode)

```bash
# Initialize databases
polybot db init

# Enable a strategy in shadow mode (no real trades)
polybot strategy enable arbitrage
polybot strategy shadow arbitrage --enable

# Start all services
polybot start
```

Access the dashboard at **http://localhost:8000/ui**

### Docker Deployment

```bash
docker compose up -d
```

## Strategies

PolyBot includes 10 trading strategies for prediction markets:

| Strategy | Description | Risk Level |
|----------|-------------|------------|
| **Arbitrage** | Buy YES + NO when combined price < $1 | Low |
| **Statistical Arbitrage** | Trade correlated markets that diverge | Medium |
| **AI Model** | ML/LLM-predicted probability mispricing | Medium |
| **Spread Farming** | Provide liquidity, capture bid-ask spread | Low |
| **Copy Trading** | Mirror successful whale traders | Medium |
| **Resolution Arb** | Near-expiry mispricing opportunities | Low |
| **Calendar Spread** | Time-based price discrepancies | Medium |
| **Momentum** | Trend-following on price movements | High |
| **Poll Divergence** | Trade when polls diverge from prices | Medium |
| **Volume Spike** | React to unusual volume patterns | High |

[Full strategy documentation](https://docs.cryptuon.com/polybot/user-guide/strategies/)

## Extending PolyBot

PolyBot is designed for extensibility. Add your own strategies, venues, or AI models.

### Custom Strategy

```python
from polybot.strategies.base import BaseStrategy, StrategyConfig
from polybot.models.messages import PriceUpdate, Signal, SignalAction

class MyStrategy(BaseStrategy):
    name = "my_strategy"
    description = "My custom trading strategy"
    
    def _get_config(self) -> StrategyConfig:
        return StrategyConfig(max_position_size=100.0)
    
    async def scan(self, update: PriceUpdate) -> list[Signal]:
        # Your alpha logic here
        if self._found_opportunity(update):
            return [Signal(
                strategy=self.name,
                market_id=update.market_id,
                token_id=update.token_id,
                action=SignalAction.BUY_YES,
                price=update.ask,
                size=50.0,
                reason="Custom signal",
            )]
        return []
    
    async def should_exit(self, position, update) -> bool:
        # Exit logic
        return position.unrealized_pnl_pct > 0.10
```

### AI Model Plugin

```python
from polybot.plugins.base import AIModelPlugin, MarketContext, Prediction

class MyAIPlugin(AIModelPlugin):
    name = "my_ai"
    version = "1.0.0"
    
    async def initialize(self, config: dict) -> None:
        self.model = load_my_model(config["model_path"])
    
    async def predict(self, context: MarketContext) -> Prediction:
        prob = self.model.predict(context.question)
        return Prediction(
            yes_probability=prob,
            confidence=0.8,
            reasoning="Model analysis"
        )
    
    async def should_update(self) -> bool:
        return False
```

[Developer Guide](https://docs.cryptuon.com/polybot/developer-guide/)

## AI Agent Integration

PolyBot includes comprehensive AI agent integration via MCP (Model Context Protocol):

- **MCP Server** for AI agents (Claude, etc.) to interact with trading
- **Strategy Assessment** for AI to analyze and improve strategies
- **Claude Code Skill** for direct CLI interaction

### Quick Start

```bash
# Enable MCP server
export MCP_ENABLED=true
export MCP_AI_TRADING_MODE=shadow  # Start with paper trading

# Start MCP server
polybot mcp start
```

### Claude Code Skill

Install the skill for direct CLI access in Claude Code:

```bash
cp -r .claude/skills ~/.claude/skills/
```

Then use `/polybot` in Claude Code:
```
/polybot strategy list
/polybot mcp status
```

### AI Capabilities

| Feature | Description |
|---------|-------------|
| **Market Analysis** | Query markets, prices, positions |
| **Shadow Trading** | Paper trade without real money |
| **Live Trading** | Real orders with approval workflow |
| **Strategy Assessment** | Analyze performance, suggest improvements |
| **CLI Execution** | Run polybot commands programmatically |

### Trading Modes

| Mode | Description |
|------|-------------|
| `disabled` | AI can only read market data |
| `shadow` | AI can paper trade (no real money) |
| `live` | AI can submit real orders (with approval) |

### Safety Controls

- **Position Limits**: AI trades limited to `MCP_MAX_POSITION_USD`
- **Daily Loss Limit**: Auto-disable if `MCP_DAILY_LOSS_LIMIT_USD` exceeded
- **Approval Queue**: Live trades require human approval by default
- **Audit Logging**: All AI actions logged for review
- **CLI Whitelist**: Only safe commands allowed via MCP

[AI Integration Guide](https://docs.cryptuon.com/polybot/user-guide/ai-agents/)

## Architecture

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
        | Service | | Service | | Service |
        +---------+ +---------+ +---------+
               |         |         |
               +---------+---------+
                         |
                         v
        +-----------------------------------+
        |        Strategy Services          |
        |   (10 strategies, AI plugins)     |
        +-----------------------------------+
```

Services communicate via NNG (nanomsg-next-gen) for high-performance internal messaging.

## CLI Reference

```bash
# Service management
polybot start              # Start all services
polybot api                # Run API server only
polybot scanner            # Run scanner only
polybot executor           # Run executor only

# Strategy management
polybot strategy list              # List all strategies
polybot strategy enable <name>     # Enable a strategy
polybot strategy disable <name>    # Disable a strategy
polybot strategy shadow <name>     # Toggle shadow mode
polybot strategy run <name>        # Run single strategy

# AI model tools
polybot ai plugins                 # List AI plugins
polybot ai predict <market_id>     # Test prediction
polybot ai scan                    # Scan for opportunities

# MCP (AI Agent) management
polybot mcp start                  # Start MCP server
polybot mcp status                 # Show status and pending approvals
polybot mcp mode <mode>            # Set AI trading mode
polybot mcp pending                # List pending approvals
polybot mcp approve <id>           # Approve AI trade
polybot mcp reject <id>            # Reject AI trade
polybot mcp audit                  # View AI action audit log

# Database
polybot db init            # Initialize databases
polybot db stats           # Show performance stats

# Configuration
polybot config             # Show current config
polybot auth               # Manage API credentials
```

## Documentation

- [Installation Guide](https://docs.cryptuon.com/polybot/getting-started/installation/)
- [Configuration Reference](https://docs.cryptuon.com/polybot/getting-started/configuration/)
- [Strategy Deep Dives](https://docs.cryptuon.com/polybot/user-guide/strategies/)
- [Building Custom Strategies](https://docs.cryptuon.com/polybot/developer-guide/extending/custom-strategy/)
- [AI Plugin Development](https://docs.cryptuon.com/polybot/developer-guide/extending/ai-plugins/)
- [Docker Deployment](https://docs.cryptuon.com/polybot/deployment/docker/)
- [API Reference](https://docs.cryptuon.com/polybot/developer-guide/api-reference/)

## Comparison with Alternatives

| Feature | PolyBot | Fully-Autonomous AI Bot | OctoBot Prediction | Poly-Maker |
|---------|---------|-------------------------|-------------------|------------|
| Strategies | 10 built-in | AI-only | Copy + Arb | Market Making |
| Multi-venue | Yes (3 venues) | No | No | No |
| Dashboard | Vue.js real-time | Terminal only | OctoBot UI | Google Sheets |
| AI plugins | Any model | GPT-4/Claude/Gemini | Via OctoBot | None |
| **MCP Server** | **Yes - Full integration** | No | No | No |
| **Claude Code Skill** | **Yes - /polybot** | No | No | No |
| **CLI Tools** | **50+ commands** | Limited | Via OctoBot | Basic |
| **AI Trading Modes** | **3 (disabled/shadow/live)** | Live only | N/A | N/A |
| **Approval Workflow** | **Yes - Human-in-loop** | No | No | No |
| **Audit Logging** | **Full AI action logs** | Basic | Basic | None |
| Shadow Mode | Yes | No | Yes | No |
| License | MIT | MIT | GPL-3.0 | MIT |

### Why PolyBot for AI-Assisted Trading?

PolyBot is the only prediction market trading system with **native AI agent support**:

- **MCP Server**: AI agents (Claude, GPT, etc.) can query markets, analyze strategies, and execute trades via the Model Context Protocol
- **Claude Code Skill**: Run `polybot` commands directly in Claude Code with `/polybot strategy list`
- **Strategy Assessment**: AI can analyze your strategy performance and suggest code improvements
- **Safety First**: Three trading modes (disabled/shadow/live), approval workflows, position limits, and full audit logging
- **50+ CLI Commands**: Complete system control from the command line, all accessible to AI agents

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

```bash
# Development setup
git clone https://github.com/cryptuon/polybot
cd polybot
uv sync --dev
uv run pytest

# Run linting
uv run ruff check src/ tests/
uv run mypy src/polybot/
```

## License

MIT License - see [LICENSE](LICENSE) for details.

## Disclaimer

This software is for educational and research purposes. Trading on prediction markets involves financial risk. Use at your own discretion. Not financial advice.

---

<div align="center">
  <sub>Built with care by <a href="https://www.cryptuon.com">Cryptuon</a></sub>
</div>

---

## Part of Cryptuon Research

`polybot` is one of [20 open-source blockchain-infrastructure projects](https://www.cryptuon.com/projects) from **[Cryptuon Research](https://www.cryptuon.com)** — blockchain theory, shipped as protocols.

**Related projects:** [dgbit](https://dgbit.cryptuon.com/) · [Mentat](https://mentat.cryptuon.com/) · [Moby Market](https://mobymarket.cryptuon.com/)

Docs: [docs.cryptuon.com/polybot](https://docs.cryptuon.com/polybot/) · Contact: [contact@cryptuon.com](mailto:contact@cryptuon.com)
