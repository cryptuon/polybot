<div align="center">

# PolyBot

**Open-source, agent-driven trading framework for prediction markets**

[![PyPI](https://img.shields.io/pypi/v/polybot-trader?color=blue)](https://pypi.org/project/polybot-trader/)
[![Python](https://img.shields.io/pypi/pyversions/polybot-trader)](https://pypi.org/project/polybot-trader/)
[![CI](https://github.com/cryptuon/polybot/actions/workflows/ci.yml/badge.svg)](https://github.com/cryptuon/polybot/actions)
[![codecov](https://codecov.io/gh/cryptuon/polybot/branch/main/graph/badge.svg)](https://codecov.io/gh/cryptuon/polybot)
[![Docs](https://img.shields.io/badge/docs-cryptuon.com-blue)](https://docs.cryptuon.com/polybot)
[![License](https://img.shields.io/github/license/cryptuon/polybot)](LICENSE)

[Documentation](https://docs.cryptuon.com/polybot) |
[Quick Start](#quick-start) |
[Strategies](#strategies) |
[Roadmap](ROADMAP.md) |
[Discord](https://discord.gg/cryptuon)

**[🌐 Site](https://polybot.cryptuon.com/) · [📚 Docs](https://docs.cryptuon.com/polybot/) · [📦 PyPI package](https://pypi.org/project/polybot-trader/) · [🔬 Cryptuon Research](https://github.com/cryptuon)**

</div>

---

PolyBot is an **agent-driven trading framework for prediction markets**. It gives LLM agents — and the humans supervising them — a typed, safe-by-default surface for analysing and trading event contracts across **Polymarket**, **Kalshi**, **Opinion**, and **Binance** (for hedging). Agents drive the system through a native **MCP server** that exposes **25+ typed tools**; every strategy runs in **paper (shadow) mode by default**, and any live order is **human-in-the-loop approval-gated** and audit-logged.

It is a Python CLI and framework — MIT-licensed, self-hosted, your keys and your data. Not a hosted service, not a signals newsletter, and not financial advice.

> **AI Agent Integration** — PolyBot ships an MCP server for AI agents, a Claude Code skill (`/polybot`), and strategy-assessment tools. An agent can analyse markets and *propose* trades; a human approves them. Read-only and paper modes need no approval; live trading does.

## Why this matters in 2026

Two curves are crossing. Prediction markets went from a niche to one of the most-watched market structures anywhere — election, macro, and event contracts now clear real volume across Polymarket, Kalshi, and a growing set of on-chain venues. At the same time, LLM agents crossed the threshold where they can genuinely reason over market microstructure, read news, and hold a thesis.

The obvious next step — *let an agent trade these markets* — is also the dangerous one. An agent with an API key and no guardrails is a liability, not a product. PolyBot exists for the safe version of that idea: agents as **first-class principals with typed tools, hard risk limits, and mandatory human approval on anything that moves real money.** The default is paper trading. Going live is an explicit, per-strategy decision, and even then an agent proposes while a human disposes.

If you believe agents will operate markets in 2026, the interesting engineering problem is not "can the model trade" — it's "can it trade *safely, auditably, and within limits you set*." That is the problem PolyBot is built around. See [ROADMAP.md](ROADMAP.md) for where it goes next.

**No returns are promised or implied.** Prediction-market trading carries financial risk; PolyBot is infrastructure for doing it carefully, not a strategy for making money.

## Why PolyBot?

Most people building an agent for prediction markets end up hand-writing a bespoke bot per venue — a Polymarket script, a Kalshi script, a fragile LLM prompt, and risk checks copy-pasted into each. PolyBot replaces that with one typed framework.

| Approach | Bespoke bots per venue | PolyBot |
|----------|------------------------|---------|
| **Venues** | One integration per script | Polymarket, Kalshi, Opinion, Binance behind one `BaseVenue` |
| **Domain model** | Re-derive markets/orders/positions each time | Shared Pydantic types across every venue and strategy |
| **Risk** | Bolted onto each script, drifts out of sync | Position/exposure/loss caps enforced in the platform, pre-submission |
| **Agent access** | Custom prompt glue, no guardrails | Native MCP server, 25+ typed tools, approval-gated |
| **Safety default** | Usually live from day one | Paper (shadow) mode by default |
| **Audit** | Ad hoc logging, if any | Every signal, order, and tool call logged |
| **License** | Varies | MIT |

*Honest tradeoff:* a bespoke bot for a single venue can be simpler and lower-dependency if you only ever trade that one venue and never involve an agent. PolyBot earns its weight when you want multiple venues, agent access, or shared risk — not before.

### Built for agent-driven trading

- **Agent-native**: an MCP server exposes 25+ typed tools so Claude, GPT, or any MCP client can analyse markets and place approval-gated trades.
- **Human-in-the-loop**: live trades require explicit human approval — agents never fill blindly.
- **Shadow Mode**: every strategy paper-trades by default; promote to live per-strategy, reversibly.
- **Risk Controls**: position limits, daily loss limits, exposure caps — enforced platform-wide, before submission.

### Built for developers

- **Clean Abstractions**: extend with custom strategies, venues, or AI models.
- **Type-Safe**: full type hints, Pydantic models, `mypy --strict`.
- **Well Documented**: comprehensive guides and API reference.
- **Self-hosted**: Docker, Prometheus metrics, structured logging — your infra, your keys.

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

Shadow (paper) mode is the default. No real orders are placed until you explicitly promote a strategy to live.

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

Risk levels describe strategy mechanics, not expected returns — every strategy can lose money.

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

PolyBot treats AI agents as first-class principals via MCP (Model Context Protocol):

- **MCP Server** for AI agents (Claude, etc.) to interact with trading
- **Strategy Assessment** for AI to analyze and improve strategies
- **Claude Code Skill** for direct CLI interaction

### Quick Start

```bash
# Enable MCP server
export MCP_ENABLED=true
export MCP_AI_TRADING_MODE=shadow  # Start with paper trading (this is the default)

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
| **Live Trading** | Real orders with human approval workflow |
| **Strategy Assessment** | Analyze performance, suggest improvements |
| **CLI Execution** | Run whitelisted polybot commands programmatically |

### Trading Modes

The default mode is `shadow`. An agent cannot move real money until you explicitly switch to `live`, and even then each trade is approval-gated.

| Mode | Description |
|------|-------------|
| `disabled` | AI can only read market data |
| `shadow` | AI can paper trade (no real money) — **default** |
| `live` | AI can submit real orders (human approval required) |

### Safety Controls

- **Paper-trading default**: agents start in `shadow`; live trading is opt-in, per-strategy.
- **Human-in-the-loop**: live trades require human approval by default (`MCP_REQUIRE_APPROVAL`).
- **Position Limits**: AI trades limited to `MCP_MAX_POSITION_USD`.
- **Daily Loss Limit**: auto-disable if `MCP_DAILY_LOSS_LIMIT_USD` exceeded.
- **Approval Queue**: pending live trades wait for a human at the CLI.
- **Audit Logging**: all AI actions logged for review.
- **CLI Whitelist**: only safe commands allowed via MCP.

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
- [Roadmap](ROADMAP.md)

## Comparison with Alternatives

The honest baseline for most teams isn't another framework — it's writing a bespoke bot per venue. PolyBot compares against that and the closest existing tools:

| Feature | PolyBot | Bespoke bots per venue | OctoBot Prediction | Poly-Maker |
|---------|---------|------------------------|-------------------|------------|
| Strategies | 10 built-in | Whatever you write | Copy + Arb | Market Making |
| Multi-venue | Yes (Polymarket, Kalshi, Opinion, Binance) | One per bot | No | No |
| Domain model | Shared, typed | Re-derived per bot | Via OctoBot | Ad hoc |
| AI plugins | Any model, typed | DIY prompt glue | Via OctoBot | None |
| **MCP Server** | **Yes — 25+ typed tools** | No | No | No |
| **Claude Code Skill** | **Yes — /polybot** | No | No | No |
| **AI Trading Modes** | **3 (disabled/shadow/live)** | DIY | N/A | N/A |
| **Approval Workflow** | **Yes — human-in-the-loop** | DIY | No | No |
| **Audit Logging** | **Full AI action logs** | DIY | Basic | None |
| Paper-trading default | Yes | Rarely | Yes | No |
| License | MIT | Yours | GPL-3.0 | MIT |

*When a bespoke bot wins:* single venue, no agent, minimal dependencies. *When PolyBot wins:* multiple venues, agent access, or a shared risk model you want enforced once rather than re-implemented per script.

### Why PolyBot for agent-driven trading

PolyBot is built to let AI agents operate prediction markets **safely**:

- **MCP Server**: agents (Claude, GPT, etc.) query markets, analyse strategies, and propose trades via the Model Context Protocol — as typed tools, not prompts.
- **Claude Code Skill**: run `polybot` commands directly in Claude Code with `/polybot strategy list`.
- **Strategy Assessment**: an agent can analyse strategy performance and suggest code improvements.
- **Safety First**: paper-trading default, three trading modes, human approval on live trades, position limits, and full audit logging.

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

This software is for educational and research purposes. Trading on prediction markets involves financial risk. PolyBot makes no representation or warranty about returns. Use at your own discretion. Not financial advice.

---

<div align="center">
  <sub>Built with care by <a href="https://www.cryptuon.com">Cryptuon</a></sub>
</div>

---

## Part of Cryptuon Research

`polybot` is one of [20 open-source blockchain-infrastructure projects](https://www.cryptuon.com/projects) from **[Cryptuon Research](https://www.cryptuon.com)** — blockchain theory, shipped as protocols.

**Related projects:** [dgbit](https://dgbit.cryptuon.com/) · [Mentat](https://mentat.cryptuon.com/) · [Moby Market](https://mobymarket.cryptuon.com/)

Docs: [docs.cryptuon.com/polybot](https://docs.cryptuon.com/polybot/) · Contact: [contact@cryptuon.com](mailto:contact@cryptuon.com)
