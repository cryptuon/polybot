# Contributing to PolyBot

Thank you for your interest in contributing to PolyBot! This document provides guidelines and information for contributors.

## Getting Started

### Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/cryptuon/polybot
   cd polybot
   ```

2. **Install dependencies**
   ```bash
   # Install Python dependencies with uv (recommended)
   uv sync --dev

   # Or with pip
   pip install -e ".[dev]"
   ```

3. **Install frontend dependencies**
   ```bash
   cd frontend
   npm install
   cd ..
   ```

4. **Set up pre-commit hooks** (optional but recommended)
   ```bash
   uv run pre-commit install
   ```

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src/polybot --cov-report=html

# Run specific test file
uv run pytest tests/unit/test_strategies.py -v
```

### Code Quality

```bash
# Linting
uv run ruff check src/ tests/

# Format check
uv run ruff format --check src/ tests/

# Type checking
uv run mypy src/polybot/
```

## How to Contribute

### Reporting Bugs

1. **Check existing issues** - Search [GitHub Issues](https://github.com/cryptuon/polybot/issues) first
2. **Create a new issue** with:
   - Clear title and description
   - Steps to reproduce
   - Expected vs actual behavior
   - Environment details (OS, Python version, etc.)

### Suggesting Features

1. **Check the roadmap** - Feature might already be planned
2. **Open a discussion** - For major features, discuss first
3. **Create an issue** with:
   - Use case description
   - Proposed solution
   - Alternatives considered

### Pull Requests

1. **Fork the repository**
2. **Create a feature branch**
   ```bash
   git checkout -b feature/my-feature
   ```
3. **Make your changes**
   - Write tests for new functionality
   - Update documentation if needed
   - Follow code style guidelines
4. **Run tests and linting**
   ```bash
   uv run pytest
   uv run ruff check src/ tests/
   uv run mypy src/polybot/
   ```
5. **Commit with clear messages**
   ```bash
   git commit -m "Add feature: brief description"
   ```
6. **Push and create PR**
   ```bash
   git push origin feature/my-feature
   ```

### PR Guidelines

- **One feature per PR** - Keep PRs focused
- **Write tests** - Cover new functionality
- **Update docs** - If behavior changes
- **Follow style** - Match existing code patterns
- **Add changelog entry** - For user-facing changes

## Code Style

### Python

- **Type hints** - Required for all functions
- **Docstrings** - Google style for public APIs
- **Line length** - 100 characters max
- **Imports** - Sorted with ruff

Example:
```python
async def process_signal(
    signal: Signal,
    executor: ExecutorService,
    *,
    validate: bool = True,
) -> OrderResult:
    """Process a trading signal.

    Args:
        signal: The trading signal to process.
        executor: Executor service instance.
        validate: Whether to validate before execution.

    Returns:
        Result of the order execution.

    Raises:
        ValidationError: If signal validation fails.
    """
    if validate:
        await signal.validate()
    return await executor.execute(signal)
```

### TypeScript/Vue

- **ESLint** - Follow Vue.js style guide
- **Components** - Single file components
- **Composition API** - Preferred over Options API

## Project Structure

```
polybot/
├── src/polybot/           # Main Python package
│   ├── api/               # FastAPI routes
│   ├── core/              # Core utilities
│   ├── db/                # Database stores
│   ├── models/            # Pydantic models
│   ├── plugins/           # AI plugins
│   ├── services/          # Background services
│   ├── strategies/        # Trading strategies
│   └── venues/            # Venue integrations
├── frontend/              # Vue.js dashboard
├── tests/                 # Test suite
├── documentation/         # MkDocs documentation
└── deploy/                # Deployment configs
```

## Adding a New Strategy

1. Create `src/polybot/strategies/my_strategy.py`
2. Inherit from `BaseStrategy`
3. Implement `scan()` and `should_exit()`
4. Register in `strategies/__init__.py`
5. Add tests in `tests/strategies/test_my_strategy.py`
6. Document in `documentation/docs/user-guide/strategies/`

See [Custom Strategy Guide](https://docs.cryptuon.com/polybot/developer-guide/extending/custom-strategy/) for details.

## Adding an AI Plugin

1. Create `src/polybot/plugins/my_plugin.py`
2. Inherit from `AIModelPlugin`
3. Implement required methods
4. Register in plugin discovery
5. Add tests and documentation

See [AI Plugin Guide](https://docs.cryptuon.com/polybot/developer-guide/extending/ai-plugins/) for details.

## Questions?

- **Discord**: [Join our server](https://discord.gg/cryptuon)
- **Discussions**: [GitHub Discussions](https://github.com/cryptuon/polybot/discussions)
- **Email**: team@cryptuon.com

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
