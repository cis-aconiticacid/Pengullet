"""Tests for the arbitrage scanner."""

from decimal import Decimal

from pengullet.market.models import Market, OrderBook, OrderBookEntry, Token
from pengullet.strategy.scanner import ArbitrageScanner


def _make_market(
    yes_ask: float,
    no_ask: float,
    yes_size: float = 100.0,
    no_size: float = 100.0,
    question: str = "Test market?",
) -> Market:
    """Helper to build a Market with order books attached."""
    yes_token = Token(
        token_id="yes-token-1",
        outcome="Yes",
        order_book=OrderBook(
            token_id="yes-token-1",
            asks=[OrderBookEntry(price=Decimal(str(yes_ask)), size=Decimal(str(yes_size)))],
            bids=[],
        ),
    )
    no_token = Token(
        token_id="no-token-1",
        outcome="No",
        order_book=OrderBook(
            token_id="no-token-1",
            asks=[OrderBookEntry(price=Decimal(str(no_ask)), size=Decimal(str(no_size)))],
            bids=[],
        ),
    )
    return Market(
        condition_id="cond-1",
        question=question,
        tokens=[yes_token, no_token],
    )


class TestArbitrageScanner:
    def test_detects_arbitrage_when_total_ask_below_one(self) -> None:
        market = _make_market(yes_ask=0.45, no_ask=0.52)
        scanner = ArbitrageScanner()
        candidates = scanner.scan([market])
        assert len(candidates) == 1
        c = candidates[0]
        assert c.total_cost == Decimal("0.97")
        assert c.profit_per_share == Decimal("0.03")

    def test_no_arbitrage_when_total_ask_equals_one(self) -> None:
        market = _make_market(yes_ask=0.50, no_ask=0.50)
        scanner = ArbitrageScanner()
        candidates = scanner.scan([market])
        assert len(candidates) == 0

    def test_no_arbitrage_when_total_ask_above_one(self) -> None:
        market = _make_market(yes_ask=0.55, no_ask=0.50)
        scanner = ArbitrageScanner()
        candidates = scanner.scan([market])
        assert len(candidates) == 0

    def test_max_shares_uses_smallest_ask_size(self) -> None:
        market = _make_market(yes_ask=0.40, no_ask=0.50, yes_size=200.0, no_size=50.0)
        scanner = ArbitrageScanner()
        candidates = scanner.scan([market])
        assert len(candidates) == 1
        assert candidates[0].max_shares == Decimal("50.0")

    def test_skips_market_without_order_book(self) -> None:
        token_yes = Token(token_id="t1", outcome="Yes", order_book=None)
        token_no = Token(token_id="t2", outcome="No", order_book=None)
        market = Market(condition_id="c1", question="Q?", tokens=[token_yes, token_no])
        scanner = ArbitrageScanner()
        assert scanner.scan([market]) == []

    def test_skips_market_with_empty_asks(self) -> None:
        token_yes = Token(
            token_id="t1",
            outcome="Yes",
            order_book=OrderBook(token_id="t1", asks=[], bids=[]),
        )
        token_no = Token(
            token_id="t2",
            outcome="No",
            order_book=OrderBook(
                token_id="t2",
                asks=[OrderBookEntry(price=Decimal("0.5"), size=Decimal("10"))],
                bids=[],
            ),
        )
        market = Market(condition_id="c1", question="Q?", tokens=[token_yes, token_no])
        scanner = ArbitrageScanner()
        assert scanner.scan([market]) == []

    def test_sorts_by_gross_profit_descending(self) -> None:
        # Market A: 3% profit, 100 shares = $3 gross
        market_a = _make_market(yes_ask=0.45, no_ask=0.52, yes_size=100, no_size=100, question="A")
        # Market B: 10% profit, 50 shares = $5 gross
        market_b = _make_market(yes_ask=0.40, no_ask=0.50, yes_size=50, no_size=50, question="B")

        scanner = ArbitrageScanner()
        candidates = scanner.scan([market_a, market_b])
        assert len(candidates) == 2
        assert candidates[0].market.question == "B"
        assert candidates[1].market.question == "A"
