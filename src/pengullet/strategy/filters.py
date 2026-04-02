"""Filters to discard low-quality or risky opportunities."""

from __future__ import annotations

from decimal import Decimal

import structlog

from pengullet.config.settings import Settings
from pengullet.market.models import ScoredOpportunity

logger = structlog.get_logger(__name__)


class OpportunityFilter:
    """Applies configurable filters to scored opportunities.

    Filters out opportunities that don't meet minimum thresholds
    for profitability, liquidity, or other risk criteria.
    """

    def __init__(self, settings: Settings) -> None:
        self._min_profit = settings.min_profit_threshold
        self._min_liquidity = Decimal("5.0")  # minimum shares available
        self._min_spread_ratio = Decimal("0.001")  # 0.1% minimum profit margin

    def apply(self, opportunities: list[ScoredOpportunity]) -> list[ScoredOpportunity]:
        filtered: list[ScoredOpportunity] = []
        for opp in opportunities:
            if self._passes(opp):
                filtered.append(opp)

        removed = len(opportunities) - len(filtered)
        if removed > 0:
            logger.info("filter.applied", passed=len(filtered), removed=removed)
        return filtered

    def _passes(self, opp: ScoredOpportunity) -> bool:
        if opp.net_profit < self._min_profit:
            logger.debug(
                "filter.rejected.low_profit",
                net_profit=float(opp.net_profit),
                threshold=float(self._min_profit),
            )
            return False

        if opp.candidate.max_shares < self._min_liquidity:
            logger.debug(
                "filter.rejected.low_liquidity",
                max_shares=float(opp.candidate.max_shares),
                threshold=float(self._min_liquidity),
            )
            return False

        if opp.candidate.total_cost > Decimal("0"):
            margin = opp.candidate.profit_per_share / opp.candidate.total_cost
            if margin < self._min_spread_ratio:
                logger.debug("filter.rejected.thin_margin", margin=float(margin))
                return False

        return True
