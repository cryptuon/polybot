# Installation

This guide covers all methods to install PolyBot.

## Requirements

- **Python**: 3.11 or higher
- **OS**: Linux, macOS, or Windows (WSL recommended)
- **Memory**: 2GB RAM minimum
- **Disk**: 500MB for installation + data

## PyPI Installation (Recommended)

The simplest way to install PolyBot:

```bash
pip install polybot-trader
```

Or with [uv](https://github.com/astral-sh/uv) (faster):

```bash
uv pip install polybot-trader
```

### Verify Installation

```bash
polybot --version
polybot --help
```

## Docker Installation

Docker is ideal for production deployments.

### Quick Start

```bash
# Clone the repository
git clone https://github.com/cryptuon/polybot
cd polybot

# Copy environment template
cp .env.example .env
# Edit .env with your credentials

# Start all services
docker compose up -d
```

### Services

The Docker Compose setup includes:

| Service | Port | Description |
|---------|------|-------------|
| `polybot` | 8000 | Main application |
| `prometheus` | 9090 | Metrics (optional) |
| `grafana` | 3000 | Dashboards (optional) |

Enable monitoring with:
```bash
docker compose --profile monitoring up -d
```

### Persistent Data

Data is stored in Docker volumes:
- `polybot-data`: SQLite and DuckDB databases
- `polybot-logs`: Application logs

## From Source

For development or customization:

```bash
# Clone repository
git clone https://github.com/cryptuon/polybot
cd polybot

# Install with uv (recommended)
uv sync

# Or with pip
pip install -e ".[dev]"
```

### Running from Source

```bash
# With uv
uv run polybot --help

# Or directly
python -m polybot --help
```

### Building the Frontend

The Vue.js dashboard requires Node.js:

```bash
cd frontend
npm install
npm run dev     # Development server
npm run build   # Production build
```

## Platform-Specific Notes

### macOS

Install Python via Homebrew:
```bash
brew install python@3.11
```

### Ubuntu/Debian

```bash
sudo apt update
sudo apt install python3.11 python3.11-venv
```

### Windows

We recommend using WSL2 for the best experience:

1. Install WSL2 with Ubuntu
2. Follow Linux installation steps

Native Windows is supported but may have limitations with NNG sockets.

## Post-Installation

After installation, you need to:

1. **Configure credentials**: See [Configuration](configuration.md)
2. **Initialize databases**: `polybot db init`
3. **Set up authentication**: `polybot auth`

## Upgrading

### PyPI

```bash
pip install --upgrade polybot-trader
```

### Docker

```bash
docker compose pull
docker compose up -d
```

### From Source

```bash
git pull
uv sync
```

## Troubleshooting

### Common Issues

**ModuleNotFoundError: No module named 'polybot'**
```bash
# Ensure you're in the virtual environment
source .venv/bin/activate
```

**NNG socket errors on Windows**
```bash
# Use WSL2 instead of native Windows
wsl --install
```

**Permission denied for IPC sockets**
```bash
# Check /tmp/polybot directory permissions
sudo chmod 777 /tmp/polybot
```

For more help, see [FAQ](../faq.md) or [open an issue](https://github.com/cryptuon/polybot/issues).
