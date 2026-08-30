from app.services.profile import calculate_foir, classify_profile
from app.services.underwriting_rules import get_platform_rules, load_underwriting_rules


def evaluate_eligibility(input_data: dict, offered_amount: int | None = None, offered_tenure: int | None = None) -> dict:
    rules = get_platform_rules()
    eval_data = dict(input_data)
    if offered_amount is not None:
        eval_data["amount"] = offered_amount
    if offered_tenure is not None:
        eval_data["tenure_months"] = offered_tenure
    profile = classify_profile(input_data)
    foir_details = calculate_foir(eval_data)
    alternate_ok = (
        input_data.get("bank_statement_avg_balance", 0) >= input_data["monthly_income"] * 0.8
        or input_data["income_type"] == "salaried"
    )

    checks = [
        {
            "label": "Age",
            "passed": rules["minAge"] <= input_data["age"] <= rules["maxAge"],
            "detail": f"{input_data['age']} years; supported range is {rules['minAge']}–{rules['maxAge']}",
        },
        {
            "label": "Monthly income",
            "passed": input_data["monthly_income"] >= rules["minMonthlyIncome"],
            "detail": f"₹{input_data['monthly_income']:,}; minimum is ₹{rules['minMonthlyIncome']:,}",
        },
        {
            "label": "FOIR",
            "passed": foir_details["foir"] <= rules["maxFoir"],
            "detail": (
                f"{foir_details['foirPercent']}% "
                f"(existing EMIs ₹{input_data.get('existing_emis', 0):,} + "
                f"proposed ₹{foir_details['proposedEmi']:,}); cap is {rules['maxFoir'] * 100}%"
            ),
        },
        {
            "label": "Profile segment",
            "passed": True,
            "detail": f"{profile['label']} — {profile['detail']}",
        },
        {
            "label": "Alternate data",
            "passed": profile["segment"] != "thin_file" or alternate_ok,
            "detail": (
                "Not required for bureau-backed profile"
                if profile["segment"] != "thin_file"
                else f"Avg bank balance ₹{input_data.get('bank_statement_avg_balance', 0):,}"
            ),
        },
        {
            "label": "Requested amount",
            "passed": eval_data["amount"] <= input_data["monthly_income"] * rules["maxAmountIncomeMultiple"],
            "detail": (
                f"₹{eval_data['amount']:,}"
                + (" after offer cap" if offered_amount is not None else "")
                + f"; capped at {rules['maxAmountIncomeMultiple']}× monthly income"
            ),
        },
    ]

    failed = next((check for check in checks if not check["passed"]), None)
    return {
        "eligible": failed is None,
        "checks": checks,
        "reason": f"{failed['label']}: {failed['detail']}" if failed else None,
        "profile": profile,
        "foir": foir_details,
        "rulesVersion": load_underwriting_rules().get("version", "1.0.0"),
    }
