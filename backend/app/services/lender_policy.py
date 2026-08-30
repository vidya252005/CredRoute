def resolve_cibil(input_data: dict) -> int | None:
    score = input_data.get("cibil_score", input_data.get("cibilScore", input_data.get("creditScore")))
    if score in ("", None, 0):
        return None
    parsed = int(score)
    return parsed if parsed > 0 else None


def normalize_lender_policy(lender: dict) -> dict:
    return {
        "min_income": lender.get("min_income", lender.get("minIncome")),
        "min_credit_score": lender.get("min_credit_score", lender.get("minCreditScore")),
        "max_amount": lender.get("max_amount", lender.get("maxAmount")),
        "max_foir": lender.get("max_foir", lender.get("maxFoir", 0.6)),
        "base_interest_rate": lender.get("base_interest_rate", lender.get("baseInterestRate", 14)),
        "income_types": lender.get("income_types", lender.get("incomeTypes")),
        "city_tiers": lender.get("city_tiers", lender.get("cityTiers")),
        "serves_prime": lender.get("serves_prime", lender.get("servesPrime", False)),
        "serves_near_prime": lender.get("serves_near_prime", lender.get("servesNearPrime", False)),
        "serves_thin_file": lender.get("serves_thin_file", lender.get("servesThinFile", False)),
    }


def check_hard_policy_gates(policy: dict, input_data: dict, lender_name: str) -> dict | None:
    missing = [
        key
        for key, value in (
            ("min_income", policy["min_income"]),
            ("max_amount", policy["max_amount"]),
            ("min_credit_score", policy["min_credit_score"]),
        )
        if value is None
    ]
    if missing:
        return {"eligible": False, "reason": f"{lender_name} policy incomplete ({', '.join(missing)})"}

    if input_data["amount"] > policy["max_amount"]:
        return {
            "eligible": False,
            "reason": f"Requested amount exceeds {lender_name} max ticket size (₹{policy['max_amount']:,})",
        }

    if input_data["monthly_income"] < policy["min_income"]:
        return {
            "eligible": False,
            "reason": f"Monthly income below {lender_name} minimum (₹{policy['min_income']:,})",
        }

    cibil = resolve_cibil(input_data)
    min_score = policy["min_credit_score"]
    if min_score and min_score > 0:
        if cibil is None:
            if not policy.get("serves_thin_file"):
                return {
                    "eligible": False,
                    "reason": f"{lender_name} requires a bureau score (minimum {min_score})",
                }
        elif cibil < min_score:
            return {
                "eligible": False,
                "reason": f"CIBIL {cibil} below {lender_name} threshold ({min_score})",
            }

    return None
