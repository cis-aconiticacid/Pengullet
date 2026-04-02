"""Tests for the profit evaluator and filters."""

from decimal import Decimal

from pengullet.config.settings import Settings
from pengullet.market.models import ArbitrageCandidate, Market, OrderBook, OrderBookEntry, Token
from pengullet.strategy.evaluator import Evaluator
from pengullet.strategy.filters import OpportunityFilter


def _make_candidate(
    total_cost: float = 0.95,
    profit: float = 0.05,
    max_shares: float = 100.0,
) -> ArbitrageCandidate:
    yes_ask = OrderBookEntry(price=Decimal(str(total_cost / 2)), size=Decimal(str(max_shares)))
    no_ask = OrderBookEntry(price=Decimal(str(total_cost / 2)), size=Decimal(str(max_shares)))

    market = Market(
        condition_id="cond-1",
        question="Test?",
        tokens=[
            Token(
                token_id="t1",
                outcome="Yes",
                order_book=OrderBook(token_id="t1", asks=[yes_ask], bids=[]),
            ),
            Token(
                token_id="t2",
                outcome="No",
                order_book=OrderBook(token_id="t2", asks=[no_ask], bids=[]),
            ),
        ],
    )

    return ArbitrageCandidate(
        market=market,
        best_asks={"Yes": yes_ask, "No": no_ask},
        total_cost=Decimal(str(total_cost)),
        profit_per_share=Decimal(str(profit)),
        max_shares=Decimal(str(max_shares)),
        gross_profit=Decimal(str(profit)) * Decimal(str(max_shares)),
    )


class TestEvaluator:
    def _settings(self, **overrides: object) -> Settings:
        defaults = {
            "polymarket_api_url": "https://clob.polymarket.com",
            "min_profit_threshold": Decimal("0.005"),
            "max_position_size": Decimal("50.0"),
            "max_total_exposure": Decimal("500.0"),
        }
        defaults.update(overrides)
        return Settings(**defaults)  # type: ignore[arg-type]

    def test_profitable_candidate_is_scored(self) -> None:
        candidate = _make_candidate(total_cost=0.92, profit=0.08, max_shares=100.0)
        evaluator = Evaluator(self._settings())
        scored = evaluator.evaluate([candidate])
        assert len(scored) == 1
        assert scored[0].net_profit > 0

    def test_tiny_profit_is_excluded(self) -> None:
        candidate = _make_candidate(total_cost=0.999, profit=0.001, max_shares=10.0)
        evaluator = Evaluator(self._settings())
        scored = evaluator.evaluate([candidate])
        assert len(scored) == 0

    def test_recommended_size_respects_max_position(self) -> None:
        candidate = _make_candidate(total_cost=0.90, profit=0.10, max_shares=1000.0)
        settings = self._settings(max_position_size=Decimal("20.0"))
        evaluator = Evaluator(settings)
        scored = evaluator.evaluate([candidate])
        assert len(scored) == 1
        # $20 max / $0.90 cost ≈ 22.2 shares max
        assert scored[0].recommended_size <= Decimal("23")


class TestOpportunityFilter:
    def _settings(self) -> Settings:
        return Settings(
            polymarket_api_url="https://clob.polymarket.com",
            min_profit_threshold=Decimal("0.01"),
            max_position_size=Decimal("50.0"),
            max_total_exposure=Decimal("500.0"),
        )

    def test_passes_good_opportunity(self) -> None:
        candidate = _make_candidate(total_cost=0.90, profit=0.10, max_shares=50.0)
        evaluator = Evaluator(self._settings())
        scored = evaluator.evaluate([candidate])

        opp_filter = OpportunityFilter(self._settings())
        filtered = opp_filter.apply(scored)
        assert len(filtered) == len(scored)

    def test_rejects_low_liquidity(self) -> None:
        candidate = _make_candidate(total_cost=0.90, profit=0.10, max_shares=2.0)
        evaluator = Evaluator(self._settings())
        scored = evaluator.evaluate([candidate])

        opp_filter = OpportunityFilter(self._settings())
        filtered = opp_filter.apply(scored)
        assert len(filtered) == 0
