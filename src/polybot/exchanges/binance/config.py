"""Binance API configuration."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class BinanceSpotConfig(BaseSettings):
    """Binance Spot API configuration."""

    model_config = SettingsConfigDict(
        env_prefix="BINANCE_SPOT_", env_file=".env", extra="ignore"
    )

    api_key: str = Field(default="")
    api_secret: str = Field(default="")
    testnet: bool = Field(default=True)
    recv_window: int = Field(default=5000)

    # REST endpoints
    base_url: str = Field(default="https://api.binance.com")
    testnet_url: str = Field(default="https://testnet.binance.vision")

    # WebSocket endpoints
    ws_url: str = Field(default="wss://stream.binance.com:9443/ws")
    testnet_ws_url: str = Field(default="wss://testnet.binance.vision/ws")

    @property
    def rest_url(self) -> str:
        """Get REST URL based on testnet setting."""
        return self.testnet_url if self.testnet else self.base_url

    @property
    def websocket_url(self) -> str:
        """Get WebSocket URL based on testnet setting."""
        return self.testnet_ws_url if self.testnet else self.ws_url


class BinanceFuturesConfig(BaseSettings):
    """Binance USDM Perpetual Futures configuration."""

    model_config = SettingsConfigDict(
        env_prefix="BINANCE_FUTURES_", env_file=".env", extra="ignore"
    )

    api_key: str = Field(default="")
    api_secret: str = Field(default="")
    testnet: bool = Field(default=True)
    recv_window: int = Field(default=5000)

    # USDM Futures endpoints
    base_url: str = Field(default="https://fapi.binance.com")
    testnet_url: str = Field(default="https://testnet.binancefuture.com")
    ws_url: str = Field(default="wss://fstream.binance.com/ws")
    testnet_ws_url: str = Field(default="wss://stream.binancefuture.com/ws")

    # Position mode
    hedge_mode: bool = Field(default=False, description="True for hedge mode")
    default_leverage: int = Field(default=10)

    @property
    def rest_url(self) -> str:
        """Get REST URL based on testnet setting."""
        return self.testnet_url if self.testnet else self.base_url

    @property
    def websocket_url(self) -> str:
        """Get WebSocket URL based on testnet setting."""
        return self.testnet_ws_url if self.testnet else self.ws_url


class BinanceOptionsConfig(BaseSettings):
    """Binance Options (VOPTIONS) configuration."""

    model_config = SettingsConfigDict(
        env_prefix="BINANCE_OPTIONS_", env_file=".env", extra="ignore"
    )

    api_key: str = Field(default="")
    api_secret: str = Field(default="")
    testnet: bool = Field(default=True)

    base_url: str = Field(default="https://eapi.binance.com")
    ws_url: str = Field(default="wss://nbstream.binance.com/eoptions")

    @property
    def rest_url(self) -> str:
        """Get REST URL (no testnet for options)."""
        return self.base_url

    @property
    def websocket_url(self) -> str:
        """Get WebSocket URL."""
        return self.ws_url
