"""High-level market data fetcher with caching."""

from __future__ import annotations

import asyncio
import time
from decimal import Decimal
from typing import Any

import structlog

from pengullet.config.settings import Settings
from pengullet.market.client import PolymarketClient
from pengullet.market.models import Market, OrderBook, Token

logger = structlog.get_logger(__name__)


class MarketFetcher:
    """Fetches and assembles Market objects with order book data.

    Maintains an in-memory cache of markets and order books to avoid
    redundant API calls within the same scan cycle.
    """

    def __init__(self, client: PolymarketClient, settings: Settings) -> None:
        self._client = client
        self._settings = settings
        self._market_cache: list[Market] = []
        self._market_cache_ts: float = 0.0
        self._market_cache_ttl: float = 60.0  # re-fetch market list every 60s

    async def fetch_active_markets(self) -> list[Market]:
        """Fetch all active, tradeable markets.

        Uses a TTL cache for the market list itself. Order books are
        always refreshed.
        """
        now = time.monotonic()
        if self._market_cache and (now - self._market_cache_ts) < self._market_cache_ttl:
            markets = self._market_cache
        else:
            raw_markets = await self._client.get_all_markets()
            markets = self._parse_markets(raw_markets)
            self._market_cache = markets
            self._market_cache_ts = now
            logger.info("markets.refreshed", count=len(markets))

        tradeable = [m for m in markets if m.is_tradeable]
        logger.info("markets.tradeable", count=len(tradeable))
        return tradeable

    async def enrich_with_order_books(
        self,
        markets: list[Market],
        concurrency: int = 20,
    ) -> list[Market]:
        """Fetch order books for all tokens in parallel and attach them."""
        semaphore = asyncio.Semaphore(concurrency)

        async def fetch_book(token: Token) -> tuple[str, OrderBook]:
            async with semaphore:
                book = await self._client.get_order_book(token.token_id)
                return token.token_id, book

        tasks = []
        for market in markets:
            for token in market.tokens:
                tasks.append(fetch_book(token))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        book_map: dict[str, OrderBook] = {}
        for result in results:
            if isinstance(result, Exception):
                logger.warning("orderbook.fetch_failed", error=str(result))
                continue
            token_id, book = result
            book_map[token_id] = book

        enriched: list[Market] = []
        for market in markets:
            tokens_with_books: list[Token] = []
            for token in market.tokens:
                book = book_map.get(token.token_id)
                updated = token.model_copy(update={"order_book": book})
                tokens_with_books.append(updated)

            updated_market = market.model_copy(update={"tokens": tokens_with_books})
            enriched.append(updated_market)

        fetched_count = sum(1 for r in results if not isinstance(r, Exception))
        failed_count = len(results) - fetched_count
        logger.info("orderbooks.enriched", fetched=fetched_count, failed=failed_count)
        return enriched

    # ── Parsing helpers ──────────────────────────────────────────────

    @staticmethod
    def _parse_markets(raw_markets: list[dict[str, Any]]) -> list[Market]:
        markets: list[Market] = []
        for raw in raw_markets:
            tokens: list[Token] = []
            for t in raw.get("tokens", []):
                token_id = t.get("token_id", "")
                outcome = t.get("outcome", "")
                price_str = t.get("price")
                price = Decimal(str(price_str)) if price_str is not None else None
                tokens.append(Token(token_id=token_id, outcome=outcome, price=price))

            market = Market(
                condition_id=raw.get("condition_id", ""),
                question=raw.get("question", ""),
                slug=raw.get("market_slug", ""),
                active=raw.get("active", True),
                closed=raw.get("closed", False),
                tokens=tokens,
            )
            markets.append(market)
        return markets
