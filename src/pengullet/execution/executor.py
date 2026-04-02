"""Order execution engine for Polymarket CLOB trades."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any

import structlog

from pengullet.execution.risk import RiskManager
from pengullet.execution.wallet import WalletManager
from pengullet.market.models import ScoredOpportunity

logger = structlog.get_logger(__name__)


class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"


@dataclass
class OrderResult:
    success: bool
    order_id: str = ""
    token_id: str = ""
    side: str = ""
    price: float = 0.0
    size: float = 0.0
    error: str = ""


class OrderExecutor:
    """Places arbitrage orders via the Polymarket CLOB.

    For each opportunity, places BUY limit orders on every outcome
    token at the best-ask price. All legs must fill for the arbitrage
    to be complete.
    """

    def __init__(
        self,
        wallet: WalletManager,
        risk_manager: RiskManager,
        *,
        dry_run: bool = True,
    ) -> None:
        self._wallet = wallet
        self._risk = risk_manager
        self._dry_run = dry_run

    async def execute(self, opp: ScoredOpportunity) -> list[OrderResult]:
        """Execute an arbitrage opportunity by placing orders on all legs."""
        if not self._risk.check(opp):
            return [OrderResult(success=False, error="risk_check_failed")]

        if self._dry_run:
            return self._simulate(opp)

        if not self._wallet.is_ready:
            await self._wallet.initialize()

        if not self._wallet.is_ready:
            return [OrderResult(success=False, error="wallet_not_ready")]

        results: list[OrderResult] = []
        for outcome, ask in opp.candidate.best_asks.items():
            token = self._find_token(opp, outcome)
            if token is None:
                results.append(OrderResult(success=False, error=f"token_not_found:{outcome}"))
                continue

            result = await self._place_order(
                token_id=token.token_id,
                side=OrderSide.BUY,
                price=ask.price,
                size=opp.recommended_size,
            )
            results.append(result)

        all_ok = all(r.success for r in results)
        if all_ok:
            self._risk.record_trade(opp)
            logger.info(
                "execution.success",
                market=opp.candidate.market.question[:60],
                net_profit=float(opp.net_profit),
            )
        else:
            self._risk.record_loss()
            logger.warning(
                "execution.partial_failure",
                results=[r.error for r in results if not r.success],
            )
        return results

    def _simulate(self, opp: ScoredOpportunity) -> list[OrderResult]:
        """Dry-run: log what would be executed without placing real orders."""
        results: list[OrderResult] = []
        for outcome, ask in opp.candidate.best_asks.items():
            logger.info(
                "execution.dry_run",
                outcome=outcome,
                price=float(ask.price),
                size=float(opp.recommended_size),
                market=opp.candidate.market.question[:60],
            )
            results.append(
                OrderResult(
                    success=True,
                    token_id=self._find_token_id(opp, outcome),
                    side=OrderSide.BUY.value,
                    price=float(ask.price),
                    size=float(opp.recommended_size),
                )
            )
        self._risk.record_trade(opp)
        return results

    async def _place_order(
        self,
        token_id: str,
        side: OrderSide,
        price: Decimal,
        size: Decimal,
    ) -> OrderResult:
        """Place a single limit order via py-clob-client."""
        try:
            client: Any = self._wallet.clob_client
            from py_clob_client.order_builder.constants import BUY

            order_args = {
                "token_id": token_id,
                "price": float(price),
                "size": float(size),
                "side": BUY,
            }
            signed_order = client.create_order(order_args)
            resp = client.post_order(signed_order)

            order_id = resp.get("orderID", "")
            logger.info("order.placed", order_id=order_id, token_id=token_id)
            return OrderResult(
                success=True,
                order_id=order_id,
                token_id=token_id,
                side=side.value,
                price=float(price),
                size=float(size),
            )
        except Exception as exc:
            logger.exception("order.failed", token_id=token_id)
            return OrderResult(success=False, token_id=token_id, error=str(exc))

    @staticmethod
    def _find_token(opp: ScoredOpportunity, outcome: str) -> Any:
        for token in opp.candidate.market.tokens:
            if token.outcome == outcome:
                return token
        return None

    @staticmethod
    def _find_token_id(opp: ScoredOpportunity, outcome: str) -> str:
        for token in opp.candidate.market.tokens:
            if token.outcome == outcome:
                return token.token_id
        return ""
