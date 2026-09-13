# Decision engine

Order of work:

1. Risk (cached ML / heuristic)
2. Affordability (FOIR)
3. Alternative data (thin-file path)
4. Credit-line preview / persist
5. Offer pricing
6. Eligibility
7. Fraud (priced ticket)
8. Decision policy → approve / review / reject
9. Consent + adverse action

`ApplicationInput` is immutable. Derived results live on `DecisionSnapshot`. Routing gets a `RoutingContext`, not a rebuilt pipeline bag.

JSON on `LoanApplication.eligibility` / `risk` is a **redacted snapshot**. Authoritative rows: `risk_assessments`, `fraud_assessments`, `decision_audits`.
