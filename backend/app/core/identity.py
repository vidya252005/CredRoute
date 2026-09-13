"""PAN hashing and in-memory identity. Raw PAN is never the persistence key."""

from __future__ import annotations

import hashlib
import hmac
import re

from app.core.config import settings
from app.core.privacy import mask_pan

_PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")


def normalize_pan(pan: str) -> str:
    return (pan or "").strip().upper()


def is_valid_pan(pan: str) -> bool:
    return bool(_PAN_RE.fullmatch(normalize_pan(pan)))


def pan_lookup_hash(pan: str) -> str:
    normalized = normalize_pan(pan)
    digest = hmac.new(
        settings.pan_hmac_secret.encode("utf-8"),
        normalized.encode("utf-8"),
        hashlib.sha256,
    )
    return digest.hexdigest()


class SensitiveIdentity:
    """Holds raw PAN only in memory. Repr/str never leak it."""

    __slots__ = ("_pan", "pan_hash", "pan_masked")

    def __init__(self, pan: str):
        raw = normalize_pan(pan)
        self._pan = raw
        self.pan_hash = pan_lookup_hash(raw)
        self.pan_masked = mask_pan(raw) or ""

    def reveal(self) -> str:
        return self._pan

    def __repr__(self) -> str:
        return f"SensitiveIdentity(pan={self.pan_masked!r})"

    def __str__(self) -> str:
        return self.pan_masked
