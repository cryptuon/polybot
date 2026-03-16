# Dashboard

PolyBot includes a Vue.js web dashboard for monitoring and managing your trading.

## Accessing the Dashboard

Start the API server:

```bash
polybot start
# or
polybot api
```

Open in browser:
```
http://localhost:8000/ui
```

## Dashboard Sections

### Home

Overview of your trading activity:

- **Total P&L** - Realized and unrealized
- **Active positions** - Current holdings
- **Strategy status** - Which strategies are running
- **Recent signals** - Latest trading signals

### Strategies

Manage trading strategies:

- **Enable/Disable** - Toggle strategies on/off
- **Shadow mode** - Toggle paper trading
- **Configuration** - View strategy settings
- **Performance** - Per-strategy metrics

### Positions

View open positions:

- **Market** - Which market
- **Side** - YES or NO
- **Size** - Position size
- **Entry price** - Average entry
- **Current price** - Live price
- **P&L** - Unrealized profit/loss

### Orders

Order management:

- **Open orders** - Pending orders
- **Order history** - Recent fills
- **Cancel orders** - Cancel pending orders

### Markets

Browse available markets:

- **Active markets** - Currently tradeable
- **Search** - Find specific markets
- **Details** - Volume, liquidity, prices

### Analytics

Performance analytics:

- **P&L chart** - Performance over time
- **Win rate** - Percentage of winning trades
- **Strategy comparison** - Side-by-side metrics
- **Volume** - Trading volume by strategy

### Strategy Logs

Detailed strategy activity:

- **Signals** - All generated signals
- **Scans** - Scanning activity
- **Errors** - Any issues
- **Filter** - By strategy, type, time

### Settings

Configuration:

- **Risk limits** - Position and exposure limits
- **API settings** - Connection configuration
- **Notifications** - Alert settings

## Real-Time Updates

The dashboard uses WebSocket for live updates:

- Price changes
- Position updates
- New signals
- Order fills

No need to refresh - data updates automatically.

## API Endpoints

The dashboard uses these API endpoints:

| Endpoint | Description |
|----------|-------------|
| `GET /api/markets` | List markets |
| `GET /api/strategies` | List strategies |
| `POST /api/strategies/{name}/toggle` | Enable/disable |
| `GET /api/positions` | Open positions |
| `GET /api/orders` | Orders |
| `GET /api/analytics/summary` | Performance |
| `WS /ws` | Real-time updates |

Full API docs at:
```
http://localhost:8000/docs
```

## Mobile Access

The dashboard is responsive and works on mobile devices. For remote access:

1. Bind to all interfaces:
   ```bash
   API_HOST=0.0.0.0
   ```

2. Use a reverse proxy (nginx) with HTTPS

3. Enable authentication:
   ```bash
   AUTH_ENABLED=true
   AUTH_JWT_SECRET=your-secure-secret
   ```

## Customization

### Themes

The dashboard supports dark and light modes (toggle in settings).

### Building from Source

To modify the dashboard:

```bash
cd frontend
npm install
npm run dev    # Development server
npm run build  # Production build
```

## Troubleshooting

### Dashboard not loading

1. Check API is running: `curl http://localhost:8000/`
2. Check for CORS issues in browser console
3. Verify port 8000 is not blocked

### Data not updating

1. Check WebSocket connection in browser dev tools
2. Verify services are running: `polybot status`
3. Check for errors: `polybot logs --tail 50`

### Slow performance

1. Reduce polling frequency in settings
2. Limit displayed history
3. Check system resources
