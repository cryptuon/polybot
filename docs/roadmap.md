# Roadmap Alignment

This document aligns our near-term strategy roadmap with the prediction market
landscape and the specific projects referenced: Polymarket, Kalshi, and Opinion.
It is a working plan for product scope, data needs, and risk guardrails.

## Market Landscape (external references)

### Polymarket
- Positioning: "world's largest prediction market" with broad event coverage.
- Market model: crypto-based prediction market using USDC on Polygon.
- Takeaway: high-liquidity event markets with crypto rails, best suited for fast
  signal ingestion, low-latency execution, and market-making where spreads exist.

### Kalshi
- Positioning: CFTC-regulated exchange and prediction market for event contracts.
- Takeaway: a regulated, US-facing venue with compliance-sensitive access and
  a more formal listing process. This favors conservative risk controls, slower
  iterations, and additional legal/compliance review for new strategies.

### Opinion
- Positioning: listed as a prediction market protocol with DEX volume metrics.
- The project is categorized as a prediction market and provides an app surface.
- Takeaway: DEX-style execution model with volume enough to justify routing,
  but likely different mechanics (fees, liquidity, chain risk) than Polymarket.

## Strategy Alignment

### 15-min crypto options market-making
- Scope: quote options (likely on CEX venues such as Binance) on a 15-minute
  cadence with systematic inventory management.
- Why it fits: provides hedging and cross-venue pricing signals that can
  sharpen prediction market quotes for crypto-related events.
- Requirements:
  - Options order book connector and greeks/vol surface ingestion.
  - Inventory and delta hedging loop synced to the 15-minute cadence.
  - Cross-venue pricing signals to avoid stale quotes.

### Arbitrage with Binance
- Scope: exploit pricing gaps between prediction market event prices and
  related Binance spot/perp/option markets.
- Why it fits: crypto event markets often map to underlying price or volatility.
- Requirements:
  - Robust mapping between event definitions and underlying instruments.
  - Latency-aware execution and pre-trade risk checks.
  - Funding/transfer constraints and fees modeled explicitly.

### Insider-identifying directional bets (reframed)
- Scope: directional bets driven by information advantage from public sources
  and market microstructure signals.
- Guardrail: no material non-public information (MNPI). Signals must be from
  public data and logged for auditability.
- Requirements:
  - News and social ingestion with provenance tracking.
  - Signal-to-trade pipeline with explicit compliance gating.
  - Post-trade attribution and drift monitoring.

### Mid-frequency copy trading
- Scope: track top wallets/traders and replicate at a mid-frequency cadence.
- Why it fits: already present in the system and aligns with Polymarket flows.
- Requirements:
  - Wallet ranking and risk-adjusted weighting.
  - Slippage-aware execution and time-decay replication.
  - Safeguards for herding and spoofed activity.

### To be continued
- New strategies must include venue fit, data dependencies, and compliance
  gating before engineering effort starts.

## Draft Roadmap Phases

### Phase 0: Baseline alignment (0-4 weeks)
- Document market-specific constraints (Polymarket, Kalshi, Opinion).
- Define compliance policy for directional bets (public-only signals).
- Add data dictionaries for market mappings and event taxonomy.

### Phase 1: Cross-venue infrastructure (1-3 months)
- Build Binance connectors for spot/perp/options (pricing and execution).
- Add unified risk layer for multi-venue exposure and hedging.
- Implement event-to-underlying mapping for arbitrage logic.

### Phase 2: Strategy hardening (3-6 months)
- Productionize 15-min options market-making with hedging.
- Expand copy trading with quality filters and latency controls.
- Add Opinion routing with chain-risk and fee modeling.

### Phase 3: Scale and optimization (6-12 months)
- Dynamic capital allocation across strategies and venues.
- Portfolio-level risk controls (correlation, tail exposure, regime shifts).
- Continuous evaluation of new venue integrations.

## Risks and Guardrails
- Regulatory exposure: Kalshi requires additional compliance review.
- Market integrity: exclude MNPI, log sources, and maintain audit trails.
- Liquidity and slippage: enforce per-market depth checks and max spread rules.
- Chain/venue risk: handle settlement delays, chain congestion, and outages.

## Open Questions
- Which venues are in scope for options market-making beyond Binance?
- What geographies and entity structures are permitted for each venue?
- Preferred order types and rate limits per venue?
- What thresholds define "public signal" vs prohibited information?

## Sources
- Polymarket homepage: https://polymarket.com
- Polymarket summary: https://en.wikipedia.org/api/rest_v1/page/summary/Polymarket
- Kalshi about page: https://kalshi.com/about
- Kalshi summary: https://en.wikipedia.org/api/rest_v1/page/summary/Kalshi
- Opinion metrics and category: https://defillama.com/protocol/opinion
