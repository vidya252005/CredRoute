from locust import HttpUser, between, task
import random
import string


def _pan() -> str:
    letters = "".join(random.choice(string.ascii_uppercase) for _ in range(5))
    digits = "".join(random.choice(string.digits) for _ in range(4))
    return f"{letters}{digits}{random.choice(string.ascii_uppercase)}"


class BorrowerUser(HttpUser):
    wait_time = between(0.05, 0.2)

    @task(5)
    def health(self):
        self.client.get("/api/health")

    @task(3)
    def lenders(self):
        self.client.get("/api/lenders")

    @task(2)
    def metrics(self):
        self.client.get("/api/metrics")

    @task(1)
    def evaluate(self):
        self.client.post(
            "/api/applications/evaluate",
            json={
                "name": "Load Test User",
                "pan": _pan(),
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
            },
        )
