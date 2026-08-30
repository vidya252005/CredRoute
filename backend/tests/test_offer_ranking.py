from app.services.offer_ranking import rank_offers


def test_rank_offers_prefers_better_fit():
    offers = [
        {
            "interestRate": 14,
            "approvalProbability": 0.7,
            "maxAmount": 500000,
            "profileFit": 0.9,
            "successRate": 0.8,
            "journeyScore": 0.8,
        },
        {
            "interestRate": 12,
            "approvalProbability": 0.9,
            "maxAmount": 500000,
            "profileFit": 0.95,
            "successRate": 0.9,
            "journeyScore": 0.9,
        },
    ]
    ranked = rank_offers(
        offers,
        {"amount": 100000, "tenure_months": 12, "city_tier": 1},
        {"label": "Prime", "segment": "prime"},
    )
    assert ranked[0]["rank"] == 1
    assert ranked[0]["interestRate"] == 12
