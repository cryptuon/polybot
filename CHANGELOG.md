# Changelog

All notable changes to PolyBot will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial public release
- 10 trading strategies: Arbitrage, Statistical Arbitrage, AI Model, Spread Farming, Copy Trading, Resolution Arb, Calendar Spread, Momentum, Poll Divergence, Volume Spike
- Multi-venue support: Polymarket, Kalshi, Binance (for hedging)
- AI plugin system for custom prediction models
- Vue.js dashboard with real-time updates
- Shadow mode for paper trading
- Risk management: position limits, daily loss limits, exposure caps
- CLI for strategy and service management
- Docker and Docker Compose support
- Prometheus metrics and Grafana dashboards
- MkDocs documentation

## [0.1.0] - 2026-04-15

### Added
- Initial release of PolyBot trading system
- Core trading infrastructure with NNG messaging
- FastAPI REST API and WebSocket gateway
- SQLite for operational data, DuckDB for analytics
- Comprehensive test suite
- CI/CD with GitHub Actions

[Unreleased]: https://github.com/cryptuon/polybot/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/cryptuon/polybot/releases/tag/v0.1.0
