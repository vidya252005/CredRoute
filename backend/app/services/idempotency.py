"""Race-safe Idempotency-Key handling with an explicit status machine."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import AppError
from app.models.entities import IdempotencyKey

IN_PROGRESS = "IN_PROGRESS"
COMPLETED = "COMPLETED"
FAILED = "FAILED"

ClaimResult = Literal["process", "replay"]


def request_hash(body: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode("utf-8")).hexdigest()


class IdempotencyService:
    def __init__(self, db: Session):
        self.db = db

    def claim(self, key: str | None, body: dict[str, Any]) -> tuple[ClaimResult, str | None, dict | None]:
        if not key:
            return "process", None, None
        digest = request_hash(body)
        now = datetime.now(UTC)
        existing = self.db.query(IdempotencyKey).filter(IdempotencyKey.key == key).first()
        if existing:
            return self._resolve_existing(existing, digest, now)

        row = IdempotencyKey(
            key=key,
            request_hash=digest,
            response={},
            status=IN_PROGRESS,
            expires_at=now + timedelta(hours=settings.idempotency_ttl_hours),
        )
        try:
            with self.db.begin_nested():
                self.db.add(row)
                self.db.flush()
            return "process", digest, None
        except IntegrityError:
            existing = self.db.query(IdempotencyKey).filter(IdempotencyKey.key == key).first()
            if not existing:
                raise AppError("IDEMPOTENCY_CONFLICT", "Could not claim idempotency key.", 409)
            return self._resolve_existing(existing, digest, now)

    def _resolve_existing(self, existing: IdempotencyKey, digest: str, now: datetime) -> tuple[ClaimResult, str, dict | None]:
        expires_at = existing.expires_at
        if expires_at is not None and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at and expires_at < now:
            self.db.delete(existing)
            self.db.flush()
            retry = IdempotencyKey(
                key=existing.key,
                request_hash=digest,
                response={},
                status=IN_PROGRESS,
                expires_at=now + timedelta(hours=settings.idempotency_ttl_hours),
            )
            self.db.add(retry)
            self.db.flush()
            return "process", digest, None
        stored = existing.request_hash
        if stored and stored != digest:
            raise AppError(
                "IDEMPOTENCY_CONFLICT",
                "Idempotency-Key was reused with a different request payload.",
                409,
            )
        if existing.status == IN_PROGRESS:
            raise AppError("IDEMPOTENCY_IN_PROGRESS", "A request with this key is already running.", 409)
        if existing.status == FAILED:
            existing.status = IN_PROGRESS
            existing.request_hash = digest
            existing.response = {}
            existing.expires_at = now + timedelta(hours=settings.idempotency_ttl_hours)
            self.db.flush()
            return "process", digest, None
        return "replay", digest, existing.response

    def complete(self, key: str | None, digest: str | None, response: dict[str, Any]) -> None:
        if not key:
            return
        row = self.db.query(IdempotencyKey).filter(IdempotencyKey.key == key).first()
        if not row:
            row = IdempotencyKey(key=key, request_hash=digest, response=response, status=COMPLETED)
            self.db.add(row)
            return
        row.request_hash = digest
        row.response = response
        row.status = COMPLETED

    def fail(self, key: str | None) -> None:
        if not key:
            return
        row = self.db.query(IdempotencyKey).filter(IdempotencyKey.key == key).first()
        if row:
            row.status = FAILED
