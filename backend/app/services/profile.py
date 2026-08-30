FOIR_CAP = 0.6


def estimate_emi(amount: float, annual_rate: float, tenure_months: int) -> float:
    monthly_rate = annual_rate / 100 / 12
    if not monthly_rate:
        return amount / tenure_months
    return (
        amount * monthly_rate * (1 + monthly_rate) ** tenure_months
    ) / ((1 + monthly_rate) ** tenure_months - 1)


def calculate_foir(input_data: dict, estimated_rate: float = 14) -> dict:
    proposed_emi = estimate_emi(input_data["amount"], estimated_rate, input_data["tenure_months"])
    total_emi = input_data.get("existing_emis", 0) + proposed_emi
    foir = total_emi / max(input_data["monthly_income"], 1)
    return {
        "foir": round(foir, 3),
        "proposedEmi": round(proposed_emi),
        "totalEmi": round(total_emi),
        "foirPercent": round(foir * 100, 1),
    }


def classify_profile(input_data: dict) -> dict:
    cibil = input_data.get("cibil_score")
    has_cibil = cibil is not None and cibil > 0
    if not has_cibil or cibil < 650:
        return {
            "segment": "thin_file",
            "label": "Thin-file",
            "detail": (
                f"CIBIL {cibil} — below prime bureau threshold"
                if has_cibil
                else "No CIBIL score — new-to-credit applicant"
            ),
        }
    if cibil >= 750 and input_data["income_type"] == "salaried":
        return {
            "segment": "prime",
            "label": "Prime",
            "detail": f"CIBIL {cibil} salaried applicant",
        }
    return {
        "segment": "near_prime",
        "label": "Near-prime",
        "detail": f"CIBIL {cibil} {input_data['income_type'].replace('_', ' ')} applicant",
    }


def lender_fit_score(lender: dict, profile: dict) -> float:
    segment = profile["segment"]
    if lender.get("serves_thin_file") and segment == "thin_file":
        return 1.0
    if lender.get("serves_prime") and segment == "prime":
        return 1.0
    if lender.get("serves_near_prime") and segment == "near_prime":
        return 0.95
    if lender.get("serves_thin_file") and segment == "near_prime":
        return 0.55
    if lender.get("serves_near_prime") and segment == "thin_file":
        return 0.35
    if lender.get("serves_prime") and segment == "near_prime":
        return 0.7
    return 0.2


def normalize_pan(pan: str) -> str:
    return (pan or "").strip().upper()


def is_valid_pan(pan: str) -> bool:
    import re

    return bool(re.fullmatch(r"[A-Z]{5}[0-9]{4}[A-Z]", normalize_pan(pan)))
