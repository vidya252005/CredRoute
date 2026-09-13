"""Bounded concurrency for outbound lender calls."""

from __future__ import annotations

import asyncio

from app.core.config import settings


def lender_semaphore(limit: int | None = None) -> asyncio.Semaphore:
    return asyncio.Semaphore(limit or settings.lender_max_concurrency)
