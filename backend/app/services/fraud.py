from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.entities import BorrowerProfile, LoanApplication
from app.core.identity import SensitiveIdentity
from app.services.underwriting_rules import get_fraud_rules


def score_fraud_signals(input_data: dict, risk: dict, recent_pans: int = 0) -> dict:
    rules = get_fraud_rules()
    signals = []
    score = float(risk.get("fraudProbability") or 0)

    if recent_pans >= rules["velocityPanLimit"]:
        signals.append(f"PAN velocity: {recent_pans} applications in {rules['stackingWindowHours']}h")
        score = min(0.99, score + 0.2)

    stacking_limit = settings.stacking_limit or rules["stackingLimit"]
    if settings.stacking_enabled and recent_pans >= stacking_limit:
        signals.append(f"Loan stacking limit exceeded ({stacking_limit} in window)")
        score = min(0.99, score + 0.35)

    age = input_data.get("age", 0)
    low, high = rules["highRiskAgeBounds"]
    if low <= age <= high and (input_data.get("cibil_score") or 0) < 640:
        signals.append("Young applicant with weak bureau score")
        score = min(0.99, score + 0.08)

    if input_data.get("existing_emis", 0) > input_data["monthly_income"] * 0.55:
        signals.append("Existing obligations exceed 55% of income")
        score = min(0.99, score + 0.1)

    if input_data["amount"] > input_data["monthly_income"] * 20:
        signals.append("Ticket size exceeds 20× monthly income")
        score = min(0.99, score + 0.12)

    if input_data.get("rooted") is True:
        signals.append("Rooted-device proxy flagged")
        score = min(0.99, score + 0.18)

    return {
        "fraudProbability": round(min(0.99, score), 3),
        "signals": signals,
        "recentPanApplications": recent_pans,
        "stackingLimit": stacking_limit,
        "blocked": settings.stacking_enabled and recent_pans >= stacking_limit,
    }


def evaluate_fraud(db: Session, input_data: dict, risk: dict) -> dict:
    rules = get_fraud_rules()
    identity = SensitiveIdentity(input_data.get("pan", ""))
    window = timedelta(hours=rules["stackingWindowHours"])
    since = datetime.now(UTC) - window

    recent_pans = 0
    if db is not None:
        recent_pans = (
            db.query(LoanApplication)
            .join(BorrowerProfile, LoanApplication.borrower_profile_id == BorrowerProfile.id)
            .filter(BorrowerProfile.pan_hash == identity.pan_hash, LoanApplication.created_at >= since)
            .count()
        )

    return score_fraud_signals(input_data, risk, recent_pans)
