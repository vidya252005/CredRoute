"""Generic retry policy with exponential backoff and jitter."""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass, field

from app.resilience.errors import ProviderRateLimited, ProviderTimeout, ProviderUnavailable


@dataclass(slots=True)
class RetryPolicy:
    max_attempts: int = 3
    base_delay_ms: int = 40
    max_delay_ms: int = 400
    retryable_exceptions: tuple[type[BaseException], ...] = field(
        default_factory=lambda: (
            TimeoutError,
            ConnectionError,
            OSError,
            ProviderTimeout,
            ProviderUnavailable,
            ProviderRateLimited,
        )
    )

    def delay_seconds(self, attempt: int) -> float:
        expo = self.base_delay_ms * (2 ** max(0, attempt - 1))
        capped = min(self.max_delay_ms, expo)
        jitter = 0.5 + random.random()
        return (capped * jitter) / 1000

    def is_retryable(self, error: BaseException) -> bool:
        return isinstance(error, self.retryable_exceptions)

    async def sleep(self, attempt: int) -> None:
        await asyncio.sleep(self.delay_seconds(attempt))
