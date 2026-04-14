"""Command-line interface for PolyBot."""

import asyncio
import logging
import sys
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.logging import RichHandler

from polybot import __version__
from polybot.config import get_settings


console = Console()


def setup_logging(level: str) -> None:
    """Configure logging with rich handler."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(message)s",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )


@click.group()
@click.version_option(version=__version__)
@click.option("--log-level", default="INFO", help="Logging level")
def cli(log_level: str) -> None:
    """PolyBot - Polymarket Trading Bot.

    A comprehensive trading bot for Polymarket with multiple
    automated strategies and a management dashboard.
    """
    setup_logging(log_level)


# =============================================================================
# Service Commands
# =============================================================================


@cli.command()
@click.option("--services", "-s", multiple=True, help="Services to start (default: all)")
@click.option("--no-api", is_flag=True, help="Don't start the API server")
def start(services: tuple, no_api: bool) -> None:
    """Start all services (scanner, executor, analytics, api)."""
    from polybot.services.manager import ServiceManager

    console.print("[bold green]Starting PolyBot services...[/]")

    manager = ServiceManager()

    if services:
        service_list = list(services)
    elif no_api:
        service_list = ["scanner", "executor", "analytics"]
    else:
        service_list = None  # All services including API

    try:
        asyncio.run(manager.run(service_list))
    except KeyboardInterrupt:
        console.print("[yellow]Shutting down...[/]")


@cli.command()
@click.argument("service")
def scanner(service: str = "") -> None:
    """Run the scanner service."""
    from polybot.services.scanner import ScannerService

    console.print("[bold green]Starting scanner service...[/]")

    service_instance = ScannerService()
    asyncio.run(service_instance.run())


@cli.command()
def executor() -> None:
    """Run the executor service."""
    from polybot.services.executor import ExecutorService

    console.print("[bold green]Starting executor service...[/]")

    service_instance = ExecutorService()
    asyncio.run(service_instance.run())


@cli.command()
def analytics() -> None:
    """Run the analytics service."""
    from polybot.services.analytics import AnalyticsService

    console.print("[bold green]Starting analytics service...[/]")

    service_instance = AnalyticsService()
    asyncio.run(service_instance.run())


# =============================================================================
# Strategy Commands
# =============================================================================


@cli.group()
def strategy() -> None:
    """Manage trading strategies."""
    pass


@strategy.command("list")
def strategy_list() -> None:
    """List all strategies."""
    from polybot.strategies import STRATEGY_REGISTRY
    from polybot.db.state_client import StateClient

    async def get_strategy_status() -> dict[str, dict]:
        """Query database for strategy status."""
        client = StateClient()
        await client.connect()
        try:
            status = {}
            for name in STRATEGY_REGISTRY.keys():
                try:
                    config = await client.get_strategy_config(name)
                    status[name] = {
                        "enabled": config.get("enabled", False) if config else False,
                        "shadow": config.get("shadow", False) if config else False,
                    }
                except Exception:
                    status[name] = {"enabled": False, "shadow": False}
            return status
        finally:
            await client.close()

    # Get status from database
    try:
        strategy_status = asyncio.run(get_strategy_status())
    except Exception:
        # If database query fails, show all as unknown
        strategy_status = {name: {"enabled": False, "shadow": False} for name in STRATEGY_REGISTRY.keys()}

    table = Table(title="Available Strategies")
    table.add_column("Name", style="cyan")
    table.add_column("Description")
    table.add_column("Enabled", style="green")
    table.add_column("Shadow", style="yellow")

    for name, cls in STRATEGY_REGISTRY.items():
        status = strategy_status.get(name, {"enabled": False, "shadow": False})
        table.add_row(
            name,
            getattr(cls, "description", ""),
            "✓" if status["enabled"] else "✗",
            "✓" if status["shadow"] else "✗",
        )

    console.print(table)


@strategy.command("run")
@click.argument("name")
def strategy_run(name: str) -> None:
    """Run a single strategy."""
    from polybot.strategies import STRATEGY_REGISTRY

    if name not in STRATEGY_REGISTRY:
        console.print(f"[red]Unknown strategy: {name}[/]")
        sys.exit(1)

    console.print(f"[bold green]Starting {name} strategy...[/]")

    strategy_class = STRATEGY_REGISTRY[name]
    strategy_instance = strategy_class()

    asyncio.run(strategy_instance.run())


@strategy.command("enable")
@click.argument("name")
def strategy_enable(name: str) -> None:
    """Enable a strategy."""
    from polybot.strategies import STRATEGY_REGISTRY
    from polybot.db.state_client import StateClient

    if name not in STRATEGY_REGISTRY:
        console.print(f"[red]Unknown strategy: {name}[/]")
        sys.exit(1)

    async def enable_strategy() -> None:
        client = StateClient()
        await client.connect()
        try:
            # Get current config to preserve shadow and config
            current = await client.get_strategy_config(name)
            shadow = current.get("shadow", False) if current else False
            config = current.get("config", {}) if current else {}

            await client.save_strategy_config(
                name=name,
                enabled=True,
                config=config,
                shadow=shadow,
            )
            console.print(f"[green]Strategy '{name}' enabled[/]")
        finally:
            await client.close()

    asyncio.run(enable_strategy())


@strategy.command("disable")
@click.argument("name")
def strategy_disable(name: str) -> None:
    """Disable a strategy."""
    from polybot.strategies import STRATEGY_REGISTRY
    from polybot.db.state_client import StateClient

    if name not in STRATEGY_REGISTRY:
        console.print(f"[red]Unknown strategy: {name}[/]")
        sys.exit(1)

    async def disable_strategy() -> None:
        client = StateClient()
        await client.connect()
        try:
            # Get current config to preserve shadow and config
            current = await client.get_strategy_config(name)
            shadow = current.get("shadow", False) if current else False
            config = current.get("config", {}) if current else {}

            await client.save_strategy_config(
                name=name,
                enabled=False,
                config=config,
                shadow=shadow,
            )
            console.print(f"[yellow]Strategy '{name}' disabled[/]")
        finally:
            await client.close()

    asyncio.run(disable_strategy())


@strategy.command("shadow")
@click.argument("name")
@click.option("--enable/--disable", "shadow_enabled", default=None, help="Enable or disable shadow mode")
def strategy_shadow(name: str, shadow_enabled: Optional[bool]) -> None:
    """Toggle shadow mode for a strategy.

    Shadow mode allows strategies to generate signals without executing trades.
    Signals are logged but not sent to the executor.

    Examples:
        polybot strategy shadow ai_model --enable
        polybot strategy shadow stat_arb --disable
    """
    from polybot.strategies import STRATEGY_REGISTRY
    from polybot.db.state_client import StateClient

    if name not in STRATEGY_REGISTRY:
        console.print(f"[red]Unknown strategy: {name}[/]")
        sys.exit(1)

    if shadow_enabled is None:
        console.print("[red]Please specify --enable or --disable[/]")
        sys.exit(1)

    async def toggle_shadow() -> None:
        client = StateClient()
        await client.connect()
        try:
            # Get current config to preserve enabled and config
            current = await client.get_strategy_config(name)
            enabled = current.get("enabled", False) if current else False
            config = current.get("config", {}) if current else {}

            await client.save_strategy_config(
                name=name,
                enabled=enabled,
                config=config,
                shadow=shadow_enabled,
            )

            if shadow_enabled:
                console.print(f"[yellow]Shadow mode enabled for '{name}'[/]")
                console.print("[dim]Signals will be logged but not executed[/]")
            else:
                console.print(f"[green]Shadow mode disabled for '{name}'[/]")
                console.print("[dim]Signals will be executed normally[/]")
        finally:
            await client.close()

    asyncio.run(toggle_shadow())


# =============================================================================
# API Commands
# =============================================================================


@cli.command()
@click.option("--host", default=None, help="Host to bind to")
@click.option("--port", default=None, type=int, help="Port to bind to")
@click.option("--reload", is_flag=True, help="Enable auto-reload")
def api(host: Optional[str], port: Optional[int], reload: bool) -> None:
    """Run the API server."""
    import uvicorn

    settings = get_settings()

    uvicorn.run(
        "polybot.api.app:app",
        host=host or settings.api.host,
        port=port or settings.api.port,
        reload=reload or settings.api.reload,
    )


# =============================================================================
# Database Commands
# =============================================================================


@cli.group()
def db() -> None:
    """Database management commands."""
    pass


@db.command("init")
def db_init() -> None:
    """Initialize databases."""
    from polybot.db.sqlite_store import SQLiteStore
    from polybot.db.duckdb_store import DuckDBStore

    console.print("[bold]Initializing databases...[/]")

    # Initialize SQLite
    async def init_sqlite() -> None:
        store = SQLiteStore()
        await store.connect()
        await store.close()

    asyncio.run(init_sqlite())
    console.print("[green]SQLite initialized[/]")

    # Initialize DuckDB
    store = DuckDBStore()
    store.connect()
    store.close()
    console.print("[green]DuckDB initialized[/]")

    console.print("[bold green]Databases ready![/]")


@db.command("stats")
def db_stats() -> None:
    """Show database statistics."""
    from polybot.db.duckdb_store import get_duckdb_store

    duckdb = get_duckdb_store()
    summary = duckdb.get_performance_summary(days=30)

    table = Table(title="30-Day Performance")
    table.add_column("Metric")
    table.add_column("Value", style="cyan")

    table.add_row("Total Trades", str(summary.get("total_trades", 0)))
    table.add_row("Win Rate", f"{summary.get('win_rate', 0)*100:.1f}%")
    table.add_row("Total P&L", f"${summary.get('total_pnl', 0):.2f}")
    table.add_row("Total Volume", f"${summary.get('total_volume', 0):.2f}")
    table.add_row("Total Fees", f"${summary.get('total_fees', 0):.2f}")

    console.print(table)


# =============================================================================
# Config Commands
# =============================================================================


@cli.command("config")
def show_config() -> None:
    """Show current configuration."""
    settings = get_settings()

    console.print("[bold]Current Configuration[/]\n")

    # API URLs
    console.print("[cyan]API Endpoints:[/]")
    console.print(f"  CLOB: {settings.clob_base_url}")
    console.print(f"  Gamma: {settings.gamma_base_url}")
    console.print(f"  Data: {settings.data_base_url}")

    # Risk settings
    console.print("\n[cyan]Risk Limits:[/]")
    console.print(f"  Max Position: ${settings.risk.max_position_size_usd}")
    console.print(f"  Max Exposure: ${settings.risk.max_total_exposure_usd}")
    console.print(f"  Daily Loss Limit: ${settings.risk.daily_loss_limit_usd}")
    console.print(f"  Max Open Orders: {settings.risk.max_open_orders}")

    # Database paths
    console.print("\n[cyan]Databases:[/]")
    console.print(f"  SQLite: {settings.database.sqlite_path}")
    console.print(f"  DuckDB: {settings.database.duckdb_path}")

    # API server
    console.print("\n[cyan]API Server:[/]")
    console.print(f"  Host: {settings.api.host}")
    console.print(f"  Port: {settings.api.port}")


# =============================================================================
# Auth Commands
# =============================================================================


@cli.command("auth")
@click.option("--create", is_flag=True, help="Create new API credentials")
@click.option("--derive", is_flag=True, help="Derive existing credentials")
def auth(create: bool, derive: bool) -> None:
    """Manage API authentication."""
    from polybot.core.client import PolymarketClient

    settings = get_settings()

    if not settings.polymarket.private_key:
        console.print("[red]No private key configured. Set POLYMARKET_PRIVATE_KEY.[/]")
        sys.exit(1)

    async def manage_auth() -> None:
        async with PolymarketClient() as client:
            if create:
                console.print("[bold]Creating new API credentials...[/]")
                creds = await client.create_api_key()
            elif derive:
                console.print("[bold]Deriving API credentials...[/]")
                creds = await client.derive_api_key()
            else:
                console.print("[bold]Creating or deriving API credentials...[/]")
                creds = await client.create_or_derive_api_key()

            console.print("\n[green]API Credentials:[/]")
            console.print(f"  API Key: {creds.api_key}")
            console.print(f"  Secret: {creds.secret[:20]}...")
            console.print(f"  Passphrase: {creds.passphrase}")
            console.print("\n[yellow]Add these to your .env file![/]")

    asyncio.run(manage_auth())


# =============================================================================
# Stat Arb Commands
# =============================================================================


@cli.group()
def statarb() -> None:
    """Statistical arbitrage commands."""
    pass


@statarb.command("correlations")
@click.option("--min-corr", default=0.5, help="Minimum correlation to show")
@click.option("--limit", default=20, help="Maximum pairs to show")
def show_correlations(min_corr: float, limit: int) -> None:
    """Show computed market correlations."""
    from polybot.db.duckdb_store import get_duckdb_store
    from polybot.db.sqlite_store import SQLiteStore

    async def get_data() -> None:
        duckdb = get_duckdb_store()
        sqlite = SQLiteStore()
        await sqlite.connect()

        # Get market names
        markets = await sqlite.get_active_markets(limit=200)
        market_names = {m.id: m.question[:50] for m in markets}

        # Query correlations
        result = duckdb._conn.execute(
            """
            SELECT market_a, market_b, correlation, calculated_at
            FROM market_correlations
            WHERE ABS(correlation) >= ?
            ORDER BY ABS(correlation) DESC
            LIMIT ?
            """,
            [min_corr, limit],
        ).fetchall()

        await sqlite.close()

        if not result:
            console.print("[yellow]No correlations found. Run the analytics service first.[/]")
            return

        table = Table(title=f"Market Correlations (>= {min_corr})")
        table.add_column("Market A", style="cyan", max_width=40)
        table.add_column("Market B", style="cyan", max_width=40)
        table.add_column("Correlation", style="green")
        table.add_column("Calculated", style="dim")

        for row in result:
            market_a_name = market_names.get(row[0], row[0][:20])
            market_b_name = market_names.get(row[1], row[1][:20])
            corr = f"{row[2]:.3f}"
            calc_time = row[3].strftime("%Y-%m-%d %H:%M") if row[3] else "Unknown"

            table.add_row(market_a_name, market_b_name, corr, calc_time)

        console.print(table)
        console.print(f"\n[dim]Showing {len(result)} pairs[/]")

    asyncio.run(get_data())


@statarb.command("compute")
@click.option("--hours", default=48, help="Lookback hours for correlation")
def compute_correlations(hours: int) -> None:
    """Manually compute market correlations."""
    import numpy as np
    from datetime import datetime, timedelta
    from polybot.db.duckdb_store import get_duckdb_store
    from polybot.db.sqlite_store import SQLiteStore

    async def compute() -> None:
        duckdb = get_duckdb_store()
        sqlite = SQLiteStore()
        await sqlite.connect()

        console.print(f"[bold]Computing correlations (lookback: {hours} hours)...[/]")

        # Get active markets
        markets = await sqlite.get_active_markets(limit=100)
        console.print(f"Found {len(markets)} active markets")

        # Get price history
        lookback = datetime.utcnow() - timedelta(hours=hours)
        price_data = {}

        for market in markets:
            history = duckdb.get_price_history(
                market_id=market.id,
                token_id=market.outcome_yes_token,
                start_time=lookback,
                limit=2000,
            )
            if history and len(history) >= 20:
                history = sorted(history, key=lambda x: x["timestamp"])
                price_data[market.id] = [h["mid"] for h in history]

        console.print(f"Got price data for {len(price_data)} markets")

        if len(price_data) < 2:
            console.print("[yellow]Not enough price history. Run the scanner first.[/]")
            await sqlite.close()
            return

        # Compute returns
        returns_data = {}
        for market_id, prices in price_data.items():
            if len(prices) >= 2:
                returns = []
                for i in range(1, len(prices)):
                    if prices[i - 1] > 0:
                        ret = (prices[i] - prices[i - 1]) / prices[i - 1]
                        returns.append(ret)
                if len(returns) >= 10:
                    returns_data[market_id] = returns

        console.print(f"Computed returns for {len(returns_data)} markets")

        # Compute correlations
        market_ids = list(returns_data.keys())
        correlations_found = 0

        with console.status("[bold green]Computing correlations..."):
            for i, market_a in enumerate(market_ids):
                for market_b in market_ids[i + 1:]:
                    returns_a = returns_data[market_a]
                    returns_b = returns_data[market_b]

                    min_len = min(len(returns_a), len(returns_b))
                    if min_len < 10:
                        continue

                    aligned_a = returns_a[-min_len:]
                    aligned_b = returns_b[-min_len:]

                    try:
                        std_a = np.std(aligned_a)
                        std_b = np.std(aligned_b)

                        if std_a < 1e-10 or std_b < 1e-10:
                            continue

                        corr = np.corrcoef(aligned_a, aligned_b)[0, 1]

                        if not np.isnan(corr) and abs(corr) >= 0.5:
                            duckdb.update_correlation(
                                market_a=market_a,
                                market_b=market_b,
                                correlation=float(corr),
                                lookback_hours=hours,
                            )
                            correlations_found += 1
                    except Exception:
                        pass

        await sqlite.close()
        console.print(f"[green]Saved {correlations_found} significant correlations[/]")

    asyncio.run(compute())


@statarb.command("opportunities")
@click.option("--spread", default=0.04, help="Minimum spread threshold")
@click.option("--min-corr", default=0.7, help="Minimum correlation")
def show_opportunities(spread: float, min_corr: float) -> None:
    """Show current stat arb opportunities."""
    from polybot.db.duckdb_store import get_duckdb_store
    from polybot.db.sqlite_store import SQLiteStore

    async def find_opportunities() -> None:
        duckdb = get_duckdb_store()
        sqlite = SQLiteStore()
        await sqlite.connect()

        # Get correlations
        result = duckdb._conn.execute(
            """
            SELECT market_a, market_b, correlation
            FROM market_correlations
            WHERE ABS(correlation) >= ?
            ORDER BY ABS(correlation) DESC
            """,
            [min_corr],
        ).fetchall()

        if not result:
            console.print("[yellow]No correlations found. Run 'polybot statarb compute' first.[/]")
            await sqlite.close()
            return

        opportunities = []

        for row in result:
            market_a = await sqlite.get_market(row[0])
            market_b = await sqlite.get_market(row[1])

            if not market_a or not market_b:
                continue

            if market_a.yes_price is None or market_b.yes_price is None:
                continue

            price_spread = abs(market_a.yes_price - market_b.yes_price)

            if price_spread >= spread:
                if market_a.yes_price > market_b.yes_price:
                    long_market, short_market = market_b, market_a
                else:
                    long_market, short_market = market_a, market_b

                opportunities.append({
                    "spread": price_spread,
                    "correlation": row[2],
                    "long": long_market,
                    "short": short_market,
                })

        await sqlite.close()

        if not opportunities:
            console.print(f"[yellow]No opportunities found with spread >= {spread*100:.1f}%[/]")
            return

        opportunities.sort(key=lambda x: x["spread"], reverse=True)

        table = Table(title=f"Stat Arb Opportunities (spread >= {spread*100:.0f}%)")
        table.add_column("Spread", style="green")
        table.add_column("Corr", style="cyan")
        table.add_column("Long (Buy YES)", max_width=45)
        table.add_column("Long $", style="green")
        table.add_column("Short (Buy NO)", max_width=45)
        table.add_column("Short $", style="red")

        for opp in opportunities[:15]:
            table.add_row(
                f"{opp['spread']*100:.2f}%",
                f"{opp['correlation']:.2f}",
                opp["long"].question[:42],
                f"{opp['long'].yes_price:.3f}",
                opp["short"].question[:42],
                f"{opp['short'].yes_price:.3f}",
            )

        console.print(table)
        console.print(f"\n[dim]Found {len(opportunities)} opportunities[/]")

    asyncio.run(find_opportunities())


@statarb.command("prices")
@click.option("--limit", default=20, help="Number of markets to show")
def show_price_snapshots(limit: int) -> None:
    """Show recent price snapshots in DuckDB."""
    from polybot.db.duckdb_store import get_duckdb_store
    from polybot.db.sqlite_store import SQLiteStore

    async def show_snapshots() -> None:
        duckdb = get_duckdb_store()
        sqlite = SQLiteStore()
        await sqlite.connect()

        # Get recent snapshots
        result = duckdb._conn.execute(
            """
            SELECT market_id, COUNT(*) as count, MIN(timestamp) as first, MAX(timestamp) as last
            FROM price_history
            GROUP BY market_id
            ORDER BY count DESC
            LIMIT ?
            """,
            [limit],
        ).fetchall()

        await sqlite.close()

        if not result:
            console.print("[yellow]No price history found. Run the scanner service.[/]")
            return

        table = Table(title="Price History Summary")
        table.add_column("Market ID", style="dim")
        table.add_column("Snapshots", style="cyan")
        table.add_column("First", style="dim")
        table.add_column("Last", style="dim")

        for row in result:
            table.add_row(
                row[0][:16] + "...",
                str(row[1]),
                row[2].strftime("%m/%d %H:%M") if row[2] else "?",
                row[3].strftime("%m/%d %H:%M") if row[3] else "?",
            )

        console.print(table)

        # Total count
        total = duckdb._conn.execute("SELECT COUNT(*) FROM price_history").fetchone()[0]
        console.print(f"\n[dim]Total snapshots: {total}[/]")

    asyncio.run(show_snapshots())


# =============================================================================
# AI Model Commands
# =============================================================================


@cli.group()
def ai() -> None:
    """AI model plugin commands."""
    pass


@ai.command("plugins")
def list_ai_plugins() -> None:
    """List all available AI plugins."""
    from polybot.plugins.example_plugin import get_all_plugins

    plugins = get_all_plugins()

    table = Table(title="Available AI Plugins")
    table.add_column("Name", style="cyan")
    table.add_column("Version", style="dim")
    table.add_column("Description")
    table.add_column("Batch", style="dim")

    for name, plugin_class in plugins.items():
        instance = plugin_class()
        table.add_row(
            name,
            instance.version,
            instance.description,
            "Yes" if instance.supports_batch else "No",
        )

    console.print(table)


@ai.command("info")
@click.argument("plugin_name")
def show_plugin_info(plugin_name: str) -> None:
    """Show detailed plugin information."""
    from polybot.plugins.example_plugin import get_all_plugins

    plugins = get_all_plugins()

    if plugin_name not in plugins:
        console.print(f"[red]Plugin not found: {plugin_name}[/]")
        console.print(f"Available: {', '.join(plugins.keys())}")
        return

    plugin = plugins[plugin_name]()
    info = plugin.get_info()

    console.print(f"\n[bold cyan]{info['name']}[/] v{info['version']}")
    console.print(f"[dim]{info['description']}[/]")
    console.print()

    for key, value in info.items():
        if key not in ("name", "version", "description"):
            console.print(f"  {key}: {value}")


@ai.command("predict")
@click.argument("market_id")
@click.option("--plugin", "-p", default="simple_heuristic", help="Plugin to use")
@click.option("--config", "-c", default="{}", help="Plugin config JSON")
def test_prediction(market_id: str, plugin: str, config: str) -> None:
    """Test AI prediction for a market."""
    import json
    from datetime import datetime
    from polybot.plugins.example_plugin import get_all_plugins
    from polybot.plugins.base import MarketContext
    from polybot.db.sqlite_store import SQLiteStore

    async def run_prediction() -> None:
        plugins = get_all_plugins()

        if plugin not in plugins:
            console.print(f"[red]Plugin not found: {plugin}[/]")
            return

        try:
            plugin_config = json.loads(config)
        except json.JSONDecodeError:
            console.print("[red]Invalid JSON config[/]")
            return

        # Get market from database
        sqlite = SQLiteStore()
        await sqlite.connect()

        market = await sqlite.get_market(market_id)
        if not market:
            console.print(f"[red]Market not found: {market_id}[/]")
            await sqlite.close()
            return

        console.print(f"\n[bold]Market:[/] {market.question[:80]}...")
        console.print(f"[dim]ID: {market.id}[/]")
        console.print()

        # Initialize plugin
        plugin_instance = plugins[plugin]()
        try:
            await plugin_instance.initialize(plugin_config)
        except Exception as e:
            console.print(f"[red]Plugin init failed: {e}[/]")
            await sqlite.close()
            return

        # Build context
        context = MarketContext(
            market_id=market.id,
            question=market.question,
            description=market.description,
            current_yes_price=market.yes_price or 0.5,
            current_no_price=1 - (market.yes_price or 0.5),
            spread=0.02,
            volume_24h=market.volume_24h,
            liquidity=market.liquidity,
            end_date=market.end_date.isoformat() if market.end_date else None,
            hours_remaining=(
                (market.end_date - datetime.utcnow()).total_seconds() / 3600
                if market.end_date
                else None
            ),
            tags=market.tags,
        )

        # Get prediction
        console.print(f"[bold]Using plugin:[/] {plugin}")
        with console.status("[bold green]Generating prediction..."):
            prediction = await plugin_instance.predict(context)

        await plugin_instance.shutdown()
        await sqlite.close()

        # Display results
        market_price = market.yes_price or 0.5
        edge = prediction.yes_probability - market_price

        console.print("\n[bold]Prediction Results:[/]")
        console.print(f"  Market Price:  {market_price*100:.1f}%")
        console.print(f"  Predicted:     {prediction.yes_probability*100:.1f}%")
        console.print(f"  Confidence:    {prediction.confidence*100:.0f}%")
        console.print(f"  Edge:          {edge*100:+.2f}%")
        console.print()

        if prediction.reasoning:
            console.print(f"[bold]Reasoning:[/] {prediction.reasoning}")
            console.print()

        # Recommendation
        if edge > 0.05:
            console.print("[bold green]Recommendation: BUY YES[/]")
        elif edge < -0.05:
            console.print("[bold red]Recommendation: BUY NO[/]")
        else:
            console.print("[bold yellow]Recommendation: HOLD[/]")

    asyncio.run(run_prediction())


@ai.command("scan")
@click.option("--plugin", "-p", default="simple_heuristic", help="Plugin to use")
@click.option("--min-edge", default=0.05, help="Minimum edge threshold")
@click.option("--limit", default=20, help="Number of markets to scan")
def scan_opportunities(plugin: str, min_edge: float, limit: int) -> None:
    """Scan markets for AI-predicted opportunities."""
    import json
    from datetime import datetime
    from polybot.plugins.example_plugin import get_all_plugins
    from polybot.plugins.base import MarketContext
    from polybot.db.sqlite_store import SQLiteStore

    async def run_scan() -> None:
        plugins = get_all_plugins()

        if plugin not in plugins:
            console.print(f"[red]Plugin not found: {plugin}[/]")
            return

        sqlite = SQLiteStore()
        await sqlite.connect()

        markets = await sqlite.get_active_markets(limit=limit)

        if not markets:
            console.print("[yellow]No active markets found[/]")
            await sqlite.close()
            return

        console.print(f"Scanning {len(markets)} markets with [cyan]{plugin}[/] plugin...")

        plugin_instance = plugins[plugin]()
        await plugin_instance.initialize({})

        opportunities = []

        with console.status("[bold green]Analyzing markets..."):
            for market in markets:
                context = MarketContext(
                    market_id=market.id,
                    question=market.question,
                    description=market.description,
                    current_yes_price=market.yes_price or 0.5,
                    current_no_price=1 - (market.yes_price or 0.5),
                    spread=0.02,
                    volume_24h=market.volume_24h,
                    liquidity=market.liquidity,
                    end_date=market.end_date.isoformat() if market.end_date else None,
                    hours_remaining=(
                        (market.end_date - datetime.utcnow()).total_seconds() / 3600
                        if market.end_date
                        else None
                    ),
                    tags=market.tags,
                )

                try:
                    pred = await plugin_instance.predict(context)
                    market_price = market.yes_price or 0.5
                    edge = pred.yes_probability - market_price

                    if abs(edge) >= min_edge:
                        opportunities.append({
                            "market": market,
                            "prediction": pred,
                            "edge": edge,
                        })
                except Exception:
                    pass

        await plugin_instance.shutdown()
        await sqlite.close()

        if not opportunities:
            console.print(f"[yellow]No opportunities found with edge >= {min_edge*100:.0f}%[/]")
            return

        # Sort by absolute edge
        opportunities.sort(key=lambda x: abs(x["edge"]), reverse=True)

        table = Table(title=f"AI Opportunities (edge >= {min_edge*100:.0f}%)")
        table.add_column("Edge", style="green")
        table.add_column("Conf", style="cyan")
        table.add_column("Action", style="bold")
        table.add_column("Market", max_width=50)
        table.add_column("Price", style="dim")

        for opp in opportunities[:15]:
            edge = opp["edge"]
            pred = opp["prediction"]
            market = opp["market"]

            action = "BUY YES" if edge > 0 else "BUY NO"
            action_style = "green" if edge > 0 else "red"

            table.add_row(
                f"{edge*100:+.1f}%",
                f"{pred.confidence*100:.0f}%",
                f"[{action_style}]{action}[/]",
                market.question[:47] + "...",
                f"{(market.yes_price or 0.5)*100:.0f}%",
            )

        console.print(table)
        console.print(f"\n[dim]Found {len(opportunities)} opportunities[/]")

    asyncio.run(run_scan())


# =============================================================================
# MCP Commands
# =============================================================================


@cli.group()
def mcp() -> None:
    """MCP server and AI agent management."""
    pass


@mcp.command("start")
@click.option("--host", default=None, help="Host to bind to")
@click.option("--port", default=None, type=int, help="Port to bind to")
def mcp_start(host: Optional[str], port: Optional[int]) -> None:
    """Start the MCP server."""
    from polybot.mcp.server import run_mcp_server

    settings = get_settings()

    if not settings.mcp.enabled:
        console.print("[red]MCP server is disabled. Set MCP_ENABLED=true to enable.[/]")
        sys.exit(1)

    console.print(f"[bold green]Starting MCP server...[/]")
    console.print(f"[dim]Mode: {settings.mcp.ai_trading_mode}[/]")
    console.print(f"[dim]Approval required: {settings.mcp.require_approval}[/]")

    asyncio.run(run_mcp_server())


@mcp.command("status")
def mcp_status() -> None:
    """Show MCP server status, mode, and pending approvals."""
    from polybot.mcp.approval import get_pending_approvals
    from polybot.mcp.audit import get_audit_stats

    settings = get_settings()

    console.print("[bold]MCP Server Status[/]\n")

    # Configuration
    console.print("[cyan]Configuration:[/]")
    console.print(f"  Enabled: {'[green]Yes[/]' if settings.mcp.enabled else '[red]No[/]'}")
    console.print(f"  AI Trading Mode: [bold]{settings.mcp.ai_trading_mode}[/]")
    console.print(f"  Require Approval: {'Yes' if settings.mcp.require_approval else 'No'}")
    console.print(f"  Max Position USD: ${settings.mcp.max_position_usd}")
    console.print(f"  Daily Loss Limit: ${settings.mcp.daily_loss_limit_usd}")

    # Pending approvals
    pending = get_pending_approvals()
    console.print(f"\n[cyan]Pending Approvals:[/] {len(pending)}")
    if pending:
        for p in pending[:5]:
            console.print(f"  [{p['id']}] {p['order_type']} - ${p['arguments'].get('size', 'N/A')}")

    # Audit stats
    stats = get_audit_stats(days=7)
    console.print(f"\n[cyan]Activity (7 days):[/]")
    console.print(f"  Total Actions: {stats['total_actions']}")
    console.print(f"  Errors: {stats['errors']}")


@mcp.command("mode")
@click.argument("mode", type=click.Choice(["disabled", "shadow", "live"]))
def mcp_set_mode(mode: str) -> None:
    """Set AI trading mode (disabled, shadow, or live).

    Note: This updates the runtime setting. For persistent change,
    set MCP_AI_TRADING_MODE in your .env file.
    """
    console.print(f"[yellow]Setting AI trading mode to: {mode}[/]")
    console.print("[dim]Note: This is a runtime change. Update MCP_AI_TRADING_MODE in .env for persistence.[/]")

    # Update runtime setting
    settings = get_settings()
    settings.mcp.ai_trading_mode = mode  # type: ignore

    if mode == "live":
        console.print("[bold red]WARNING: Live trading mode enabled![/]")
        if settings.mcp.require_approval:
            console.print("[dim]Trades will require approval.[/]")
        else:
            console.print("[bold red]Approval is DISABLED - trades will execute immediately![/]")


@mcp.command("approve")
@click.argument("approval_id")
def mcp_approve(approval_id: str) -> None:
    """Approve a pending AI trade."""
    from polybot.mcp.approval import approve_trade

    async def do_approve() -> None:
        try:
            result = await approve_trade(approval_id, approved_by="cli_operator")
            console.print(f"[green]Approved: {approval_id}[/]")
            if result.get("execution_result"):
                console.print(f"[dim]Execution result: {result['execution_result']}[/]")
        except ValueError as e:
            console.print(f"[red]Error: {e}[/]")

    asyncio.run(do_approve())


@mcp.command("reject")
@click.argument("approval_id")
@click.option("--reason", "-r", default="Rejected by operator", help="Rejection reason")
def mcp_reject(approval_id: str, reason: str) -> None:
    """Reject a pending AI trade."""
    from polybot.mcp.approval import reject_trade

    async def do_reject() -> None:
        try:
            await reject_trade(approval_id, reason=reason, rejected_by="cli_operator")
            console.print(f"[yellow]Rejected: {approval_id}[/]")
            console.print(f"[dim]Reason: {reason}[/]")
        except ValueError as e:
            console.print(f"[red]Error: {e}[/]")

    asyncio.run(do_reject())


@mcp.command("pending")
def mcp_pending() -> None:
    """List pending AI trade approvals."""
    from polybot.mcp.approval import get_pending_approvals

    pending = get_pending_approvals()

    if not pending:
        console.print("[dim]No pending approvals[/]")
        return

    table = Table(title="Pending Approvals")
    table.add_column("ID", style="cyan")
    table.add_column("Type")
    table.add_column("Size", style="green")
    table.add_column("Market")
    table.add_column("Expires")
    table.add_column("Reason")

    for p in pending:
        args = p["arguments"]
        expires_in = (p["expires_at"] - asyncio.get_event_loop().time()).total_seconds() if hasattr(p["expires_at"], "total_seconds") else "?"

        table.add_row(
            p["id"],
            p["order_type"],
            f"${args.get('size', 'N/A')}",
            args.get("market_id", "N/A")[:20] + "...",
            f"{expires_in}s" if isinstance(expires_in, (int, float)) else str(p["expires_at"])[:16],
            args.get("reason", "")[:30],
        )

    console.print(table)


@mcp.command("audit")
@click.option("--tail", "-n", default=20, help="Number of recent entries to show")
@click.option("--agent", "-a", default=None, help="Filter by agent ID")
def mcp_audit(tail: int, agent: Optional[str]) -> None:
    """View AI agent audit log."""
    from polybot.mcp.audit import get_audit_logs

    logs = get_audit_logs(tail=tail, agent_id=agent)

    if not logs:
        console.print("[dim]No audit log entries found[/]")
        return

    table = Table(title=f"AI Agent Audit Log (last {tail})")
    table.add_column("Time", style="dim")
    table.add_column("Action", style="cyan")
    table.add_column("Tool")
    table.add_column("Details")

    for entry in logs:
        ts = entry.get("timestamp", "?")[:19]
        action = entry.get("action", "?")
        tool = entry.get("tool", "?")
        args = entry.get("arguments", {})

        # Create a brief summary of arguments
        details = []
        if args.get("market_id"):
            details.append(f"market:{args['market_id'][:12]}...")
        if args.get("size"):
            details.append(f"${args['size']}")
        if args.get("strategy"):
            details.append(f"strat:{args['strategy']}")

        table.add_row(ts, action, tool, " ".join(details)[:40])

    console.print(table)


# =============================================================================
# Main Entry Point
# =============================================================================


def main() -> None:
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()
