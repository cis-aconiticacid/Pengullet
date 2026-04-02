"""Profit evaluation for arbitrage candidates."""

from __future__ import annotations

from decimal import Decimal

import structlog

from pengullet.config.settings import Settings
from pengullet.market.models import ArbitrageCandidate, ScoredOpportunity

logger = structlog.get_logger(__name__)

# Polymarket trading fee: currently ~2% on winnings
DEFAULT_FEE_RATE = Decimal("0.02")

# Polygon L2 gas is negligible but we account for a small fixed cost
DEFAULT_GAS_FEE = Decimal("0.005")


class Evaluator:
    """Evaluates arbitrage candidates, accounting for fees and slippage."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._fee_rate = DEFAULT_FEE_RATE
        self._gas_fee = DEFAULT_GAS_FEE

    def evaluate(self, candidates: list[ArbitrageCandidate]) -> list[ScoredOpportunity]:
        scored: list[ScoredOpportunity] = []
        for candidate in candidates:
            opp = self._score(candidate)
            if opp is not None:
                scored.append(opp)
        scored.sort(key=lambda o: o.net_profit, reverse=True)
        logger.info(
            "evaluation.complete",
            candidates=len(candidates),
            profitable=len(scored),
        )
        return scored

    def _score(self, candidate: ArbitrageCandidate) -> ScoredOpportunity | None:
        max_position = self._settings.max_position_size
        recommended_size = min(candidate.max_shares, max_position / candidate.total_cost)
        recommended_size = max(recommended_size, Decimal("0"))

        if recommended_size <= 0:
            return None

        gross = candidate.profit_per_share * recommended_size

        # Fee is charged on winnings ($1 per share), proportional to outcome count
        trading_fee = self._fee_rate * recommended_size

        slippage = self._estimate_slippage(candidate, recommended_size)

        net = gross - trading_fee - self._gas_fee - slippage

        opp = ScoredOpportunity(
            candidate=candidate,
            gross_profit=gross,
            trading_fee=trading_fee,
            gas_fee=self._gas_fee,
            slippage_estimate=slippage,
            net_profit=net,
            recommended_size=recommended_size,
        )

        if opp.is_profitable:
            logger.debug(
                "evaluation.profitable",
                question=candidate.market.question[:60],
                net_profit=float(net),
                size=float(recommended_size),
            )
        return opp if opp.is_profitable else None

    @staticmethod
    def _estimate_slippage(candidate: ArbitrageCandidate, size: Decimal) -> Decimal:
        """Estimate slippage based on order book depth.

        If the desired size exceeds the best-ask size, we assume we'd
        need to walk the book, incurring additional cost.  This is a
        conservative linear estimate.
        """
        worst_fill_ratio = Decimal("0")
        for ask in candidate.best_asks.values():
            if ask.size > 0:
                ratio = size / ask.size
                if ratio > Decimal("1"):
                    worst_fill_ratio = max(worst_fill_ratio, ratio - Decimal("1"))

        # ~0.5% per unit of overfill across total cost
        slippage = worst_fill_ratio * candidate.total_cost * Decimal("0.005")
        return slippage
