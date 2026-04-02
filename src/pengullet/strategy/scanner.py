"""Arbitrage opportunity scanner for Polymarket markets."""

from __future__ import annotations

from decimal import Decimal

import structlog

from pengullet.market.models import ArbitrageCandidate, Market, OrderBookEntry

logger = structlog.get_logger(__name__)


class ArbitrageScanner:
    """Scans markets for arbitrage opportunities.

    For each market, checks whether buying the best ask of every
    outcome token costs less than $1.00 (the guaranteed payout).
    If so, the difference is risk-free profit.
    """

    def scan(self, markets: list[Market]) -> list[ArbitrageCandidate]:
        candidates: list[ArbitrageCandidate] = []

        for market in markets:
            candidate = self._check_market(market)
            if candidate is not None:
                candidates.append(candidate)
                logger.info(
                    "arbitrage.found",
                    question=market.question[:80],
                    total_cost=float(candidate.total_cost),
                    profit_pct=float(candidate.profit_pct),
                    max_shares=float(candidate.max_shares),
                )

        candidates.sort(key=lambda c: c.gross_profit, reverse=True)
        logger.info("scan.complete", markets_scanned=len(markets), candidates=len(candidates))
        return candidates

    def _check_market(self, market: Market) -> ArbitrageCandidate | None:
        """Check a single market for an arbitrage opportunity.

        An opportunity exists when the sum of best-ask prices across
        all outcome tokens is less than 1.0.
        """
        if not market.tokens or len(market.tokens) < 2:
            return None

        best_asks: dict[str, OrderBookEntry] = {}
        for token in market.tokens:
            if token.order_book is None:
                return None
            ask = token.order_book.best_ask
            if ask is None:
                return None
            best_asks[token.outcome] = ask

        if len(best_asks) != len(market.tokens):
            return None

        total_cost = sum(ask.price for ask in best_asks.values())

        if total_cost >= Decimal("1.0"):
            return None

        profit_per_share = Decimal("1.0") - total_cost
        max_shares = min(ask.size for ask in best_asks.values())
        gross_profit = profit_per_share * max_shares

        return ArbitrageCandidate(
            market=market,
            best_asks=best_asks,
            total_cost=total_cost,
            profit_per_share=profit_per_share,
            max_shares=max_shares,
            gross_profit=gross_profit,
        )
