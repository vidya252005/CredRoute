"""Lender adapter factory — routing never switches on lender codes."""

from __future__ import annotations

from app.routing.adapter import LenderAdapter, MockLenderAdapter

_REGISTRY: dict[str, type[LenderAdapter]] = {}


def register_adapter(code: str, adapter_cls: type[LenderAdapter]) -> None:
    _REGISTRY[code] = adapter_cls


class LenderAdapterFactory:
    def get(self, lender_code: str) -> LenderAdapter:
        adapter_cls = _REGISTRY.get(lender_code)
        if adapter_cls is not None:
            return adapter_cls(lender_code)
        return MockLenderAdapter(lender_code)
