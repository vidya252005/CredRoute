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


def test_public_pan_loan_history_removed(client):
    response = client.get("/api/borrowers/ZZZZZ9999Z/loan-history")
    assert response.status_code == 404


def test_admin_loan_history_requires_auth(client):
    response = client.get("/api/admin/borrowers/1/loan-history")
    assert response.status_code in (401, 403)


def test_list_applications_anonymous_is_empty(client):
    client.post("/api/applications/evaluate", json=PRIME_APPLICANT)
    response = client.get("/api/applications")
    assert response.status_code == 200
    assert response.json() == []


def test_evaluate_does_not_persist_plaintext_pan(client, engine):
    response = client.post("/api/applications/evaluate", json=PRIME_APPLICANT)
    assert response.status_code == 200
    assert response.json()["applicant"]["pan"] == "ABCXX1234X"

    from sqlalchemy.orm import sessionmaker

    from app.models.entities import BorrowerCreditLine, BorrowerProfile, ConsentRecord

    db = sessionmaker(bind=engine)()
    try:
        pans = [row.pan for row in db.query(BorrowerProfile).all()]
        hashes = [row.pan_hash for row in db.query(BorrowerProfile).all()]
        consent_pans = [row.pan for row in db.query(ConsentRecord).all()]
        line_pans = [row.pan for row in db.query(BorrowerCreditLine).all()]
        assert "ABCDE1234F" not in pans
        assert "ABCDE1234F" not in consent_pans
        assert "ABCDE1234F" not in line_pans
        assert all(item and len(item) == 64 for item in hashes)
    finally:
        db.close()


def test_validation_rejects_impossible_age(client):
    response = client.post("/api/applications/evaluate", json={**PRIME_APPLICANT, "age": -5})
    assert response.status_code == 400


def test_health_live_and_ready(client):
    live = client.get("/api/health/live")
    ready = client.get("/api/health/ready")
    assert live.status_code == 200
    assert live.json()["ok"] is True
    assert ready.status_code == 200
    assert ready.json()["postgres"] is True


def test_idempotency_in_progress_conflict(client, engine):
    from sqlalchemy.orm import sessionmaker

    from app.models.entities import IdempotencyKey
    from app.services.idempotency import request_hash

    key = "in-progress-key"
    db = sessionmaker(bind=engine)()
    try:
        db.add(
            IdempotencyKey(
                key=key,
                request_hash=request_hash(PRIME_APPLICANT),
                response={},
                status="IN_PROGRESS",
            )
        )
        db.commit()
    finally:
        db.close()

    response = client.post(
        "/api/applications/evaluate",
        json=PRIME_APPLICANT,
        headers={"Idempotency-Key": key},
    )
    assert response.status_code == 409


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


def test_request_id_is_echoed(client):
    response = client.get("/api/health/live", headers={"X-Request-Id": "req-test-123"})
    assert response.status_code == 200
    assert response.headers.get("X-Request-Id") == "req-test-123"


def test_owned_application_is_hidden_from_other_borrower(client):
    owner = client.post(
        "/api/auth/register",
        json={"email": "owner@example.com", "password": "password123"},
    )
    assert owner.status_code == 200
    owner_headers = {"Authorization": f"Bearer {owner.json()['access_token']}"}
    created = client.post("/api/applications/evaluate", json=PRIME_APPLICANT, headers=owner_headers)
    assert created.status_code == 200
    application_id = created.json()["id"]

    other = client.post(
        "/api/auth/register",
        json={"email": "other@example.com", "password": "password123"},
    )
    other_headers = {"Authorization": f"Bearer {other.json()['access_token']}"}
    denied = client.get(f"/api/applications/{application_id}", headers=other_headers)
    assert denied.status_code == 403


def test_concurrent_identical_evaluations_share_one_application(client):
    from concurrent.futures import ThreadPoolExecutor, as_completed

    key = str(uuid.uuid4())

    def once():
        return client.post(
            "/api/applications/evaluate",
            json=PRIME_APPLICANT,
            headers={"Idempotency-Key": key},
        )

    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = [pool.submit(once) for _ in range(6)]
        responses = [future.result() for future in as_completed(futures)]

    successes = [item for item in responses if item.status_code == 200]
    conflicts = [item for item in responses if item.status_code == 409]
    assert successes
    assert all(item.status_code in {200, 409} for item in responses)
    assert len({item.json()["id"] for item in successes}) == 1
    assert conflicts or any(item.json().get("idempotentReplay") for item in successes)
