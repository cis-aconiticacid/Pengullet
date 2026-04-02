from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field


class Outcome(StrEnum):
    YES = "Yes"
    NO = "No"


class OrderBookEntry(BaseModel):
    """A single price/size level in the order book."""

    price: Decimal
    size: Decimal


class OrderBook(BaseModel):
    """Order book for a single outcome token."""

    token_id: str
    asks: list[OrderBookEntry] = Field(default_factory=list)
    bids: list[OrderBookEntry] = Field(default_factory=list)

    @property
    def best_ask(self) -> OrderBookEntry | None:
        if not self.asks:
            return None
        return min(self.asks, key=lambda e: e.price)

    @property
    def best_bid(self) -> OrderBookEntry | None:
        if not self.bids:
            return None
        return max(self.bids, key=lambda e: e.price)

    @property
    def spread(self) -> Decimal | None:
        ask = self.best_ask
        bid = self.best_bid
        if ask and bid:
            return ask.price - bid.price
        return None

    def ask_depth(self, levels: int = 5) -> Decimal:
        """Total size available in top N ask levels."""
        sorted_asks = sorted(self.asks, key=lambda e: e.price)
        return sum(a.size for a in sorted_asks[:levels])

    def bid_depth(self, levels: int = 5) -> Decimal:
        """Total size available in top N bid levels."""
        sorted_bids = sorted(self.bids, key=lambda e: e.price, reverse=True)
        return sum(b.size for b in sorted_bids[:levels])


class Token(BaseModel):
    """A single outcome token within a market."""

    token_id: str
    outcome: str
    price: Decimal | None = None
    order_book: OrderBook | None = None


class Market(BaseModel):
    """A Polymarket prediction market (condition)."""

    condition_id: str
    question: str
    slug: str = ""
    active: bool = True
    closed: bool = False
    tokens: list[Token] = Field(default_factory=list)

    @property
    def is_tradeable(self) -> bool:
        return self.active and not self.closed

    @property
    def outcome_count(self) -> int:
        return len(self.tokens)


class MarketGroup(BaseModel):
    """A group of related markets (multi-outcome event)."""

    group_id: str
    title: str
    markets: list[Market] = Field(default_factory=list)


class ArbitrageCandidate(BaseModel):
    """A detected arbitrage opportunity."""

    market: Market
    best_asks: dict[str, OrderBookEntry]
    total_cost: Decimal
    profit_per_share: Decimal
    max_shares: Decimal
    gross_profit: Decimal

    @property
    def profit_pct(self) -> Decimal:
        if self.total_cost == 0:
            return Decimal("0")
        return (self.profit_per_share / self.total_cost) * Decimal("100")


class ScoredOpportunity(BaseModel):
    """An arbitrage candidate after profit/risk evaluation."""

    candidate: ArbitrageCandidate
    gross_profit: Decimal
    trading_fee: Decimal
    gas_fee: Decimal
    slippage_estimate: Decimal
    net_profit: Decimal
    recommended_size: Decimal

    @property
    def is_profitable(self) -> bool:
        return self.net_profit > Decimal("0")
