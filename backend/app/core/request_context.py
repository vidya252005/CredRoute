"""Request-scoped identifiers. Never put PAN or secrets here."""

from __future__ import annotations

import uuid
from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


def current_request_id() -> str:
    return request_id_var.get() or "-"


def bind_request_id(value: str | None) -> str:
    request_id = (value or "").strip() or str(uuid.uuid4())
    request_id_var.set(request_id)
    return request_id
