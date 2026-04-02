"""Push notifications via Telegram and Discord."""

from __future__ import annotations

import httpx
import structlog

from pengullet.config.settings import Settings
from pengullet.market.models import ScoredOpportunity

logger = structlog.get_logger(__name__)


class Notifier:
    """Sends arbitrage opportunity alerts to Telegram and/or Discord."""

    def __init__(self, settings: Settings) -> None:
        self._telegram_token = settings.telegram_bot_token
        self._telegram_chat_id = settings.telegram_chat_id
        self._discord_webhook = settings.discord_webhook_url
        self._http: httpx.AsyncClient | None = None

    async def _client(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(timeout=httpx.Timeout(15.0))
        return self._http

    async def close(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()

    @property
    def is_configured(self) -> bool:
        has_telegram = bool(self._telegram_token and self._telegram_chat_id)
        has_discord = bool(self._discord_webhook)
        return has_telegram or has_discord

    async def notify_opportunity(self, opp: ScoredOpportunity) -> None:
        message = self._format_opportunity(opp)
        if self._telegram_token and self._telegram_chat_id:
            await self._send_telegram(message)
        if self._discord_webhook:
            await self._send_discord(message)

    async def notify_text(self, text: str) -> None:
        if self._telegram_token and self._telegram_chat_id:
            await self._send_telegram(text)
        if self._discord_webhook:
            await self._send_discord(text)

    # ── Formatters ───────────────────────────────────────────────────

    @staticmethod
    def _format_opportunity(opp: ScoredOpportunity) -> str:
        c = opp.candidate
        lines = [
            "🐧 *Pengullet Arbitrage Alert*",
            "",
            f"*Market:* {c.market.question}",
            f"*Total Cost:* ${float(c.total_cost):.4f}",
            f"*Profit/Share:* ${float(c.profit_per_share):.4f} ({float(c.profit_pct):.2f}%)",
            f"*Net Profit:* ${float(opp.net_profit):.4f}",
            f"*Recommended Size:* {float(opp.recommended_size):.1f} shares",
            "",
            "*Ask Prices:*",
        ]
        for outcome, ask in c.best_asks.items():
            lines.append(f"  {outcome}: ${float(ask.price):.4f} (size: {float(ask.size):.1f})")
        return "\n".join(lines)

    # ── Transport ────────────────────────────────────────────────────

    async def _send_telegram(self, text: str) -> None:
        try:
            client = await self._client()
            url = f"https://api.telegram.org/bot{self._telegram_token}/sendMessage"
            payload = {
                "chat_id": self._telegram_chat_id,
                "text": text,
                "parse_mode": "Markdown",
            }
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            logger.debug("telegram.sent")
        except Exception:
            logger.exception("telegram.send_failed")

    async def _send_discord(self, text: str) -> None:
        try:
            client = await self._client()
            # Discord webhooks don't support Markdown the same way; strip it
            clean = text.replace("*", "**")
            payload = {"content": clean}
            resp = await client.post(self._discord_webhook, json=payload)
            resp.raise_for_status()
            logger.debug("discord.sent")
        except Exception:
            logger.exception("discord.send_failed")
