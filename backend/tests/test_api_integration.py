"""FastAPI integration tests for the credit decisioning pipeline."""

import uuid

PRIME_APPLICANT = {
    "name": "Aarav Mehta",
    "pan": "ABCDE1234F",
    "age": 29,
    "monthlyIncome": 85000,
    "incomeType": "salaried",
    "cibilScore": 780,
    "existingEmis": 12000,
    "bankStatementAvgBalance": 90000,
    "cityTier": 1,
    "amount": 300000,
    "tenureMonths": 24,
    "financialNotes": "Stable salaried income with consistent savings.",
    "consentAltData": True,
}

THIN_FILE_APPLICANT = {
    "name": "Priya Sharma",
    "pan": "FGHIJ5678K",
    "age": 26,
    "monthlyIncome": 28000,
    "incomeType": "gig",
    "cibilScore": 615,
    "existingEmis": 4000,
    "bankStatementAvgBalance": 32000,
    "cityTier": 2,
    "amount": 300000,
    "tenureMonths": 12,
    "financialNotes": "Gig worker with inconsistent income.",
    "consentAltData": True,
    "rooted": False,
    "simTenureMonths": 24,
    "androidApiLevel": 33,
}


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_evaluate_prime_applicant(client):
    response = client.post("/api/applications/evaluate", json=PRIME_APPLICANT)
    assert response.status_code == 200
    body = response.json()

    assert body["id"]
    assert body["eligibility"]["eligible"] is True
    assert body["risk"]["defaultProbability"] is not None
    assert body["risk"]["decision"]["decision"] in ("approve", "review", "reject")
    assert body["applicant"]["pan"] == "ABCXX1234X"
    assert isinstance(body.get("offers"), list)
    assert body["personalizedOffer"]["offeredAmount"] > 50000
    assert body["personalizedOffer"]["offeredAmount"] <= PRIME_APPLICANT["amount"]
    assert body["consent"]["granted"] is True
    assert body["scoredInMs"] is not None


def test_evaluate_thin_file_routing(client):
    response = client.post("/api/applications/evaluate", json=THIN_FILE_APPLICANT)
    assert response.status_code == 200
    body = response.json()

    assert body["eligibility"]["profile"]["segment"] == "thin_file"
    assert body["altData"]["used"] is True
    assert body["personalizedOffer"]["capped"] is True
    assert body["personalizedOffer"]["offeredAmount"] < THIN_FILE_APPLICANT["amount"]
    assert body["creditLine"]["firstLoan"] is True


def test_consent_required(client):
    response = client.post("/api/applications/evaluate", json={**PRIME_APPLICANT, "consentAltData": False})
    assert response.status_code == 400


def test_idempotency_replay(client):
    key = str(uuid.uuid4())
    headers = {"Idempotency-Key": key}
    first = client.post("/api/applications/evaluate", json=PRIME_APPLICANT, headers=headers)
    second = client.post("/api/applications/evaluate", json=PRIME_APPLICANT, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["idempotentReplay"] is True
    assert first.json()["id"] == second.json()["id"]


def test_invalid_pan_rejected(client):
    payload = {**PRIME_APPLICANT, "pan": "INVALID"}
    response = client.post("/api/applications/evaluate", json=payload)
    assert response.status_code == 400


def test_risk_predict_endpoint(client):
    response = client.post("/api/risk/predict", json=PRIME_APPLICANT)
    assert response.status_code == 200
    body = response.json()
    assert "risk" in body
    assert "decision" in body
    assert body["risk"]["defaultProbability"] >= 0


def test_missing_required_fields(client):
    response = client.post(
        "/api/applications/evaluate",
        json={"name": "Aarav Mehta", "pan": "ABCDE1234F", "consentAltData": True},
    )
    assert response.status_code == 400


def test_list_lenders(client):
    response = client.get("/api/lenders")
    assert response.status_code == 200
    lenders = response.json()
    assert len(lenders) >= 4
    assert all("minCreditScore" in lender for lender in lenders)


def test_health_and_prometheus(client):
    health = client.get("/api/health")
    assert health.status_code == 200
    body = health.json()
    assert body["ok"] is True
    assert "postgres" in body
    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert b"credroute_http_requests_total" in metrics.content


def test_loan_history_missing_pan(client):
    response = client.get("/api/borrowers/ZZZZZ9999Z/loan-history")
    assert response.status_code == 404


def test_evaluate_exposes_explanation_and_routing(client):
    created = client.post("/api/applications/evaluate", json=PRIME_APPLICANT)
    assert created.status_code == 200
    application_id = created.json()["id"]

    detail = client.get(f"/api/applications/{application_id}")
    assert detail.status_code == 200
    assert detail.json()["id"] == application_id

    explanation = client.get(f"/api/applications/{application_id}/decision/explanation")
    assert explanation.status_code == 200
    body = explanation.json()
    assert body["applicationId"] == int(application_id)
    assert body["decision"] in ("approve", "review", "reject")
    assert "lenders" in body
    assert body.get("policyVersion")

    routing = client.get(f"/api/applications/{application_id}/routing")
    assert routing.status_code == 200
    assert routing.json()["applicationId"] == int(application_id)
    assert routing.json()["strategy"]


def test_idempotency_conflict_on_payload_mismatch(client):
    key = str(uuid.uuid4())
    headers = {"Idempotency-Key": key}
    first = client.post("/api/applications/evaluate", json=PRIME_APPLICANT, headers=headers)
    assert first.status_code == 200
    conflict = client.post(
        "/api/applications/evaluate",
        json={**PRIME_APPLICANT, "amount": 250000},
        headers=headers,
    )
    assert conflict.status_code == 409
