"""Shared domain enumerations for credit decisioning and routing."""

from __future__ import annotations

from enum import Enum


class EmploymentType(str, Enum):
    salaried = "salaried"
    self_employed = "self_employed"
    gig = "gig"
    msme = "msme"


class ProductType(str, Enum):
    personal_loan = "personal_loan"


class DecisionOutcome(str, Enum):
    approve = "approve"
    reject = "reject"
    review = "review"


class FraudRiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ConsentPurpose(str, Enum):
    bureau = "bureau"
    cashflow = "cashflow"
    device_proxy = "device_proxy"
    repayment = "repayment"


class ConsentStatus(str, Enum):
    CONSENT_REQUIRED = "CONSENT_REQUIRED"
    CONSENT_VALID = "CONSENT_VALID"
    CONSENT_EXPIRED = "CONSENT_EXPIRED"
    CONSENT_REVOKED = "CONSENT_REVOKED"


class CircuitStateName(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class LenderAttemptStatus(str, Enum):
    SUCCESS = "success"
    INELIGIBLE = "ineligible"
    FAILED = "failed"
    FAILED_TIMEOUT = "failed_timeout"
    FAILED_PROVIDER = "failed_provider"
    CIRCUIT_OPEN = "circuit_open"
    UNKNOWN = "unknown"


class RoutingStrategyName(str, Enum):
    balanced = "balanced"
    best_approval = "best_approval"
    lowest_cost = "lowest_cost"
    customer_preferred = "customer_preferred"
