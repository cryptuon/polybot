# PolyBot Roadmap

PolyBot is an open-source, agent-driven trading framework for prediction markets. This roadmap describes where the project is heading and — just as importantly — what "production" means for a piece of software like this and the cheapest honest path to get there.

For the market context behind this direction (prediction markets + LLM agents in 2026, and why safety is the hard part), see the "Why this matters in 2026" section of the [README](README.md).

> **No returns are promised or implied anywhere in this document.** "Production" here means *safe, stable, well-supported software* — not profitability. Prediction-market trading carries real financial risk.

## Vision

Make it possible for an LLM agent — supervised by a human — to analyse and trade prediction markets across multiple venues **safely by default**. The agent is a first-class principal with typed tools, hard limits, and mandatory human approval on anything that moves real money. Paper trading is the default; going live is an explicit, reversible, per-strategy decision.

The bet: in 2026, agents *will* operate markets. The valuable and defensible work is not "can the model trade" but "can it trade within limits you set, with an audit trail, and a human in the loop." PolyBot is the framework for that.

## Cheapest path to production

PolyBot is **software — a CLI and Python framework — not a blockchain or a hosted service.** That changes what "production" and "cheapest path" mean entirely. There is no chain to launch, no validators to bootstrap, no token, no cloud bill you're forced to pay. The user runs it.

For PolyBot, **"production" = a stable, published pip package plus safe live-trading capability**, and the cheapest path to it is:

1. **PyPI, not infrastructure.** Ship `polybot-trader` as a versioned wheel on PyPI. Distribution cost is ~zero; the artifact is the product. `pip install polybot-trader` is the entire deployment story for most users.
2. **User-run on cheap hardware.** PolyBot runs anywhere Python runs — a laptop, a $5/month VPS, a Raspberry Pi, or an existing box. There is no server we operate and no per-seat cost. The user owns the compute, the keys, and the data.
3. **Safe live-trading, gated.** "Production" is only reached when a user can promote a proven strategy from shadow to live *safely*. That gate — not a hosting stack — is the real work.

Concretely, production-viability is a checklist of engineering hardening, not spend:

- **Exchange/API hardening + rate limits.** Robust connectors for each venue: ret/backoff, idempotent order submission, reconciliation of partial fills and cancellations, and rate-limit compliance per venue so a live agent never gets throttled or double-submits.
- **Risk limits / circuit-breakers.** Position, exposure, and category caps plus daily-loss limits enforced pre-submission — with hard circuit-breakers that halt a strategy or venue on drawdown, disconnect, or anomalous fills.
- **Secrets management.** Private keys and API credentials kept out of logs, out of the audit trail, and out of agent-visible tool outputs; support for env files, OS keychains, and external secret stores.
- **Backtest → shadow → live parity.** The same code path for simulated fills, paper fills, and live fills, so a strategy that proves out in shadow behaves identically live. No "it worked in backtest" surprises.
- **Docs.** Installation, configuration, safety model, and per-venue setup documented well enough that a user can go from `pip install` to a safe shadow run without reading the source.
- **Versioning.** Semantic versioning, a maintained CHANGELOG, and clear deprecation policy so users can upgrade a live-trading system without fear.

That's the whole cost model: PyPI + docs + hardening. No chain, no hosting, no lock-in.

## Milestones

### Now — 0.1.x (Beta)
- 10 strategies, four venues (Polymarket, Kalshi, Opinion, Binance for hedging).
- Native MCP server with 25+ typed tools; three modes (disabled / shadow / live).
- Paper-trading default, human-in-the-loop approval on live trades, full audit log.
- Position/exposure/loss caps enforced pre-submission.
- `mypy --strict`, test suite, CI, Docker.

### Next — 0.2.x (Hardening for live)
- Exchange/API hardening: idempotent submission, reconciliation, per-venue rate limiting.
- Circuit-breakers on drawdown, disconnect, and anomalous fills.
- Secrets management improvements (keychain / external secret store support).
- Backtest → shadow → live parity harness with fill-model tests.
- Expanded docs: safety model, per-venue setup, agent-operation runbook.

### Later — 0.3.x and toward 1.0 (Stable framework)
- Stable public API surface and semantic-versioning guarantees.
- Additional venues behind `BaseVenue` without touching strategies.
- Richer agent assessment tools (regime detection, portfolio-level risk views).
- 1.0 = documented, versioned, hardened, and safe to run live within user-set limits.

## Non-goals

- **No hosted trading service.** PolyBot stays self-hosted. Your infra, your keys, your data.
- **No return promises.** PolyBot is infrastructure for trading carefully, not a strategy for making money. It will never claim or imply returns.
- **No fully-autonomous, unsupervised live trading by default.** Human-in-the-loop stays the default for anything that moves real money.
- **No MNPI or non-public-data strategies.** Signals must come from public data and be logged for auditability.

## How to influence this roadmap

Open an issue or discussion on [GitHub](https://github.com/cryptuon/polybot), or reach the team at [contact@cryptuon.com](mailto:contact@cryptuon.com). New venue or strategy proposals should include venue fit, data dependencies, and risk/compliance gating before engineering starts.
