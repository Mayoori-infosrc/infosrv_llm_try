import time
from typing import Tuple


def now_seconds() -> float:
    """Return current time in seconds (monotonic-like)."""
    return time.time()


def naive_token_estimate(text: str) -> int:
    """
    Very simple token estimate: count words.
    Replace with model/tokenizer integration for precise counts.
    """
    if not text:
        return 0
    return len(str(text).split())


def cost_estimate(tokens: int, price_per_token: float = 0.000001) -> float:
    """Simple cost estimation (configurable price_per_token)."""
    return round(tokens * price_per_token, 6)
