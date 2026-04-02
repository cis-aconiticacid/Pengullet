"""Polymarket API 探索 Demo

不需要任何 API Key，纯公开数据。
运行方式: uv run python scripts/demo_explore.py

这个脚本会依次演示:
  1. 从 Gamma API 获取热门市场列表（市场发现）
  2. 从 CLOB API 获取某个市场的订单簿（实时交易数据）
  3. 获取价格、中间价、价差等信息
  4. 扫描所有活跃市场，寻找套利机会（Sum(Ask) < $1.00）
"""

from __future__ import annotations

import asyncio
import json
import sys
from decimal import Decimal

import httpx

# ═══════════════════════════════════════════════════════════════════
# Polymarket 有三个 API：
#
#   1. Gamma API  (https://gamma-api.polymarket.com)
#      - 市场发现：浏览所有市场、事件、标签、搜索
#      - 完全公开，无需认证
#
#   2. CLOB API   (https://clob.polymarket.com)
#      - 交易数据：订单簿、价格、价差、中间价
#      - 交易操作：下单、撤单（需要认证）
#      - 读取数据不需要认证，下单才需要
#
#   3. Data API   (https://data-api.polymarket.com)
#      - 用户数据：持仓、交易历史、排行榜
#      - 完全公开
# ═══════════════════════════════════════════════════════════════════

GAMMA_API = "https://gamma-api.polymarket.com"
CLOB_API = "https://clob.polymarket.com"


def separator(title: str) -> None:
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}\n")


async def demo_1_list_markets(client: httpx.AsyncClient) -> list[dict]:
    """演示 1: 从 Gamma API 获取热门市场

    Gamma API 端点: GET /markets
    参数:
      - limit: 返回数量
      - active: 是否活跃
      - closed: 是否已关闭
      - order: 排序字段 (volume24hr, liquidity, volume 等)
      - ascending: 是否升序
    """
    separator("1. 获取 Polymarket 热门市场 (Gamma API)")

    resp = await client.get(
        f"{GAMMA_API}/markets",
        params={
            "limit": 5,
            "active": "true",
            "closed": "false",
            "order": "volume24hr",
            "ascending": "false",
        },
    )
    resp.raise_for_status()
    markets = resp.json()

    print(f"获取到 {len(markets)} 个热门市场（按24小时交易量排序）:\n")

    for i, m in enumerate(markets, 1):
        question = m["question"]
        volume_24h = float(m.get("volume24hr", 0))
        liquidity = float(m.get("liquidityNum", 0))
        outcomes = json.loads(m.get("outcomes", "[]"))
        prices = json.loads(m.get("outcomePrices", "[]"))
        best_bid = m.get("bestBid", "N/A")
        best_ask = m.get("bestAsk", "N/A")
        clob_token_ids = json.loads(m.get("clobTokenIds", "[]"))

        print(f"  [{i}] {question}")
        print(f"      24h交易量:  ${volume_24h:,.0f}")
        print(f"      流动性:     ${liquidity:,.0f}")
        print(f"      结果:       {outcomes}")
        print(f"      当前价格:   {prices}")
        print(f"      Best Bid:  {best_bid}  |  Best Ask: {best_ask}")
        print(f"      Token IDs: {[tid[:20] + '...' for tid in clob_token_ids]}")
        print()

    return markets


async def demo_2_order_book(client: httpx.AsyncClient, markets: list[dict]) -> dict | None:
    """演示 2: 从 CLOB API 获取订单簿

    CLOB API 端点: GET /book?token_id={token_id}
    返回:
      - bids: 买单列表 [{"price": "0.48", "size": "1000"}, ...]
      - asks: 卖单列表 [{"price": "0.52", "size": "800"}, ...]
      - tick_size: 最小价格增量
      - min_order_size: 最小订单量
    """
    separator("2. 获取订单簿详情 (CLOB API)")

    # 找一个有交易的市场
    target = None
    for m in markets:
        prices = json.loads(m.get("outcomePrices", "[]"))
        if any(float(p) > 0.01 and float(p) < 0.99 for p in prices):
            target = m
            break

    if target is None:
        target = markets[0] if markets else None

    if target is None:
        print("  没有找到合适的市场来展示订单簿")
        return None

    token_ids = json.loads(target.get("clobTokenIds", "[]"))
    outcomes = json.loads(target.get("outcomes", "[]"))

    print(f"  市场: {target['question']}\n")

    selected_market = {"question": target["question"], "tokens": []}

    for idx, token_id in enumerate(token_ids):
        outcome = outcomes[idx] if idx < len(outcomes) else f"Outcome {idx}"

        resp = await client.get(f"{CLOB_API}/book", params={"token_id": token_id})
        resp.raise_for_status()
        book = resp.json()

        bids = book.get("bids", [])
        asks = book.get("asks", [])
        tick_size = book.get("tick_size", "N/A")

        print(f"  ── {outcome} Token ──")
        print(f"     Token ID:      {token_id[:30]}...")
        print(f"     Tick Size:     {tick_size}")
        print("     卖单 (Asks) - 有人愿意以这些价格卖出:")

        if asks:
            sorted_asks = sorted(asks, key=lambda x: float(x["price"]))
            for a in sorted_asks[:5]:
                print(f"       价格 ${float(a['price']):.4f}  |  数量 {float(a['size']):,.1f} 份")
            if len(asks) > 5:
                print(f"       ... 还有 {len(asks) - 5} 档")
        else:
            print("       (空)")

        print("     买单 (Bids) - 有人愿意以这些价格买入:")
        if bids:
            sorted_bids = sorted(bids, key=lambda x: float(x["price"]), reverse=True)
            for b in sorted_bids[:5]:
                print(f"       价格 ${float(b['price']):.4f}  |  数量 {float(b['size']):,.1f} 份")
            if len(bids) > 5:
                print(f"       ... 还有 {len(bids) - 5} 档")
        else:
            print("       (空)")

        best_ask = min(asks, key=lambda x: float(x["price"])) if asks else None
        best_bid = max(bids, key=lambda x: float(x["price"])) if bids else None

        if best_ask and best_bid:
            spread = float(best_ask["price"]) - float(best_bid["price"])
            ba = float(best_ask['price'])
            bb = float(best_bid['price'])
            print(f"     Best Ask: ${ba:.4f}  |  Best Bid: ${bb:.4f}  |  Spread: ${spread:.4f}")
        print()

        selected_market["tokens"].append({
            "outcome": outcome,
            "token_id": token_id,
            "best_ask": best_ask,
            "best_bid": best_bid,
        })

    return selected_market


async def demo_3_prices(client: httpx.AsyncClient, markets: list[dict]) -> None:
    """演示 3: 获取价格、中间价、价差

    CLOB API 端点:
      - GET /midpoint?token_id={id}   → 中间价（best bid 和 best ask 的平均值）
      - GET /spread?token_id={id}     → 价差（best ask - best bid）
      - GET /price?token_id={id}&side=BUY  → 买入价（best ask）
      - GET /price?token_id={id}&side=SELL → 卖出价（best bid）
    """
    separator("3. 价格、中间价、价差 (CLOB API)")

    if not markets:
        print("  没有市场数据")
        return

    target = markets[0]
    token_ids = json.loads(target.get("clobTokenIds", "[]"))
    outcomes = json.loads(target.get("outcomes", "[]"))

    print(f"  市场: {target['question']}\n")

    for idx, token_id in enumerate(token_ids):
        outcome = outcomes[idx] if idx < len(outcomes) else f"Outcome {idx}"

        # 中间价
        try:
            resp = await client.get(f"{CLOB_API}/midpoint", params={"token_id": token_id})
            midpoint = resp.json().get("mid", "N/A")
        except Exception:
            midpoint = "N/A"

        # 价差
        try:
            resp = await client.get(f"{CLOB_API}/spread", params={"token_id": token_id})
            spread = resp.json().get("spread", "N/A")
        except Exception:
            spread = "N/A"

        # 买入价 / 卖出价
        try:
            params = {"token_id": token_id, "side": "BUY"}
            resp = await client.get(f"{CLOB_API}/price", params=params)
            buy_price = resp.json().get("price", "N/A")
        except Exception:
            buy_price = "N/A"

        try:
            params = {"token_id": token_id, "side": "SELL"}
            resp = await client.get(f"{CLOB_API}/price", params=params)
            sell_price = resp.json().get("price", "N/A")
        except Exception:
            sell_price = "N/A"

        print(f"  {outcome}:")
        print(f"    中间价 (Midpoint): {midpoint}")
        print(f"    买入价 (Best Ask): {buy_price}  ← 你买入要付的价格")
        print(f"    卖出价 (Best Bid): {sell_price}  ← 你卖出能得到的价格")
        print(f"    价差 (Spread):     {spread}")
        print()


async def demo_4_scan_arbitrage(client: httpx.AsyncClient) -> None:
    """演示 4: 扫描套利机会

    核心逻辑:
      1. 获取所有活跃市场
      2. 对每个市场，获取每个结果 Token 的 best ask
      3. 如果 Sum(best asks) < $1.00 → 套利机会！
    """
    separator("4. 扫描套利机会")

    print("  正在获取活跃市场（前 100 个高流动性市场）...\n")

    resp = await client.get(
        f"{GAMMA_API}/markets",
        params={
            "limit": 100,
            "active": "true",
            "closed": "false",
            "order": "liquidity",
            "ascending": "false",
        },
    )
    resp.raise_for_status()
    markets = resp.json()

    print(f"  获取到 {len(markets)} 个市场，正在逐个检查订单簿...\n")

    opportunities: list[dict] = []
    checked = 0

    for m in markets:
        token_ids = json.loads(m.get("clobTokenIds", "[]"))
        outcomes = json.loads(m.get("outcomes", "[]"))

        if len(token_ids) < 2:
            continue

        best_asks: dict[str, dict] = {}

        for idx, token_id in enumerate(token_ids):
            outcome = outcomes[idx] if idx < len(outcomes) else f"Outcome {idx}"
            try:
                resp = await client.get(f"{CLOB_API}/book", params={"token_id": token_id})
                resp.raise_for_status()
                book = resp.json()
                asks = book.get("asks", [])
                if asks:
                    best_ask = min(asks, key=lambda x: float(x["price"]))
                    best_asks[outcome] = best_ask
            except Exception:
                pass

        checked += 1

        if len(best_asks) == len(token_ids):
            total_cost = sum(Decimal(a["price"]) for a in best_asks.values())

            if total_cost < Decimal("1.0"):
                profit = Decimal("1.0") - total_cost
                max_shares = min(Decimal(a["size"]) for a in best_asks.values())
                opportunities.append({
                    "question": m["question"],
                    "total_cost": total_cost,
                    "profit_per_share": profit,
                    "profit_pct": float(profit / total_cost * 100),
                    "max_shares": max_shares,
                    "gross_profit": profit * max_shares,
                    "best_asks": best_asks,
                })

        # 进度
        if checked % 20 == 0:
            print(f"  已检查 {checked}/{len(markets)} 个市场，发现 {len(opportunities)} 个机会...")

    print(f"\n  扫描完成！检查了 {checked} 个市场")
    print(f"  发现 {len(opportunities)} 个套利机会（Sum(Ask) < $1.00）\n")

    if opportunities:
        opportunities.sort(key=lambda x: x["gross_profit"], reverse=True)
        print("  ┌─────────────────────────────────────────────────────────────┐")
        print("  │                    套 利 机 会 列 表                        │")
        print("  └─────────────────────────────────────────────────────────────┘\n")

        for i, opp in enumerate(opportunities[:10], 1):
            print(f"  #{i}  {opp['question']}")
            print(f"      总成本:       ${float(opp['total_cost']):.4f}")
            pps = float(opp['profit_per_share'])
            pct = opp['profit_pct']
            print(f"      每份利润:     ${pps:.4f} ({pct:.2f}%)")
            print(f"      可操作数量:   {float(opp['max_shares']):.1f} 份")
            print(f"      毛利润:       ${float(opp['gross_profit']):.2f}")
            print("      各结果 Ask:")
            for outcome, ask in opp["best_asks"].items():
                print(f"        {outcome}: ${float(ask['price']):.4f} x {float(ask['size']):,.1f}")
            print()
    else:
        print("  当前没有发现明显的套利机会。")
        print("  （这很正常——套利窗口通常很短暂，被机器人快速消化）")

    print("\n  ── 解读 ──")
    print("  • 如果某市场 Yes Ask=$0.45 + No Ask=$0.52 = $0.97 < $1.00")
    print("    → 你花 $0.97 同时买入 Yes 和 No，无论结果如何都拿回 $1.00")
    print("    → 利润 = $0.03 (3.09%)")
    print("  • 实际操作还需扣除 ~2% 手续费和微量 Gas 费")


async def main() -> None:
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
        # 演示 1: 列出热门市场
        markets = await demo_1_list_markets(client)

        # 演示 2: 查看某个市场的订单簿
        await demo_2_order_book(client, markets)

        # 演示 3: 获取价格信息
        await demo_3_prices(client, markets)

        # 演示 4: 扫描套利机会
        await demo_4_scan_arbitrage(client)

    separator("API 总结")
    print("""  Polymarket 有三个 API:

  1. Gamma API (https://gamma-api.polymarket.com)
     └── 市场发现: GET /markets, GET /events, GET /markets/{id}
         无需认证，返回市场问题、描述、Token IDs、交易量等

  2. CLOB API (https://clob.polymarket.com)
     ├── 公开端点（无需认证）:
     │   ├── GET /book?token_id=...      订单簿（asks + bids）
     │   ├── GET /price?token_id=...&side=BUY   买入价
     │   ├── GET /midpoint?token_id=...  中间价
     │   └── GET /spread?token_id=...    价差
     └── 交易端点（需要 API Key + 私钥签名）:
         ├── POST /order       下单
         └── DELETE /order     撤单

  3. Data API (https://data-api.polymarket.com)
     └── 用户数据: 持仓、交易历史、排行榜

  套利流程:
    Gamma API 获取市场列表 → CLOB API 获取订单簿 → 计算套利 → CLOB API 下单
""")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
