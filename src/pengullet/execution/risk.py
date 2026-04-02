"""Risk management: position limits, cooldowns, and circuit breakers."""

from __future__ import annotations

import time
from decimal import Decimal

import structlog

from pengullet.config.settings import Settings
from pengullet.market.models import ScoredOpportunity

logger = structlog.get_logger(__name__)


class RiskManager:
    """Enforces risk limits before order execution.

    Tracks open exposure, per-market cooldowns, and consecutive losses
    to prevent runaway risk.
    """

    def __init__(self, settings: Settings) -> None:
        self._max_position = settings.max_position_size
        self._max_exposure = settings.max_total_exposure
        self._cooldown_seconds: float = 120.0
        self._max_consecutive_losses: int = 5

        self._current_exposure = Decimal("0")
        self._market_last_trade: dict[str, float] = {}
        self._consecutive_losses: int = 0
        self._halted = False

    @property
    def is_halted(self) -> bool:
        return self._halted

    def check(self, opp: ScoredOpportunity) -> bool:
        """Return True if the opportunity passes all risk checks."""
        if self._halted:
            logger.warning("risk.halted", reason="circuit_breaker")
            return False

        market_id = opp.candidate.market.condition_id
        trade_cost = opp.recommended_size * opp.candidate.total_cost

        if trade_cost > self._max_position:
            logger.info("risk.rejected.position_too_large", cost=float(trade_cost))
            return False

        if self._current_exposure + trade_cost > self._max_exposure:
            logger.info(
                "risk.rejected.exposure_limit",
                current=float(self._current_exposure),
                additional=float(trade_cost),
            )
            return False

        last_trade = self._market_last_trade.get(market_id, 0.0)
        if time.monotonic() - last_trade < self._cooldown_seconds:
            logger.info("risk.rejected.cooldown", market_id=market_id)
            return False

        return True

    def record_trade(self, opp: ScoredOpportunity) -> None:
        market_id = opp.candidate.market.condition_id
        trade_cost = opp.recommended_size * opp.candidate.total_cost
        self._current_exposure += trade_cost
        self._market_last_trade[market_id] = time.monotonic()
        self._consecutive_losses = 0
        logger.info("risk.trade_recorded", exposure=float(self._current_exposure))

    def record_loss(self) -> None:
        self._consecutive_losses += 1
        if self._consecutive_losses >= self._max_consecutive_losses:
            self._halted = True
            logger.error(
                "risk.circuit_breaker_triggered",
                consecutive_losses=self._consecutive_losses,
            )

    def record_settlement(self, amount: Decimal) -> None:
        """Reduce exposure when a position settles."""
        self._current_exposure = max(Decimal("0"), self._current_exposure - amount)
        logger.info("risk.settlement", exposure=float(self._current_exposure))

    def reset(self) -> None:
        self._halted = False
        self._consecutive_losses = 0
        logger.info("risk.reset")
