from app.services.underwriting_rules import get_alt_data_rules, get_decision_rules


def evaluate_decision(eligibility: dict, risk: dict, fraud: dict, alt_data: dict | None = None) -> dict:
    rules = get_decision_rules()
    alt_rules = get_alt_data_rules()
    alt_data = alt_data or {}
    reasons = []
    segment = eligibility.get("profile", {}).get("segment")

    if not eligibility.get("eligible"):
        return {
            "decision": "reject",
            "status": "ineligible",
            "reasons": [eligibility.get("reason") or "Platform eligibility failed"],
            "explainability": _build_explainability(eligibility, risk, fraud, alt_data),
        }

    if fraud.get("blocked"):
        return {
            "decision": "reject",
            "status": "rejected",
            "reasons": fraud.get("signals") or ["Fraud stacking guard triggered"],
            "explainability": _build_explainability(eligibility, risk, fraud, alt_data),
        }

    if segment == "thin_file" and alt_data.get("used"):
        return _thin_file_decision(eligibility, risk, fraud, alt_data, alt_rules)

    default_p = risk.get("defaultProbability", 0)
    fraud_p = fraud.get("fraudProbability", risk.get("fraudProbability", 0))

    if default_p >= rules["rejectDefaultProbabilityGte"]:
        reasons.append(f"Default probability {default_p:.1%} exceeds reject threshold")
    if fraud_p >= rules["rejectFraudProbabilityGte"]:
        reasons.append(f"Fraud probability {fraud_p:.1%} exceeds reject threshold")

    if reasons:
        return {
            "decision": "reject",
            "status": "rejected",
            "reasons": reasons,
            "explainability": _build_explainability(eligibility, risk, fraud, alt_data),
        }

    review_reasons = []
    if default_p >= rules["reviewDefaultProbabilityGte"]:
        review_reasons.append(f"Default probability {default_p:.1%} requires manual review")
    if fraud_p >= rules["reviewFraudProbabilityGte"]:
        review_reasons.append(f"Fraud probability {fraud_p:.1%} requires manual review")
    if fraud.get("signals"):
        review_reasons.extend(fraud["signals"])

    if review_reasons:
        return {
            "decision": "review",
            "status": "under_review",
            "reasons": review_reasons,
            "explainability": _build_explainability(eligibility, risk, fraud, alt_data),
        }

    return {
        "decision": "approve",
        "status": "offers_ready",
        "reasons": ["Meets platform, fraud, and risk thresholds"],
        "explainability": _build_explainability(eligibility, risk, fraud, alt_data),
    }


def _thin_file_decision(eligibility, risk, fraud, alt_data, alt_rules) -> dict:
    score = float(alt_data.get("altDataScore") or 0)
    explain = _build_explainability(eligibility, risk, fraud, alt_data)

    if not alt_data.get("thinFileEligible"):
        return {
            "decision": "reject",
            "status": "rejected",
            "reasons": alt_data.get("reasons") or ["Alternative-data score below thin-file cutoff"],
            "explainability": explain,
        }

    if score >= alt_rules["approveScoreGte"] and not fraud.get("signals"):
        return {
            "decision": "approve",
            "status": "offers_ready",
            "reasons": [
                f"Thin-file approved on alternative data (score {score:.2f})",
                "Bureau PD used as advisory only — no CIBIL-prime path",
            ],
            "explainability": explain,
        }

    reasons = [f"Thin-file starter path — alt-data score {score:.2f} requires review"]
    reasons.extend(fraud.get("signals") or [])
    return {
        "decision": "review",
        "status": "under_review",
        "reasons": reasons,
        "explainability": explain,
    }


def _build_explainability(eligibility: dict, risk: dict, fraud: dict, alt_data: dict | None = None) -> dict:
    return {
        "segment": eligibility.get("profile", {}).get("segment"),
        "riskBand": risk.get("riskBand"),
        "defaultProbability": risk.get("defaultProbability"),
        "fraudProbability": fraud.get("fraudProbability", risk.get("fraudProbability")),
        "riskFactors": risk.get("riskFactors", []),
        "shapFactors": risk.get("shapFactors", []),
        "fraudSignals": fraud.get("signals", []),
        "finbertSignal": risk.get("finbertSignal"),
        "altDataScore": (alt_data or {}).get("altDataScore"),
        "altDataUsed": bool((alt_data or {}).get("used")),
    }
