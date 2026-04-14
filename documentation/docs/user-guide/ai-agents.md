# AI Agent Integration

PolyBot includes an MCP (Model Context Protocol) server that allows AI agents like Claude to interact with your trading system.

## What is MCP?

The [Model Context Protocol](https://modelcontextprotocol.io/) is an open standard for AI agents to interact with external systems. PolyBot's MCP server exposes trading functionality as tools that AI agents can call.

## Quick Start

### 1. Enable MCP Server

Add to your `.env`:

```bash
MCP_ENABLED=true
MCP_AI_TRADING_MODE=shadow  # Start with paper trading
```

### 2. Start MCP Server

```bash
polybot mcp start
```

### 3. Connect AI Agent

Configure your AI agent (Claude Code, etc.) to connect to the MCP server.

## Trading Modes

PolyBot supports three trading modes for AI agents:

| Mode | Description | Use Case |
|------|-------------|----------|
| `disabled` | Read-only access to market data | Analysis only |
| `shadow` | Paper trading (no real money) | Testing strategies |
| `live` | Real trading with approval workflow | Production |

### Setting the Mode

Via environment variable:
```bash
MCP_AI_TRADING_MODE=shadow
```

Via CLI:
```bash
polybot mcp mode shadow
```

Via API:
```bash
curl -X PUT http://localhost:8000/api/mcp/settings \
  -H "Content-Type: application/json" \
  -d '{"ai_trading_mode": "shadow"}'
```

## Available Tools

### Read-Only Tools (All Modes)

| Tool | Description |
|------|-------------|
| `list_markets` | List available prediction markets |
| `get_market` | Get market details and prices |
| `get_positions` | View open and closed positions |
| `get_orders` | View order history |
| `get_strategies` | List strategies and status |
| `get_risk_status` | Check exposure and limits |
| `analyze_market` | AI prediction for a market |

### Strategy Assessment Tools (All Modes)

| Tool | Description |
|------|-------------|
| `get_strategy_logs` | View strategy execution logs |
| `get_strategy_performance` | Detailed performance metrics |
| `analyze_strategy` | AI analysis with recommendations |
| `compare_strategies` | Side-by-side strategy comparison |
| `get_strategy_code` | Read strategy source code |
| `suggest_strategy_improvements` | AI-generated suggestions |

### Shadow Trading Tools (Shadow/Live Modes)

| Tool | Description |
|------|-------------|
| `shadow_buy` | Paper trade buy order |
| `shadow_sell` | Paper trade sell order |
| `shadow_close_position` | Close paper position |

### Live Trading Tools (Live Mode Only)

| Tool | Description |
|------|-------------|
| `submit_order` | Submit real order (may require approval) |
| `cancel_order` | Cancel pending order |
| `close_position` | Close real position |

## Approval Workflow

When `MCP_REQUIRE_APPROVAL=true` (default), live trades from AI agents require human approval before execution.

### Viewing Pending Approvals

```bash
polybot mcp pending
```

Or via API:
```bash
curl http://localhost:8000/api/mcp/pending
```

### Approving a Trade

```bash
polybot mcp approve <approval_id>
```

### Rejecting a Trade

```bash
polybot mcp reject <approval_id> -r "Reason for rejection"
```

### Approval Timeout

Pending approvals expire after `MCP_APPROVAL_TIMEOUT_SEC` (default: 300 seconds).

## Safety Controls

### Position Limits

AI trades are limited by `MCP_MAX_POSITION_USD` (default: $100), separate from your main risk limits.

### Daily Loss Limit

If AI trading losses exceed `MCP_DAILY_LOSS_LIMIT_USD`, trading is automatically disabled.

### Rate Limiting

Tool calls are limited to `MCP_RATE_LIMIT_PER_MIN` (default: 30) to prevent abuse.

### Audit Logging

All AI actions are logged to `data/mcp_audit.jsonl`:

```bash
polybot mcp audit
```

## Configuration Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_ENABLED` | `false` | Enable MCP server |
| `MCP_HOST` | `127.0.0.1` | Server host |
| `MCP_PORT` | `3001` | Server port |
| `MCP_AI_TRADING_MODE` | `shadow` | disabled/shadow/live |
| `MCP_MAX_POSITION_USD` | `100` | Max position per AI trade |
| `MCP_DAILY_LOSS_LIMIT_USD` | `200` | AI daily loss limit |
| `MCP_REQUIRE_APPROVAL` | `true` | Require approval for live trades |
| `MCP_APPROVAL_TIMEOUT_SEC` | `300` | Approval expiration |
| `MCP_RATE_LIMIT_PER_MIN` | `30` | Tool call rate limit |
| `MCP_AUDIT_LOG_ENABLED` | `true` | Log AI actions |
| `MCP_ALLOW_CODE_READ` | `true` | Allow reading strategy code |
| `MCP_ALLOW_CLI_EXECUTION` | `true` | Allow CLI commands |

## Best Practices

### Start with Shadow Mode

Always test AI strategies in shadow mode before enabling live trading:

```bash
MCP_AI_TRADING_MODE=shadow
```

### Review Audit Logs

Regularly review AI actions:

```bash
polybot mcp audit --tail 50
```

### Set Conservative Limits

Start with conservative position limits and increase gradually:

```bash
MCP_MAX_POSITION_USD=50
MCP_DAILY_LOSS_LIMIT_USD=100
```

### Enable Approval for Live Trading

Keep approval enabled until you're confident in the AI's behavior:

```bash
MCP_REQUIRE_APPROVAL=true
```

## Troubleshooting

### MCP Server Won't Start

Check that MCP is enabled:
```bash
echo $MCP_ENABLED  # Should be "true"
```

### Tools Not Appearing

Verify the trading mode allows the tools you need:
- Read-only tools: all modes
- Shadow tools: `shadow` or `live` mode
- Live tools: `live` mode only

### Approvals Expiring

Increase the timeout:
```bash
MCP_APPROVAL_TIMEOUT_SEC=600
```

### Rate Limit Errors

Increase the rate limit or optimize tool usage:
```bash
MCP_RATE_LIMIT_PER_MIN=60
```
