"""Map PD + segment + credit line into a personalized amount / tenure / APR."""

from __future__ import annotations

from app.services.profile import estimate_emi


def _apr(segment: str, default_p: float, alt_score: float, first_loan: bool) -> float:
    if segment == "thin_file":
        base = 21.0 - alt_score * 5.0
        if first_loan:
            base += 1.5
        return round(max(16.0, min(24.0, base)), 2)
    if segment == "prime":
        return round(max(11.0, min(14.5, 11.2 + default_p * 12)), 2)
    return round(max(13.5, min(19.0, 14.0 + default_p * 16)), 2)


def _tenure(segment: str, requested: int, first_loan: bool, default_p: float) -> int:
    if segment == "thin_file" and first_loan:
        return min(12, max(6, requested if requested <= 12 else 12))
    if default_p >= 0.22:
        return min(requested, 12)
    return requested


def price_offer(
    input_data: dict,
    risk: dict,
    alt_data: dict,
    credit_line: dict,
    segment: str,
) -> dict:
    requested = int(input_data["amount"])
    default_p = float(risk.get("defaultProbability") or 0.2)
    first_loan = bool(credit_line.get("firstLoan"))
    alt_score = float(alt_data.get("altDataScore") or 0.5)
    line_cap = int(credit_line.get("currentLimit") or requested)

    if segment == "thin_file":
        offered_amount = max(10000, min(requested, line_cap))
    elif default_p >= 0.22:
        offered_amount = max(10000, min(requested, int(requested * 0.45)))
    elif default_p >= 0.12:
        offered_amount = max(10000, min(requested, int(requested * 0.75)))
    else:
        offered_amount = requested
    tenure = _tenure(segment, int(input_data["tenure_months"]), first_loan, default_p)
    apr = _apr(segment, default_p, alt_score, first_loan)
    emi = round(estimate_emi(offered_amount, apr, tenure))
    capped = offered_amount < requested

    reasons = []
    if first_loan and segment == "thin_file":
        reasons.append("Starter ticket for first-loan / thin-file credit building")
    if capped and segment == "thin_file":
        reasons.append(
            f"Requested ₹{requested:,} capped to ₹{offered_amount:,} by thin-file credit line"
        )
    elif capped:
        reasons.append(
            f"Requested ₹{requested:,} reduced to ₹{offered_amount:,} by risk band"
        )
    if not reasons:
        reasons.append("Amount and APR priced from risk band")

    return {
        "requestedAmount": requested,
        "offeredAmount": offered_amount,
        "tenureMonths": tenure,
        "apr": apr,
        "monthlyPayment": emi,
        "capped": capped,
        "firstLoan": first_loan,
        "nextLimit": credit_line.get("nextLimit"),
        "currentLimit": line_cap,
        "reasons": reasons,
        "riskBand": risk.get("riskBand"),
    }
