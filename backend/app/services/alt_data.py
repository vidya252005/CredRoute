"""Mock alternative-data underwriting for thin-file / low-CIBIL applicants.

Device signals are synthetic and deterministic from PAN — not real SMS, contacts,
or handset IDs. Cash-flow uses the bank-balance field the applicant already supplied.
"""

from __future__ import annotations

import hashlib

from app.services.underwriting_rules import load_underwriting_rules


def _alt_rules() -> dict:
    return load_underwriting_rules()["altData"]


def is_thin_file_bureau(input_data: dict) -> bool:
    cibil = input_data.get("cibil_score")
    threshold = _alt_rules()["cibilThinFileBelow"]
    return cibil is None or cibil < threshold


def mock_device_signals(pan: str, overrides: dict | None = None) -> dict:
    digest = hashlib.sha256((pan or "UNKNOWN").encode("utf-8")).digest()
    derived = {
        "androidApiLevel": 28 + (digest[0] % 7),
        "simTenureMonths": 6 + (digest[1] % 48),
        "deviceAgeMonths": 8 + (digest[3] % 36),
        "rooted": digest[2] % 17 == 0,
        "signalSource": "synthetic_device_proxy",
    }
    if overrides:
        for key in ("androidApiLevel", "simTenureMonths", "deviceAgeMonths", "rooted"):
            if key in overrides and overrides[key] is not None:
                derived[key] = overrides[key]
    return derived


def score_alt_data(
    input_data: dict,
    credit_line: dict | None = None,
    device_overrides: dict | None = None,
) -> dict:
    rules = _alt_rules()
    device = mock_device_signals(input_data.get("pan", ""), device_overrides)
    income = max(float(input_data["monthly_income"]), 1.0)
    cashflow_ratio = float(input_data.get("bank_statement_avg_balance") or 0) / income
    obligation_ratio = float(input_data.get("existing_emis") or 0) / income
    on_time = int((credit_line or {}).get("onTimeRepayments") or 0)
    income_type = input_data.get("income_type") or "salaried"
    city_tier = int(input_data.get("city_tier") or 2)

    reasons: list[str] = []
    score = 0.42

    if cashflow_ratio >= rules["minCashflowRatio"]:
        score += 0.18
        reasons.append(f"Bank-balance coverage {cashflow_ratio:.0%} of monthly income")
    else:
        reasons.append("Thin cash-flow buffer versus declared income")

    if obligation_ratio <= rules["maxObligationRatio"]:
        score += 0.12
    else:
        score -= 0.08
        reasons.append("Existing EMIs consume a large share of income")

    if device["simTenureMonths"] >= rules["minSimTenureMonths"]:
        score += 0.1
        reasons.append(f"SIM tenure {device['simTenureMonths']} months (proxy for stability)")
    else:
        reasons.append("Short SIM tenure — weaker identity-stability signal")

    if device["androidApiLevel"] >= 29:
        score += 0.04
    if device["rooted"]:
        score -= 0.25
        reasons.append("Rooted-device proxy flagged")

    if income_type == "salaried":
        score += 0.06
    elif income_type == "gig":
        score -= 0.04
        reasons.append("Gig income — higher cash-flow volatility")

    if city_tier >= 3:
        score -= 0.03

    if on_time:
        score += min(0.2, on_time * 0.08)
        reasons.append(f"{on_time} on-time repayment(s) on CredRoute credit line")

    score = round(max(0.0, min(1.0, score)), 3)
    thin_file = is_thin_file_bureau(input_data)
    eligible = (
        thin_file
        and score >= rules["reviewScoreGte"]
        and not device["rooted"]
        and obligation_ratio <= rules["maxObligationRatio"]
    )

    features = {
        "cashflowRatio": round(cashflow_ratio, 3),
        "obligationRatio": round(obligation_ratio, 3),
        "onTimeRepayments": on_time,
        "incomeType": income_type,
        "cityTier": city_tier,
        **device,
    }

    return {
        "used": thin_file,
        "thinFileEligible": eligible,
        "altDataScore": score,
        "features": features,
        "reasons": reasons[:4],
        "thresholds": {
            "approveScoreGte": rules["approveScoreGte"],
            "reviewScoreGte": rules["reviewScoreGte"],
        },
        "disclaimer": "Device fields are synthetic proxies for demo — not SMS, contacts, or live handset IDs.",
    }
