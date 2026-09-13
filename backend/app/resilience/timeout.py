"""Per-provider timeout helper."""

from __future__ import annotations

import asyncio
from typing import Awaitable, TypeVar

T = TypeVar("T")


async def with_timeout(awaitable: Awaitable[T], timeout_ms: int) -> T:
    return await asyncio.wait_for(awaitable, timeout=timeout_ms / 1000)
