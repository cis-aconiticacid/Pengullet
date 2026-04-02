"""Main bot loop: continuously scan, evaluate, and optionally execute.

Usage:
    uv run python scripts/run_bot.py              # dry-run mode (default)
    uv run python scripts/run_bot.py --live        # live trading mode
"""

from __future__ import annotations

import argparse
import asyncio
import sys

import structlog

from pengullet.config.settings import Settings
from pengullet.execution.executor import OrderExecutor
from pengullet.execution.risk import RiskManager
from pengullet.execution.wallet import WalletManager
from pengullet.market.client import PolymarketClient
from pengullet.market.fetcher import MarketFetcher
from pengullet.monitoring.dashboard import Dashboard
from pengullet.monitoring.logger import setup_logging
from pengullet.monitoring.notifier import Notifier
from pengullet.strategy.evaluator import Evaluator
from pengullet.strategy.filters import OpportunityFilter
from pengullet.strategy.scanner import ArbitrageScanner

logger = structlog.get_logger(__name__)


async def run_loop(*, dry_run: bool = True) -> None:
    settings = Settings()
    setup_logging(settings.log_level)

    client = PolymarketClient(settings)
    fetcher = MarketFetcher(client, settings)
    scanner = ArbitrageScanner()
    evaluator = Evaluator(settings)
    opp_filter = OpportunityFilter(settings)

    wallet = WalletManager(settings)
    risk_mgr = RiskManager(settings)
    executor = OrderExecutor(wallet, risk_mgr, dry_run=dry_run)
    notifier = Notifier(settings)
    dashboard = Dashboard()

    mode = "DRY-RUN" if dry_run else "LIVE"
    logger.info("bot.starting", mode=mode, interval=settings.scan_interval_seconds)

    try:
        while True:
            try:
                markets = await fetcher.fetch_active_markets()
                markets = await fetcher.enrich_with_order_books(markets)

                candidates = scanner.scan(markets)
                scored = evaluator.evaluate(candidates)
                filtered = opp_filter.apply(scored)

                dashboard.record_scan(len(candidates), len(filtered))

                for opp in filtered:
                    if notifier.is_configured:
                        await notifier.notify_opportunity(opp)

                    results = await executor.execute(opp)
                    if all(r.success for r in results):
                        dashboard.record_execution(opp)

                dashboard.log_status()

            except Exception:
                logger.exception("bot.scan_cycle_error")

            await asyncio.sleep(settings.scan_interval_seconds)

    except asyncio.CancelledError:
        logger.info("bot.cancelled")
    finally:
        await client.close()
        await notifier.close()
        logger.info("bot.stopped")
        print(dashboard.render())


def main() -> None:
    parser = argparse.ArgumentParser(description="Pengullet trading bot")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Enable live trading (default is dry-run)",
    )
    args = parser.parse_args()

    try:
        asyncio.run(run_loop(dry_run=not args.live))
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
