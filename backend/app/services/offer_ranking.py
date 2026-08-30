from app.services.profile import estimate_emi


def rank_offers(offers: list[dict], input_data: dict, profile: dict) -> list[dict]:
    if not offers:
        return []
    rates = [offer["interestRate"] for offer in offers if offer.get("interestRate")]
    lowest_rate = min(rates) if rates else 1
    ranked = []
    for offer in offers:
        rate = offer["interestRate"] or lowest_rate or 1
        interest_score = lowest_rate / rate if rate else 0
        max_amount = offer.get("maxAmount") or input_data["amount"]
        amount_match = min(1, input_data["amount"] / max_amount) if max_amount else 0
        profile_fit = offer.get("profileFit", 0.5)
        score = round(
            0.3 * offer["approvalProbability"]
            + 0.2 * interest_score
            + 0.15 * amount_match
            + 0.2 * profile_fit
            + 0.1 * offer["successRate"]
            + 0.05 * offer["journeyScore"],
            3,
        )
        ranked.append(
            {
                **offer,
                "score": score,
                "monthlyPayment": round(
                    estimate_emi(input_data["amount"], offer["interestRate"], input_data["tenure_months"])
                ),
            }
        )
    ranked.sort(key=lambda item: item["score"], reverse=True)
    for index, offer in enumerate(ranked, start=1):
        offer["rank"] = index
        offer["routingReason"] = (
            f"Best fit for {profile['label']} applicants in tier-{input_data['city_tier']} cities"
            if index == 1
            else f"Alternative {profile['label'].lower()} offer"
        )
    return ranked
