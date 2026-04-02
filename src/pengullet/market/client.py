"""Low-level async client for the Polymarket CLOB API."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import httpx
import structlog

from pengullet.config.settings import Settings
from pengullet.market.models import OrderBook, OrderBookEntry

logger = structlog.get_logger(__name__)


class PolymarketClient:
    """Async wrapper around the Polymarket CLOB REST API.

    Handles authentication, rate limiting, and response parsing for
    market data and order book endpoints.
    """

    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.polymarket_api_url.rstrip("/")
        self._settings = settings
        self._http: httpx.AsyncClient | None = None

    async def _client(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=httpx.Timeout(30.0),
                headers=self._auth_headers(),
            )
        return self._http

    def _auth_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Accept": "application/json"}
        if self._settings.polymarket_api_key:
            headers["POLY_API_KEY"] = self._settings.polymarket_api_key
            headers["POLY_API_SECRET"] = self._settings.polymarket_api_secret
            headers["POLY_PASSPHRASE"] = self._settings.polymarket_api_passphrase
        return headers

    async def close(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()

    # ── Market data ──────────────────────────────────────────────────

    async def get_markets(self, next_cursor: str = "") -> dict[str, Any]:
        """Fetch a page of markets from the CLOB API.

        Returns the raw JSON dict which contains 'data' (list) and
        'next_cursor' (str) for pagination.
        """
        client = await self._client()
        params: dict[str, str] = {}
        if next_cursor:
            params["next_cursor"] = next_cursor

        resp = await client.get("/markets", params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_all_markets(self) -> list[dict[str, Any]]:
        """Page through all active markets."""
        all_markets: list[dict[str, Any]] = []
        cursor = ""

        while True:
            page = await self.get_markets(next_cursor=cursor)
            data = page.get("data", [])
            if not data:
                break
            all_markets.extend(data)

            cursor = page.get("next_cursor", "")
            if not cursor or cursor == "LTE=":
                break

            logger.debug("markets.paginating", cursor=cursor, fetched_so_far=len(all_markets))

        logger.info("markets.fetched_all", total=len(all_markets))
        return all_markets

    # ── Order book ───────────────────────────────────────────────────

    async def get_order_book(self, token_id: str) -> OrderBook:
        """Fetch the order book for a single token."""
        client = await self._client()
        resp = await client.get("/book", params={"token_id": token_id})
        resp.raise_for_status()
        data = resp.json()
        return self._parse_order_book(token_id, data)

    async def get_prices(self, token_ids: list[str]) -> dict[str, Decimal]:
        """Fetch mid-market prices for multiple tokens."""
        client = await self._client()
        ids_param = ",".join(token_ids)
        resp = await client.get("/prices", params={"token_ids": ids_param})
        resp.raise_for_status()
        raw: dict[str, str] = resp.json()
        return {tid: Decimal(str(price)) for tid, price in raw.items()}

    # ── Parsing helpers ──────────────────────────────────────────────

    @staticmethod
    def _parse_order_book(token_id: str, data: dict[str, Any]) -> OrderBook:
        asks = [
            OrderBookEntry(price=Decimal(str(e["price"])), size=Decimal(str(e["size"])))
            for e in data.get("asks", [])
        ]
        bids = [
            OrderBookEntry(price=Decimal(str(e["price"])), size=Decimal(str(e["size"])))
            for e in data.get("bids", [])
        ]
        return OrderBook(token_id=token_id, asks=asks, bids=bids)
