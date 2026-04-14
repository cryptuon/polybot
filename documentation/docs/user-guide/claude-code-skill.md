# Claude Code Skill

PolyBot includes a skill for Claude Code that provides direct CLI access within Claude Code conversations.

## Installation

### Automatic Installation

From the polybot repository directory:

```bash
cp -r .claude/skills ~/.claude/skills/
```

### Manual Installation

Create the skill file at `~/.claude/skills/polybot.md` with the content from `.claude/skills/polybot.md` in the repository.

## Usage

Once installed, you can use the `/polybot` command in Claude Code:

```
/polybot strategy list
```

Or ask Claude naturally:

- "Show me the current strategy status"
- "Enable the arbitrage strategy in shadow mode"
- "What's the AI trading audit log showing?"

## Available Commands

### Service Management

```bash
/polybot start              # Start all services
/polybot api                # Run API server only
/polybot mcp start          # Start MCP server
```

### Strategy Management

```bash
/polybot strategy list                    # List all strategies
/polybot strategy enable <name>           # Enable a strategy
/polybot strategy disable <name>          # Disable a strategy
/polybot strategy shadow <name> --enable  # Enable shadow mode
/polybot strategy shadow <name> --disable # Disable shadow mode
/polybot strategy run <name>              # Run single strategy
```

### AI Trading Management

```bash
/polybot mcp status                 # Show MCP status
/polybot mcp mode <mode>            # Set trading mode
/polybot mcp pending                # List pending approvals
/polybot mcp approve <id>           # Approve AI trade
/polybot mcp reject <id> -r "why"   # Reject AI trade
/polybot mcp audit                  # View audit log
```

### Market Analysis

```bash
/polybot ai plugins                 # List AI plugins
/polybot ai info <plugin>           # Plugin details
/polybot ai predict <market_id>     # Test prediction
/polybot ai scan                    # Scan for opportunities
```

### Statistical Arbitrage

```bash
/polybot statarb correlations       # View correlations
/polybot statarb compute            # Compute correlations
/polybot statarb opportunities      # Find opportunities
```

### Database & Configuration

```bash
/polybot db init                    # Initialize databases
/polybot db stats                   # Show statistics
/polybot config                     # Show configuration
```

## Example Workflows

### Starting Shadow Trading

```
/polybot strategy enable arbitrage
/polybot strategy shadow arbitrage --enable
/polybot start
```

### Reviewing AI Activity

```
/polybot mcp status
/polybot mcp audit --tail 20
```

### Approving AI Trades

```
/polybot mcp pending
/polybot mcp approve abc123
```

## Safety Notes

- **Shadow Mode First**: Always test in shadow mode before live trading
- **Review Audit Logs**: Check AI actions regularly with `/polybot mcp audit`
- **Approval Workflow**: Keep approval enabled for live trades

## Troubleshooting

### Skill Not Found

Ensure the skill file is in the correct location:

```bash
ls ~/.claude/skills/polybot.md
```

### Commands Failing

Check that PolyBot is installed and configured:

```bash
polybot --version
polybot config
```

### Permission Denied

Some commands require the API server or services to be running:

```bash
/polybot api  # In another terminal
```
