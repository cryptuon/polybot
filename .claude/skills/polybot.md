---
name: polybot
description: Interact with PolyBot trading system via CLI
---

# PolyBot CLI Skill

Execute PolyBot CLI commands for trading system management.

## Available Commands

### Service Management
- `polybot start` - Start all services
- `polybot api` - Run API server only
- `polybot mcp start` - Start MCP server

### Strategy Management  
- `polybot strategy list` - List all strategies with enabled/shadow status
- `polybot strategy enable <name>` - Enable a strategy
- `polybot strategy disable <name>` - Disable a strategy
- `polybot strategy shadow <name> --enable` - Enable shadow mode (paper trading)
- `polybot strategy shadow <name> --disable` - Disable shadow mode
- `polybot strategy run <name>` - Run a single strategy

### AI Trading Management (MCP)
- `polybot mcp status` - Show MCP server status, mode, and pending approvals
- `polybot mcp mode <disabled|shadow|live>` - Set AI trading mode
- `polybot mcp pending` - List pending AI trade approvals
- `polybot mcp approve <id>` - Approve a pending AI trade
- `polybot mcp reject <id> -r "reason"` - Reject a pending AI trade
- `polybot mcp audit` - View AI action audit log

### Market Analysis
- `polybot ai plugins` - List available AI prediction plugins
- `polybot ai info <plugin>` - Show plugin details
- `polybot ai predict <market_id>` - Test AI prediction for a market
- `polybot ai scan` - Scan markets for AI-predicted opportunities

### Statistical Arbitrage
- `polybot statarb correlations` - Show computed market correlations
- `polybot statarb compute --hours 48` - Compute correlations
- `polybot statarb opportunities` - Show current stat arb opportunities
- `polybot statarb prices` - Show recent price snapshots

### Database & Configuration
- `polybot db init` - Initialize databases
- `polybot db stats` - Show 30-day trading statistics
- `polybot config` - Show current configuration

### Authentication
- `polybot auth --create` - Create new API credentials
- `polybot auth --derive` - Derive existing credentials

## Usage

When using this skill, run commands via bash. For example:

```bash
# List all strategies
polybot strategy list

# Enable arbitrage in shadow mode
polybot strategy enable arbitrage
polybot strategy shadow arbitrage --enable

# Check MCP status
polybot mcp status

# Approve an AI trade
polybot mcp approve abc123
```

## AI Trading Modes

| Mode | Description |
|------|-------------|
| `disabled` | AI can only read market data |
| `shadow` | AI can paper trade (no real money) |
| `live` | AI can submit real orders (with approval) |

## Safety Notes

- Shadow mode is recommended for testing AI strategies
- Live trading requires explicit approval by default
- All AI actions are logged in the audit log
- Position limits apply to AI trades separately from manual limits
