import asyncio
import time
from abc import ABC, abstractmethod

from app.core.config import settings
from app.services.circuit_breaker import get_circuit_state, is_circuit_open, record_failure, record_success
from app.services.lender_policy import check_hard_policy_gates, normalize_lender_policy, resolve_cibil
from app.services.profile import calculate_foir, lender_fit_score


class LenderProvider(ABC):
    code: str

    @abstractmethod
    async def check_eligibility(self, lender: dict, input_data: dict, profile: dict) -> dict:
        raise NotImplementedError

    async def fetch_offer(self, lender: dict, input_data: dict, risk: dict, profile: dict, fit: float) -> dict:
        policy = normalize_lender_policy(lender)
        cibil = resolve_cibil(input_data)
        if cibil is None:
            cibil = 0 if profile.get("segment") == "thin_file" else 650
        score_lift = max(0, (cibil - max(policy["min_credit_score"] or 600, 600)) / 1000)
        alternate_boost = (
            0.08
            if profile["segment"] == "thin_file"
            and input_data.get("bank_statement_avg_balance", 0) >= input_data["monthly_income"] * 0.8
            else 0
        )
        approval_probability = round(
            min(
                0.98,
                max(
                    0.35,
                    lender.get("success_rate", lender.get("successRate", 0.8)) * fit
                    + score_lift
                    + alternate_boost
                    - risk["defaultProbability"] * 0.2,
                ),
            ),
            3,
        )
        return {
            "lenderId": lender["id"],
            "lenderCode": lender["code"],
            "lenderName": lender["name"],
            "interestRate": round(
                max(10.5, policy["base_interest_rate"] + risk["defaultProbability"] * 2),
                2,
            ),
            "processingFee": lender.get("processing_fee", lender.get("processingFee", 0)),
            "approvalProbability": approval_probability,
            "maxAmount": policy["max_amount"],
            "successRate": lender.get("success_rate", lender.get("successRate", 0.8)),
            "journeyScore": lender.get("journey_score", lender.get("journeyScore", 0.8)),
            "profileFit": round(fit, 3),
        }


class MockLenderProvider(LenderProvider):
    def __init__(self, code: str):
        self.code = code

    async def check_eligibility(self, lender: dict, input_data: dict, profile: dict) -> dict:
        await asyncio.sleep(min(lender.get("simulated_latency_ms", lender.get("simulatedLatencyMs", 120)), 220) / 1000)
        policy = normalize_lender_policy(lender)

        if lender["code"] == "RURAL-COLENDING-MOCK" and input_data["amount"] > 350000:
            raise TimeoutError("simulated lender timeout")

        policy_failure = check_hard_policy_gates(policy, input_data, lender["name"])
        if policy_failure:
            return policy_failure

        income_types = policy["income_types"] or []
        if income_types and input_data["income_type"] not in income_types:
            return {
                "eligible": False,
                "reason": f"{lender['name']} does not serve {input_data['income_type']} profiles",
            }

        city_tiers = policy["city_tiers"] or []
        if city_tiers and input_data["city_tier"] not in city_tiers:
            return {
                "eligible": False,
                "reason": f"{lender['name']} does not serve tier-{input_data['city_tier']} cities",
            }

        fit = lender_fit_score({**lender, **policy}, profile)
        if fit < 0.4:
            return {"eligible": False, "reason": f"{lender['name']} is not a fit for {profile['label']} applicants"}

        if profile["segment"] == "thin_file" and policy["serves_thin_file"]:
            if input_data.get("bank_statement_avg_balance", 0) < input_data["monthly_income"] * 0.8:
                return {"eligible": False, "reason": "Insufficient alternate bank-statement data for thin-file routing"}

        foir = calculate_foir(input_data, policy["base_interest_rate"])
        if foir["foir"] > policy["max_foir"]:
            return {"eligible": False, "reason": f"FOIR {foir['foirPercent']}% exceeds {lender['name']} cap"}

        return {"eligible": True, "fit": fit}


async def query_lender(provider: MockLenderProvider, lender: dict, input_data: dict, risk: dict, profile: dict) -> dict:
    started = time.time()
    if is_circuit_open(lender["code"]):
        raise RuntimeError("circuit breaker open")

    last_error = None
    for attempt in range(1, settings.lender_max_retries + 1):
        try:
            result = await asyncio.wait_for(
                provider.check_eligibility(lender, input_data, profile),
                timeout=settings.lender_timeout_ms / 1000,
            )
            latency_ms = int((time.time() - started) * 1000)
            if not result["eligible"]:
                record_success(lender["code"])
                return {
                    "status": "ineligible",
                    "lenderCode": lender["code"],
                    "latencyMs": latency_ms,
                    "message": result["reason"],
                }
            offer = await provider.fetch_offer(lender, input_data, risk, profile, result["fit"])
            offer["latencyMs"] = latency_ms
            record_success(lender["code"])
            return {"status": "success", "lenderCode": lender["code"], "latencyMs": latency_ms, "offer": offer}
        except Exception as error:  # noqa: BLE001
            last_error = error
            if attempt < settings.lender_max_retries:
                await asyncio.sleep(0.04 * attempt)
    record_failure(lender["code"])
    raise last_error or RuntimeError("lender unavailable")


async def query_lenders_in_parallel(lenders: list[dict], input_data: dict, risk: dict, profile: dict) -> list[dict]:
    async def run(lender: dict) -> dict:
        provider = MockLenderProvider(lender["code"])
        started = time.time()
        try:
            return await query_lender(provider, lender, input_data, risk, profile)
        except Exception as error:  # noqa: BLE001
            return {
                "status": "failed",
                "lenderCode": lender["code"],
                "latencyMs": int((time.time() - started) * 1000),
                "message": str(error),
                "circuit": get_circuit_state(lender["code"]).__dict__,
            }

    return await asyncio.gather(*[run(lender) for lender in lenders])
