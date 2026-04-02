from decimal import Decimal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Polymarket CLOB API
    polymarket_api_url: str = "https://clob.polymarket.com"
    polymarket_private_key: str = ""
    polymarket_api_key: str = ""
    polymarket_api_secret: str = ""
    polymarket_api_passphrase: str = ""

    # Chain config
    chain_id: int = 137
    rpc_url: str = "https://polygon-rpc.com"

    # Trading parameters
    min_profit_threshold: Decimal = Field(default=Decimal("0.005"))
    max_position_size: Decimal = Field(default=Decimal("50.0"))
    max_total_exposure: Decimal = Field(default=Decimal("500.0"))
    scan_interval_seconds: int = 10

    # Notifications
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    discord_webhook_url: str = ""

    # Logging
    log_level: str = "INFO"
