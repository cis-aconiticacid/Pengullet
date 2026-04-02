"""Wallet management and transaction signing for Polygon/Polymarket."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import structlog

from pengullet.config.settings import Settings

logger = structlog.get_logger(__name__)


class WalletManager:
    """Manages the trading wallet: balance queries, allowances, and signing.

    Uses the py-clob-client SDK for EIP-712 order signing and the web3
    library for on-chain balance checks.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._private_key = settings.polymarket_private_key
        self._clob_client: Any = None

    async def initialize(self) -> None:
        """Lazily initialize the CLOB client with API credentials."""
        if self._clob_client is not None:
            return

        try:
            from py_clob_client.client import ClobClient

            self._clob_client = ClobClient(
                self._settings.polymarket_api_url,
                key=self._private_key,
                chain_id=self._settings.chain_id,
                creds={
                    "apiKey": self._settings.polymarket_api_key,
                    "secret": self._settings.polymarket_api_secret,
                    "passphrase": self._settings.polymarket_api_passphrase,
                },
            )
            logger.info("wallet.initialized")
        except ImportError:
            logger.warning("wallet.py_clob_client_not_installed")
        except Exception:
            logger.exception("wallet.init_failed")

    @property
    def clob_client(self) -> Any:
        return self._clob_client

    @property
    def is_ready(self) -> bool:
        return self._clob_client is not None

    async def get_usdc_balance(self) -> Decimal:
        """Query on-chain USDC balance on Polygon."""
        if not self._clob_client:
            return Decimal("0")
        try:
            # py-clob-client exposes balance helpers
            bal = self._clob_client.get_balance()
            return Decimal(str(bal))
        except Exception:
            logger.exception("wallet.balance_query_failed")
            return Decimal("0")
