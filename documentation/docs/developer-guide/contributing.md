# Contributing

Thank you for your interest in contributing to PolyBot!

## Getting Started

### Development Setup

```bash
# Clone the repository
git clone https://github.com/cryptuon/polybot
cd polybot

# Install dependencies
uv sync --dev

# Install frontend dependencies
cd frontend && npm install && cd ..

# Run tests
uv run pytest
```

### Code Quality

```bash
# Linting
uv run ruff check src/ tests/

# Format
uv run ruff format src/ tests/

# Type checking
uv run mypy src/polybot/
```

## How to Contribute

### Reporting Bugs

1. Search [existing issues](https://github.com/cryptuon/polybot/issues)
2. Create a new issue with:
   - Clear description
   - Steps to reproduce
   - Expected vs actual behavior
   - Environment details

### Suggesting Features

1. Check the [roadmap](https://github.com/cryptuon/polybot/blob/main/docs/roadmap.md)
2. Open a discussion for major features
3. Create an issue with use case and proposed solution

### Pull Requests

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make changes with tests
4. Run checks: `uv run pytest && uv run ruff check`
5. Commit: `git commit -m "Add feature: description"`
6. Push: `git push origin feature/my-feature`
7. Open a pull request

## Code Guidelines

### Python Style

- Type hints required
- Google-style docstrings
- 100 character line limit
- Use `ruff` for formatting

```python
async def process_signal(
    signal: Signal,
    executor: ExecutorService,
    *,
    validate: bool = True,
) -> OrderResult:
    """Process a trading signal.

    Args:
        signal: The trading signal.
        executor: Executor service instance.
        validate: Whether to validate first.

    Returns:
        Result of order execution.
    """
    ...
```

### Testing

- Write tests for new features
- Maintain >80% coverage
- Use pytest fixtures
- Test edge cases

```python
@pytest.fixture
def strategy():
    return ArbitrageStrategy()

async def test_scan_finds_opportunity(strategy, price_update):
    signals = await strategy.scan(price_update)
    assert len(signals) == 1
```

### Commits

- Clear, concise messages
- Reference issues: `Fixes #123`
- One logical change per commit

## Project Structure

```
polybot/
├── src/polybot/        # Main package
│   ├── api/            # FastAPI routes
│   ├── core/           # Core utilities
│   ├── db/             # Database stores
│   ├── models/         # Pydantic models
│   ├── plugins/        # AI plugins
│   ├── services/       # Background services
│   ├── strategies/     # Trading strategies
│   └── venues/         # Venue integrations
├── frontend/           # Vue.js dashboard
├── tests/              # Test suite
├── documentation/      # MkDocs
└── deploy/             # Deployment configs
```

## Adding Features

### New Strategy

1. Create `src/polybot/strategies/my_strategy.py`
2. Inherit from `BaseStrategy`
3. Register in `strategies/__init__.py`
4. Add tests
5. Add documentation

### New AI Plugin

1. Create `src/polybot/plugins/my_plugin.py`
2. Inherit from `AIModelPlugin`
3. Register in plugin discovery
4. Add tests and docs

### New Venue

1. Create `src/polybot/venues/my_venue.py`
2. Inherit from `BaseVenue`
3. Add configuration
4. Register and test

## Community

- [Discord](https://discord.gg/cryptuon)
- [GitHub Discussions](https://github.com/cryptuon/polybot/discussions)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
