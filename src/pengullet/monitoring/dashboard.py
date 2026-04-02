"""Simple text-based status dashboard."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from decimal import Decimal

import structlog

from pengullet.market.models import ScoredOpportunity

logger = structlog.get_logger(__name__)


@dataclass
class ScanStats:
    total_scans: int = 0
    total_candidates_found: int = 0
    total_profitable: int = 0
    total_executed: int = 0
    total_profit: Decimal = Decimal("0")
    total_volume: Decimal = Decimal("0")
    start_time: float = field(default_factory=time.monotonic)
    last_scan_time: float = 0.0
    recent_opportunities: list[ScoredOpportunity] = field(default_factory=list)


class Dashboard:
    """In-memory stats tracker and text dashboard renderer."""

    MAX_RECENT = 20

    def __init__(self) -> None:
        self._stats = ScanStats()

    @property
    def stats(self) -> ScanStats:
        return self._stats

    def record_scan(self, candidates: int, profitable: int) -> None:
        self._stats.total_scans += 1
        self._stats.total_candidates_found += candidates
        self._stats.total_profitable += profitable
        self._stats.last_scan_time = time.monotonic()

    def record_execution(self, opp: ScoredOpportunity) -> None:
        self._stats.total_executed += 1
        self._stats.total_profit += opp.net_profit
        self._stats.total_volume += opp.recommended_size * opp.candidate.total_cost
        self._stats.recent_opportunities.append(opp)
        if len(self._stats.recent_opportunities) > self.MAX_RECENT:
            self._stats.recent_opportunities = self._stats.recent_opportunities[-self.MAX_RECENT :]

    def render(self) -> str:
        s = self._stats
        uptime = time.monotonic() - s.start_time
        hours = uptime / 3600

        lines = [
            "=" * 60,
            "  PENGULLET DASHBOARD",
            "=" * 60,
            f"  Uptime:              {hours:.1f} hours",
            f"  Total scans:         {s.total_scans}",
            f"  Candidates found:    {s.total_candidates_found}",
            f"  Profitable:          {s.total_profitable}",
            f"  Executed:            {s.total_executed}",
            f"  Total profit:        ${float(s.total_profit):.4f}",
            f"  Total volume:        ${float(s.total_volume):.2f}",
            "-" * 60,
        ]

        if s.recent_opportunities:
            lines.append("  Recent opportunities:")
            for opp in s.recent_opportunities[-5:]:
                q = opp.candidate.market.question[:40]
                lines.append(f"    {q}  net=${float(opp.net_profit):.4f}")

        lines.append("=" * 60)
        return "\n".join(lines)

    def log_status(self) -> None:
        logger.info(
            "dashboard.status",
            scans=self._stats.total_scans,
            candidates=self._stats.total_candidates_found,
            profitable=self._stats.total_profitable,
            executed=self._stats.total_executed,
            profit=float(self._stats.total_profit),
        )
