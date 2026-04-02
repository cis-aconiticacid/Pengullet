# Pengullet

Polymarket secondary market arbitrage scanner and trading bot.

Pengullet monitors Polymarket prediction markets for mispriced outcome tokens — when the sum of best-ask prices across all outcomes is less than $1.00, an arbitrage opportunity exists. The bot detects these opportunities, evaluates them after fees and slippage, and can execute trades automatically.

## How It Works

On Polymarket, each prediction market has outcome tokens (e.g. Yes/No). In theory, `Price(Yes) + Price(No) = $1.00`. In practice, order book fragmentation creates opportunities where the total cost is less than $1.00, guaranteeing a profit at settlement.

```
Profit = $1.00 - Sum(best ask prices for all outcomes) - fees
```

## Quick Start

```bash
# Install dependencies
uv sync

# Explore Polymarket API and see real market data (no API key needed)
uv run python scripts/demo_explore.py

# Copy and configure environment variables
cp .env.example .env
# Edit .env with your Polymarket API credentials

# Run a one-shot scan (read-only, no trading)
uv run python scripts/scan.py

# Run the bot in dry-run mode (continuous scanning, no real orders)
uv run python scripts/run_bot.py

# Run the bot in live trading mode
uv run python scripts/run_bot.py --live
```

## Exploring Polymarket (Demo)

`scripts/demo_explore.py` is a self-contained demo that requires no API keys. It calls Polymarket's public APIs and prints real market data to help you understand how the platform works:

1. **Hot markets** — fetches the top markets by 24h volume from the Gamma API
2. **Order book** — shows bid/ask levels, sizes, and spreads for a live market
3. **Prices** — displays midpoint, buy price, sell price, and spread for each outcome token
4. **Arbitrage scan** — scans 100 markets looking for Sum(Ask) < $1.00 opportunities

```bash
uv run python scripts/demo_explore.py
```

The script also prints a summary of Polymarket's three APIs (Gamma, CLOB, Data) and their key endpoints at the end.

## Project Structure

```
src/pengullet/
├── config/         Configuration management (pydantic-settings)
├── market/         Polymarket API client, data models, order book fetcher
├── strategy/       Arbitrage scanner, profit evaluator, opportunity filters
├── execution/      Order executor, risk manager, wallet/signing
├── monitoring/     Structured logging, Telegram/Discord alerts, dashboard
└── utils/          Shared helpers
```

## Running Tests

```bash
uv run pytest
```

## Configuration

All configuration is done via environment variables (or a `.env` file). See `.env.example` for the full list.

Key settings:

| Variable | Description | Default |
|---|---|---|
| `POLYMARKET_API_URL` | CLOB API base URL | `https://clob.polymarket.com` |
| `POLYMARKET_PRIVATE_KEY` | Ethereum private key for signing | — |
| `MIN_PROFIT_THRESHOLD` | Minimum net profit to act on | `0.005` |
| `MAX_POSITION_SIZE` | Max USDC per trade | `50.0` |
| `MAX_TOTAL_EXPOSURE` | Max total open exposure | `500.0` |
| `SCAN_INTERVAL_SECONDS` | Seconds between scan cycles | `10` |
