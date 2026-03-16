"""Configuration management for PolyBot.

Uses pydantic-settings for type-safe configuration from environment variables.
"""

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class PolymarketCredentials(BaseSettings):
    """Polymarket API credentials."""

    model_config = SettingsConfigDict(env_prefix="POLYMARKET_", env_file=".env", extra="ignore")

    private_key: str = Field(default="", description="Wallet private key")
    proxy_address: str = Field(default="", description="Proxy wallet address")
    api_key: str = Field(default="", description="L2 API key")
    api_secret: str = Field(default="", description="L2 API secret")
    api_passphrase: str = Field(default="", description="L2 API passphrase")
    signature_type: int = Field(default=2, description="0=EOA, 1=POLY_PROXY, 2=GNOSIS_SAFE")


class ArbitrageConfig(BaseSettings):
    """Arbitrage strategy configuration.

    Note: 'enabled' is managed via database state, not environment.
    """

    model_config = SettingsConfigDict(env_prefix="ARB_", env_file=".env", extra="ignore")

    min_profit_pct: float = Field(default=0.01, description="Minimum profit percentage")
    poll_interval_sec: float = Field(default=2.0, description="Poll interval in seconds")
    max_position_size: float = Field(default=100.0, description="Max position size in USD")


class StatArbConfig(BaseSettings):
    """Statistical arbitrage strategy configuration.

    Note: 'enabled' is managed via database state, not environment.
    """

    model_config = SettingsConfigDict(env_prefix="STAT_ARB_", env_file=".env", extra="ignore")

    spread_threshold: float = Field(default=0.04, description="Spread threshold to trigger")
    lookback_hours: int = Field(default=24, description="Hours of history for correlation")
    min_correlation: float = Field(default=0.7, description="Minimum correlation coefficient")


class AIModelConfig(BaseSettings):
    """AI model strategy configuration.

    Note: 'enabled' is managed via database state, not environment.
    """

    model_config = SettingsConfigDict(env_prefix="AI_", env_file=".env", extra="ignore")

    model_plugin: str = Field(default="example", alias="AI_MODEL_PLUGIN")
    model_config_json: str = Field(default="{}", alias="AI_MODEL_CONFIG")
    min_confidence: float = Field(default=0.7)
    min_edge: float = Field(default=0.05)


class SpreadFarmConfig(BaseSettings):
    """Spread farming strategy configuration.

    Note: 'enabled' is managed via database state, not environment.
    """

    model_config = SettingsConfigDict(env_prefix="SPREAD_FARM_", env_file=".env", extra="ignore")

    min_spread: float = Field(default=0.02, description="Minimum spread to farm")
    order_size: float = Field(default=10.0, description="Order size in USD")


class CopyTradeConfig(BaseSettings):
    """Copy trading strategy configuration.

    Note: 'enabled' is managed via database state, not environment.
    """

    model_config = SettingsConfigDict(env_prefix="COPY_TRADE_", env_file=".env", extra="ignore")

    min_whale_balance: float = Field(default=100000.0, description="Min balance to track")
    proportional_size: float = Field(default=0.01, description="Proportion of whale trade")


class RiskConfig(BaseSettings):
    """Risk management configuration."""

    model_config = SettingsConfigDict(env_prefix="RISK_", env_file=".env", extra="ignore")

    # Existing limits
    max_position_size_usd: float = Field(default=1000.0)
    max_total_exposure_usd: float = Field(default=10000.0)
    daily_loss_limit_usd: float = Field(default=500.0)
    max_open_orders: int = Field(default=50)

    # Multi-venue limits
    max_venue_exposure_usd: float = Field(default=5000.0, description="Max exposure per venue")
    max_venue_concentration: float = Field(default=0.7, description="Max % in one venue")

    # Delta/hedging
    max_delta: float = Field(default=500.0, description="Max net delta in USD")
    hedge_delta_threshold: float = Field(default=100.0, description="Delta to trigger hedge")
    auto_hedge_enabled: bool = Field(default=False, description="Enable automatic hedging")

    # Monitoring
    snapshot_interval_sec: int = Field(default=30, description="Risk snapshot interval")
    alert_exposure_threshold: float = Field(default=0.8, description="Alert at % of limit")


class VenuesConfig(BaseSettings):
    """Venue enable/disable configuration."""

    model_config = SettingsConfigDict(env_prefix="VENUES_", env_file=".env", extra="ignore")

    polymarket_enabled: bool = Field(default=True)
    binance_enabled: bool = Field(default=False)
    kalshi_enabled: bool = Field(default=False, description="Requires compliance review")
    opinion_enabled: bool = Field(default=False, description="DEX - chain risk")


class BinanceConfig(BaseSettings):
    """Binance exchange configuration."""

    model_config = SettingsConfigDict(env_prefix="BINANCE_", env_file=".env", extra="ignore")

    api_key: str = Field(default="")
    api_secret: str = Field(default="")
    testnet: bool = Field(default=True, description="Use testnet for safety")

    # Market types to enable
    spot_enabled: bool = Field(default=True)
    futures_enabled: bool = Field(default=False)
    options_enabled: bool = Field(default=False)

    # Rate limits
    requests_per_minute: int = Field(default=1200)
    orders_per_second: int = Field(default=10)


class KalshiConfig(BaseSettings):
    """Kalshi exchange configuration."""

    model_config = SettingsConfigDict(env_prefix="KALSHI_", env_file=".env", extra="ignore")

    api_key: str = Field(default="")
    api_secret: str = Field(default="")
    environment: str = Field(default="demo", description="demo or prod")
    compliance_approved: bool = Field(default=False, description="Must be True for live trading")


class OpinionConfig(BaseSettings):
    """Opinion protocol configuration."""

    model_config = SettingsConfigDict(env_prefix="OPINION_", env_file=".env", extra="ignore")

    rpc_url: str = Field(default="")
    private_key: str = Field(default="")
    chain_id: int = Field(default=1)


class DatabaseConfig(BaseSettings):
    """Database configuration."""

    model_config = SettingsConfigDict(env_prefix="", env_file=".env", extra="ignore")

    sqlite_path: Path = Field(default=Path("./data/polybot.db"))
    duckdb_path: Path = Field(default=Path("./data/analytics.duckdb"))
    strategy_logs_path: Path = Field(default=Path("./data/strategy_logs.duckdb"))

    @field_validator("sqlite_path", "duckdb_path", "strategy_logs_path", mode="before")
    @classmethod
    def ensure_path(cls, v: str | Path) -> Path:
        return Path(v)


class APIConfig(BaseSettings):
    """API server configuration."""

    model_config = SettingsConfigDict(env_prefix="API_", env_file=".env", extra="ignore")

    host: str = Field(default="127.0.0.1")
    port: int = Field(default=8000)
    reload: bool = Field(default=False)


class NNGConfig(BaseSettings):
    """NNG messaging configuration."""

    model_config = SettingsConfigDict(env_prefix="NNG_", env_file=".env", extra="ignore")

    ipc_path: str = Field(default="/tmp/polybot")
    recv_timeout_ms: int = Field(default=1000)

    @property
    def prices_address(self) -> str:
        return f"ipc://{self.ipc_path}/prices.pub"

    @property
    def events_address(self) -> str:
        return f"ipc://{self.ipc_path}/events.pub"

    def service_events_address(self, service_name: str) -> str:
        """Get service-specific events address.

        Each service needs its own event publisher address to avoid
        'Address in use' conflicts when multiple services run concurrently.
        """
        return f"ipc://{self.ipc_path}/{service_name}_events.pub"

    @property
    def executor_address(self) -> str:
        return f"ipc://{self.ipc_path}/executor.req"

    @property
    def analytics_address(self) -> str:
        return f"ipc://{self.ipc_path}/analytics.req"

    @property
    def state_address(self) -> str:
        return f"ipc://{self.ipc_path}/state.req"

    @property
    def signals_address(self) -> str:
        return f"ipc://{self.ipc_path}/signals.push"

    @property
    def strategy_logs_address(self) -> str:
        return f"ipc://{self.ipc_path}/strategy_logs.req"

    @property
    def strategy_runner_address(self) -> str:
        return f"ipc://{self.ipc_path}/strategy_runner.req"

    # Multi-venue addresses
    @property
    def binance_prices_address(self) -> str:
        return f"ipc://{self.ipc_path}/binance_prices.pub"

    @property
    def binance_spot_prices_address(self) -> str:
        return f"ipc://{self.ipc_path}/binance_spot_prices.pub"

    @property
    def binance_futures_prices_address(self) -> str:
        return f"ipc://{self.ipc_path}/binance_futures_prices.pub"

    @property
    def mapping_address(self) -> str:
        return f"ipc://{self.ipc_path}/mapping.req"

    @property
    def risk_address(self) -> str:
        return f"ipc://{self.ipc_path}/risk.req"


class LogConfig(BaseSettings):
    """Logging configuration."""

    model_config = SettingsConfigDict(env_prefix="LOG_", env_file=".env", extra="ignore")

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(default="INFO")
    format: Literal["json", "text"] = Field(default="json")


class AuthConfig(BaseSettings):
    """API authentication configuration."""

    model_config = SettingsConfigDict(env_prefix="AUTH_", env_file=".env", extra="ignore")

    enabled: bool = Field(default=True, description="Enable API authentication")
    jwt_secret: str = Field(default="", description="JWT signing secret (required in production)")
    jwt_algorithm: str = Field(default="HS256", description="JWT algorithm")
    jwt_expire_minutes: int = Field(default=60, description="JWT token expiration in minutes")
    api_keys_hash: str = Field(
        default="", description="Comma-separated SHA256 hashes of valid API keys"
    )


class CORSConfig(BaseSettings):
    """CORS configuration."""

    model_config = SettingsConfigDict(env_prefix="CORS_", env_file=".env", extra="ignore")

    allowed_origins: str = Field(
        default="http://localhost:3000,http://localhost:5173",
        description="Comma-separated allowed origins",
    )
    allow_credentials: bool = Field(default=True, description="Allow credentials in CORS")
    allow_methods: str = Field(
        default="GET,POST,PUT,DELETE,OPTIONS", description="Allowed HTTP methods"
    )
    allow_headers: str = Field(
        default="Authorization,X-API-Key,Content-Type,Accept",
        description="Allowed headers",
    )


class Settings(BaseSettings):
    """Main settings aggregating all configuration sections."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Nested configurations
    polymarket: PolymarketCredentials = Field(default_factory=PolymarketCredentials)
    arbitrage: ArbitrageConfig = Field(default_factory=ArbitrageConfig)
    stat_arb: StatArbConfig = Field(default_factory=StatArbConfig)
    ai_model: AIModelConfig = Field(default_factory=AIModelConfig)
    spread_farm: SpreadFarmConfig = Field(default_factory=SpreadFarmConfig)
    copy_trade: CopyTradeConfig = Field(default_factory=CopyTradeConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    nng: NNGConfig = Field(default_factory=NNGConfig)
    log: LogConfig = Field(default_factory=LogConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)
    cors: CORSConfig = Field(default_factory=CORSConfig)

    # Multi-venue configurations
    venues: VenuesConfig = Field(default_factory=VenuesConfig)
    binance: BinanceConfig = Field(default_factory=BinanceConfig)
    kalshi: KalshiConfig = Field(default_factory=KalshiConfig)
    opinion: OpinionConfig = Field(default_factory=OpinionConfig)

    # External API keys
    perplexity_api_key: str = Field(default="", alias="PERPLEXITY_API_KEY")
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")

    # API base URLs (constants)
    clob_base_url: str = "https://clob.polymarket.com"
    gamma_base_url: str = "https://gamma-api.polymarket.com"
    data_base_url: str = "https://data-api.polymarket.com"
    ws_base_url: str = "wss://ws-subscriptions-clob.polymarket.com/ws"
    chain_id: int = 137  # Polygon mainnet


# Global settings instance
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get the global settings instance, creating it if necessary."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """Force reload settings from environment."""
    global _settings
    _settings = Settings()
    return _settings
