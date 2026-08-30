"""Shared applicant feature engineering for ML, risk, and monitoring."""

from __future__ import annotations

from app.core.privacy import mask_pan
from app.services.profile import calculate_foir, classify_profile


def engineer_features(
    input_data: dict,
    financial_notes: str | None = None,
    credit_line: dict | None = None,
) -> dict:
    profile = classify_profile(input_data)
    foir = calculate_foir(input_data)
    monthly_income = max(input_data["monthly_income"], 1)
    cibil = input_data.get("cibil_score")
    existing_emis = input_data.get("existing_emis", 0)
    bank_balance = input_data.get("bank_statement_avg_balance", 0)

    amount_to_income = input_data["amount"] / monthly_income
    obligation_ratio = existing_emis / monthly_income
    balance_coverage = bank_balance / monthly_income
    credit_utilisation = min(1.0, input_data["amount"] / (monthly_income * 12.0))
    originated = int((credit_line or {}).get("originatedCount") or 0)
    on_time = int((credit_line or {}).get("onTimeRepayments") or 0)
    repayment_consistency = round(on_time / originated, 3) if originated else None

    structured = {
        "RevolvingUtilizationOfUnsecuredLines": min(2.0, credit_utilisation),
        "age": float(input_data["age"]),
        "NumberOfTime30-59DaysPastDueNotWorse": 1.0 if cibil and cibil < 680 else 0.0,
        "DebtRatio": min(2.0, obligation_ratio),
        "MonthlyIncome": float(monthly_income),
        "NumberOfOpenCreditLinesAndLoans": min(
            15.0,
            round(existing_emis / 4000.0) + (2.0 if input_data["tenure_months"] >= 24 else 1.0),
        ),
        "NumberOfTimes90DaysLate": 1.0 if cibil and cibil < 620 else 0.0,
        "NumberRealEstateLoansOrLines": 2.0 if input_data["amount"] >= 500000 else 1.0,
        "NumberOfTime60-89DaysPastDueNotWorse": 1.0 if cibil and cibil < 650 else 0.0,
        "NumberOfDependents": 0.0,
    }

    return {
        "applicantId": mask_pan(input_data.get("pan")),
        "segment": profile["segment"],
        "profileLabel": profile["label"],
        "monthlyIncome": monthly_income,
        "cibilScore": cibil,
        "amountToIncome": round(amount_to_income, 3),
        "debtToIncome": round(obligation_ratio, 3),
        "obligationRatio": round(obligation_ratio, 3),
        "emiToIncome": foir["foir"],
        "creditUtilisation": round(credit_utilisation, 3),
        "repaymentConsistency": repayment_consistency,
        "balanceCoverage": round(balance_coverage, 3),
        "foir": foir["foir"],
        "foirPercent": foir["foirPercent"],
        "proposedEmi": foir["proposedEmi"],
        "incomeType": input_data["income_type"],
        "cityTier": input_data.get("city_tier", 1),
        "tenureMonths": input_data["tenure_months"],
        "loanAmount": input_data["amount"],
        "financialNotesLength": len(financial_notes or ""),
        "structuredFeatures": structured,
        "profile": profile,
        "foirDetails": foir,
    }
