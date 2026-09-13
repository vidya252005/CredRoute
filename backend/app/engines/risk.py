"""Credit risk engine — wraps the existing ML/heuristic predictor."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.core.cache import cache_get, cache_set
from app.domain.context import DecisionContext
from app.domain.results import RiskResult
from app.engines.feature_builder import FeatureBuilder
from app.services.risk import calculate_risk


class RiskEngine(ABC):
    @abstractmethod
    def score(self, context: DecisionContext) -> RiskResult:
        raise NotImplementedError


class CreditRiskEngine(RiskEngine):
    def __init__(self, cache_ttl_seconds: int = 120):
        self.cache_ttl_seconds = cache_ttl_seconds

    def score(self, context: DecisionContext) -> RiskResult:
        features = FeatureBuilder.build(context)
        input_data = context.to_input_data()
        raw = calculate_risk(input_data, context.financial_notes)
        segment = features.get("segment")
        return RiskResult(
            default_probability=float(raw.get("defaultProbability") or 0),
            risk_band=str(raw.get("riskBand") or "MEDIUM"),
            segment=segment,
            confidence=float(raw.get("confidence") or 0),
            model_source=raw.get("modelSource"),
            model_version=str(raw.get("modelAuc") or raw.get("modelSource") or ""),
            risk_factors=list(raw.get("riskFactors") or []),
            shap_factors=list(raw.get("shapFactors") or []),
            engineered_features=raw.get("engineeredFeatures") or features,
            raw=raw,
        )


class CachedRiskEngine(RiskEngine):
    def __init__(self, inner: RiskEngine | None = None, ttl_seconds: int = 120):
        self.inner = inner or CreditRiskEngine()
        self.ttl_seconds = ttl_seconds

    def score(self, context: DecisionContext) -> RiskResult:
        import hashlib

        from app.core.identity import pan_lookup_hash

        input_data = context.to_input_data()
        notes_token = hashlib.sha256((context.financial_notes or "").encode("utf-8")).hexdigest()[:16]
        cache_key = (
            f"risk:{pan_lookup_hash(str(input_data.get('pan') or ''))}:{input_data.get('amount')}:{input_data.get('tenure_months')}:"
            f"{input_data.get('monthly_income')}:{input_data.get('cibil_score')}:"
            f"{input_data.get('existing_emis')}:{input_data.get('income_type')}:"
            f"{input_data.get('bank_statement_avg_balance')}:{input_data.get('city_tier')}:"
            f"{notes_token}"
        )
        cached = cache_get(cache_key)
        if cached:
            return RiskResult(
                default_probability=float(cached.get("defaultProbability") or 0),
                risk_band=str(cached.get("riskBand") or "MEDIUM"),
                segment=cached.get("engineeredFeatures", {}).get("segment"),
                confidence=float(cached.get("confidence") or 0),
                model_source=cached.get("modelSource"),
                risk_factors=list(cached.get("riskFactors") or []),
                shap_factors=list(cached.get("shapFactors") or []),
                engineered_features=cached.get("engineeredFeatures") or {},
                raw=cached,
            )
        result = self.inner.score(context)
        cache_set(cache_key, result.raw, self.ttl_seconds)
        return result
