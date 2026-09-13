"""Idempotency-Key lookup with request-hash conflict detection."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.entities import IdempotencyKey


def request_hash(body: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode("utf-8")).hexdigest()


class IdempotencyService:
    def __init__(self, db: Session):
        self.db = db

    def lookup(self, key: str | None, body: dict[str, Any]) -> tuple[dict | None, str | None]:
        if not key:
            return None, None
        digest = request_hash(body)
        cached = self.db.query(IdempotencyKey).filter(IdempotencyKey.key == key).first()
        if not cached:
            return None, digest
        stored = getattr(cached, "request_hash", None)
        if stored and stored != digest:
            raise AppError(
                "IDEMPOTENCY_CONFLICT",
                "Idempotency-Key was reused with a different request payload.",
                409,
            )
        return cached.response, digest

    def store(self, key: str | None, digest: str | None, response: dict[str, Any]) -> None:
        if not key:
            return
        row = IdempotencyKey(key=key, response=response)
        if digest is not None and hasattr(row, "request_hash"):
            row.request_hash = digest
        self.db.add(row)
