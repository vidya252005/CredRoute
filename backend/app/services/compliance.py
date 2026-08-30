"""Consent record and borrower-facing adverse-action reasons."""

from __future__ import annotations


CONSENT_PURPOSES = [
    {
        "id": "bureau",
        "label": "CIBIL / bureau score you entered (no live bureau pull)",
    },
    {
        "id": "cashflow",
        "label": "Average bank balance as a cash-flow signal",
    },
    {
        "id": "device_proxy",
        "label": "Synthetic device/SIM tenure proxy (not SMS, contacts, or live handset IDs)",
    },
    {
        "id": "repayment",
        "label": "CredRoute repayment history on this PAN, if any",
    },
]


def build_consent(input_data: dict, alt_data: dict, granted: bool) -> dict:
    used = [CONSENT_PURPOSES[0], CONSENT_PURPOSES[1], CONSENT_PURPOSES[3]]
    if alt_data.get("used"):
        used = CONSENT_PURPOSES
    return {
        "granted": granted,
        "purposes": used,
        "notCollected": ["SMS logs", "phone contacts", "live GPS", "third-party data sales"],
        "altDataUsed": bool(alt_data.get("used")),
        "panMasked": True,
    }


def _borrower_facing(reason: str) -> str:
    text = reason.lower()
    if "default probability" in text or ("risk" in text and "exceeds" in text):
        return "The application did not meet our credit-risk cutoff for the amount requested."
    if "fraud" in text or "stacking" in text or "velocity" in text:
        return "We could not complete verification because of repeated or overlapping applications."
    if "foir" in text:
        return "Existing and proposed EMIs would exceed a safe share of monthly income."
    if "income" in text:
        return "Declared income is below the minimum for this product."
    if "age" in text:
        return "Age is outside the supported range for this product."
    if "alternate data" in text or "cash-flow" in text or "thin" in text:
        return "Alternative cash-flow and stability signals were not strong enough for a first loan."
    if "rooted" in text:
        return "Device integrity checks did not pass."
    if "eligible" in text or "platform" in text:
        return "The application did not meet platform eligibility rules."
    return reason


def adverse_action(decision: dict, eligibility: dict, alt_data: dict, fraud: dict) -> dict | None:
    if decision.get("decision") != "reject":
        return None

    raw = list(decision.get("reasons") or [])
    if eligibility.get("reason"):
        raw.insert(0, eligibility["reason"])
    if alt_data.get("used") and not alt_data.get("thinFileEligible"):
        raw.extend(alt_data.get("reasons") or [])
    if fraud.get("signals"):
        raw.extend(fraud["signals"])

    seen: set[str] = set()
    reasons: list[str] = []
    for item in raw:
        mapped = _borrower_facing(str(item))
        if mapped not in seen:
            seen.add(mapped)
            reasons.append(mapped)
        if len(reasons) == 3:
            break

    if not reasons:
        reasons = ["We are unable to offer credit on this application at this time."]

    return {
        "required": True,
        "reasons": reasons,
        "notice": (
            "These are the principal reasons for the decision. "
            "This is a portfolio demo — not a regulated adverse-action notice."
        ),
    }
