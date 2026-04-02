import asyncio
from collections.abc import Callable, Coroutine
from decimal import Decimal
from typing import Any, TypeVar

T = TypeVar("T")

PRECISION = Decimal("0.0001")


def round_price(price: Decimal) -> Decimal:
    return price.quantize(PRECISION)


def cents_to_decimal(cents: float | int) -> Decimal:
    """Convert a price in cents (e.g. 45 meaning $0.45) to a Decimal."""
    return Decimal(str(cents)) / Decimal("100")


def decimal_to_cents(price: Decimal) -> float:
    """Convert a Decimal price to cents (e.g. 0.45 -> 45.0)."""
    return float(price * Decimal("100"))


async def retry_async(
    fn: Callable[..., Coroutine[Any, Any, T]],
    *args: Any,
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    **kwargs: Any,
) -> T:
    """Retry an async function with exponential backoff."""
    last_exc: Exception | None = None
    current_delay = delay
    for attempt in range(max_retries):
        try:
            return await fn(*args, **kwargs)
        except Exception as exc:
            last_exc = exc
            if attempt < max_retries - 1:
                await asyncio.sleep(current_delay)
                current_delay *= backoff
    raise last_exc  # type: ignore[misc]
