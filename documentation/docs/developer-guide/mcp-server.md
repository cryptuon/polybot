# MCP Server Development

This guide covers the architecture and development of PolyBot's MCP (Model Context Protocol) server.

## Architecture

The MCP server is implemented in `src/polybot/mcp/` with the following structure:

```
src/polybot/mcp/
    __init__.py           # Package exports
    server.py             # MCP server implementation
    tools.py              # Tool definitions
    handlers.py           # Tool implementation handlers
    approval.py           # Approval workflow
    audit.py              # Audit logging
```

## Server Implementation

The MCP server is built on the `mcp` Python library and uses stdio transport:

```python
from mcp.server import Server
from mcp.server.stdio import stdio_server

server = Server("polybot")

@server.list_tools()
async def list_tools() -> list[Tool]:
    """Return available tools based on configuration."""
    tools = get_readonly_tools()
    
    if settings.mcp.ai_trading_mode in ("shadow", "live"):
        tools.extend(get_shadow_tools())
    
    if settings.mcp.ai_trading_mode == "live":
        tools.extend(get_live_tools())
    
    return tools

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""
    result = await handle_tool_call(name, arguments)
    return [TextContent(type="text", text=result)]
```

## Tool Categories

### Read-Only Tools

Always available when MCP is enabled:

```python
def get_readonly_tools() -> list[Tool]:
    return [
        Tool(
            name="list_markets",
            description="List available prediction markets",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "default": 50},
                    "active_only": {"type": "boolean", "default": True},
                },
            },
        ),
        # ... more tools
    ]
```

### Trading Tools

Gated by `ai_trading_mode` setting:

```python
def get_shadow_tools() -> list[Tool]:
    """Requires shadow or live mode."""
    return [
        Tool(
            name="shadow_buy",
            description="Paper trade buy order",
            inputSchema={
                "type": "object",
                "properties": {
                    "market_id": {"type": "string"},
                    "side": {"type": "string", "enum": ["YES", "NO"]},
                    "size": {"type": "number"},
                    "reason": {"type": "string"},
                },
                "required": ["market_id", "side", "size", "reason"],
            },
        ),
    ]
```

## Adding Custom Tools

### 1. Define the Tool

Add to `tools.py`:

```python
def get_custom_tools() -> list[Tool]:
    return [
        Tool(
            name="my_custom_tool",
            description="Description of what the tool does",
            inputSchema={
                "type": "object",
                "properties": {
                    "param1": {"type": "string", "description": "First parameter"},
                    "param2": {"type": "integer", "default": 10},
                },
                "required": ["param1"],
            },
        ),
    ]
```

### 2. Implement the Handler

Add to `handlers.py`:

```python
async def handle_custom_tool(name: str, arguments: dict) -> str:
    if name == "my_custom_tool":
        param1 = arguments["param1"]
        param2 = arguments.get("param2", 10)
        
        # Implement your logic
        result = do_something(param1, param2)
        
        return json.dumps({"result": result})
    
    return json.dumps({"error": f"Unknown tool: {name}"})
```

### 3. Register in Tool Router

Update `handle_tool_call` in `tools.py`:

```python
async def handle_tool_call(name: str, arguments: dict) -> str:
    # ... existing categories
    
    custom_tools = {t.name for t in get_custom_tools()}
    if name in custom_tools:
        return await handle_custom_tool(name, arguments)
```

### 4. Add to Tool List

Update `list_tools` in `server.py` to include your tools.

## Approval Workflow

The approval system stores pending trades in memory and persists to `data/mcp_approvals.json`:

```python
from polybot.mcp.approval import submit_for_approval, approve_trade

# Submit for approval
approval = await submit_for_approval(
    order_type="submit_order",
    arguments={"market_id": "...", "size": 50},
    expires_at=datetime.utcnow() + timedelta(seconds=300),
)

# Approve
result = await approve_trade(approval["id"], approved_by="operator")
```

## Audit Logging

All tool calls are logged to `data/mcp_audit.jsonl`:

```python
from polybot.mcp.audit import audit_log

await audit_log(
    action="tool_call",
    tool="list_markets",
    arguments={"limit": 50},
    timestamp=datetime.utcnow(),
)
```

Query logs:

```python
from polybot.mcp.audit import get_audit_logs, get_audit_stats

logs = get_audit_logs(tail=20)
stats = get_audit_stats(days=7)
```

## Security Considerations

### Permission Checks

Always check permissions before executing:

```python
settings = get_settings()

if settings.mcp.ai_trading_mode != "live":
    raise PermissionError("Live trading requires live mode")

if size > settings.mcp.max_position_usd:
    raise PermissionError(f"Position size exceeds limit")
```

### CLI Command Whitelist

Only allow safe CLI commands:

```python
ALLOWED_CLI_COMMANDS = {
    "strategy": ["list", "enable", "disable", "shadow"],
    "db": ["init", "stats"],
    "config": [],
}

BLOCKED_CLI_COMMANDS = {"auth", "start"}
```

### Rate Limiting

Implement rate limiting at the server level:

```python
# Track calls per minute
_call_counts: dict[str, list[datetime]] = {}

def check_rate_limit(agent_id: str) -> bool:
    now = datetime.utcnow()
    minute_ago = now - timedelta(minutes=1)
    
    calls = _call_counts.get(agent_id, [])
    calls = [c for c in calls if c > minute_ago]
    
    if len(calls) >= settings.mcp.rate_limit_per_min:
        return False
    
    calls.append(now)
    _call_counts[agent_id] = calls
    return True
```

## Testing

### Unit Tests

```python
import pytest
from polybot.mcp.tools import get_readonly_tools, handle_tool_call

def test_readonly_tools_available():
    tools = get_readonly_tools()
    names = {t.name for t in tools}
    assert "list_markets" in names
    assert "get_positions" in names

@pytest.mark.asyncio
async def test_list_markets():
    result = await handle_tool_call("list_markets", {"limit": 10})
    data = json.loads(result)
    assert "markets" in data
```

### Integration Tests

```python
@pytest.mark.asyncio
async def test_mcp_server():
    server = create_mcp_server()
    
    # Test tool listing
    tools = await server.list_tools()
    assert len(tools) > 0
    
    # Test tool call
    result = await server.call_tool("get_strategies", {})
    assert len(result) == 1
    assert result[0].type == "text"
```

## API Integration

The MCP status and approvals are also available via REST API:

```python
# API routes in src/polybot/api/routes/mcp.py

@router.get("/status")
async def get_mcp_status():
    """Get MCP server status."""

@router.get("/pending")
async def list_pending_approvals():
    """List pending trade approvals."""

@router.post("/pending/{id}/approve")
async def approve_trade(id: str):
    """Approve a pending trade."""
```

## Extending Resources

MCP also supports resources for streaming data. To add market data resources:

```python
@server.list_resources()
async def list_resources() -> list[Resource]:
    return [
        Resource(
            uri="polybot://markets",
            name="Market Data",
            description="Real-time market prices",
            mimeType="application/json",
        ),
    ]

@server.read_resource()
async def read_resource(uri: str) -> str:
    if uri == "polybot://markets":
        markets = await get_active_markets()
        return json.dumps(markets)
```
