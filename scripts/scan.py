"""One-shot scan: fetch markets, detect arbitrage, print results.

Usage:
    uv run python scripts/scan.py
"""

from __future__ import annotations

import asyncio
import sys

from pengullet.config.settings import Settings
from pengullet.market.client import PolymarketClient
from pengullet.market.fetcher import MarketFetcher
from pengullet.monitoring.logger import setup_logging
from pengullet.strategy.evaluator import Evaluator
from pengullet.strategy.filters import OpportunityFilter
from pengullet.strategy.scanner import ArbitrageScanner


async def main() -> None:
    settings = Settings()
    setup_logging(settings.log_level)

    client = PolymarketClient(settings)
    fetcher = MarketFetcher(client, settings)
    scanner = ArbitrageScanner()
    evaluator = Evaluator(settings)
    opp_filter = OpportunityFilter(settings)

    try:
        print("Fetching active markets...")
        markets = await fetcher.fetch_active_markets()
        print(f"Found {len(markets)} tradeable markets")

        print("Enriching with order book data...")
        markets = await fetcher.enrich_with_order_books(markets)

        print("Scanning for arbitrage opportunities...")
        candidates = scanner.scan(markets)
        print(f"Found {len(candidates)} raw candidates")

        scored = evaluator.evaluate(candidates)
        filtered = opp_filter.apply(scored)
        print(f"After evaluation & filtering: {len(filtered)} actionable opportunities")

        if filtered:
            print("\n" + "=" * 70)
            for i, opp in enumerate(filtered, 1):
                c = opp.candidate
                print(f"\n--- Opportunity #{i} ---")
                print(f"  Market:       {c.market.question}")
                print(f"  Total cost:   ${float(c.total_cost):.4f}")
                pps = float(c.profit_per_share)
                pct = float(c.profit_pct)
                print(f"  Profit/share: ${pps:.4f} ({pct:.2f}%)")
                print(f"  Net profit:   ${float(opp.net_profit):.4f}")
                print(f"  Rec. size:    {float(opp.recommended_size):.1f} shares")
                print("  Asks:")
                for outcome, ask in c.best_asks.items():
                    print(f"    {outcome}: ${float(ask.price):.4f} x {float(ask.size):.1f}")
            print("\n" + "=" * 70)
        else:
            print("No profitable arbitrage opportunities found at this time.")
    finally:
        await client.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
