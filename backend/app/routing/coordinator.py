"""Concurrent lender querying with timeouts, retries, and a concurrency cap."""

from __future__ import annotations

import time

from app.core.config import settings
from app.domain.context import DecisionContext
from app.domain.enums import LenderAttemptStatus
from app.domain.lender import LenderEligibilityRequest, LenderRecord, OfferRequest
from app.domain.results import LenderDecisionExplanation, LenderEvaluation
from app.resilience.bulkhead import lender_semaphore
from app.resilience.circuit_breaker import CircuitBreaker, get_circuit_state
from app.resilience.retry import RetryPolicy
from app.resilience.timeout import with_timeout
from app.routing.factory import LenderAdapterFactory


class LenderQueryCoordinator:
    def __init__(
        self,
        factory: LenderAdapterFactory | None = None,
        retry_policy: RetryPolicy | None = None,
        max_concurrency: int | None = None,
    ):
        self.factory = factory or LenderAdapterFactory()
        self.retry_policy = retry_policy or RetryPolicy(
            max_attempts=settings.lender_max_retries,
            base_delay_ms=settings.lender_retry_base_delay_ms,
            max_delay_ms=settings.lender_retry_max_delay_ms,
        )
        self.max_concurrency = max_concurrency

    async def query_all(
        self,
        lenders: list[LenderRecord],
        context: DecisionContext,
        risk: dict,
        profile: dict,
    ) -> list[LenderEvaluation]:
        import asyncio

        semaphore = lender_semaphore(self.max_concurrency)
        input_data = context.to_input_data()

        async def run(lender: LenderRecord) -> LenderEvaluation:
            async with semaphore:
                return await self.query_one(lender, context, input_data, risk, profile)

        return list(await asyncio.gather(*[run(lender) for lender in lenders]))

    async def query_one(
        self,
        lender: LenderRecord,
        context: DecisionContext,
        input_data: dict,
        risk: dict,
        profile: dict,
    ) -> LenderEvaluation:
        adapter = self.factory.get(lender.code)
        breaker = CircuitBreaker(lender.code)
        started = time.time()
        if not breaker.allow_request():
            return LenderEvaluation(
                lender_code=lender.code,
                status=LenderAttemptStatus.CIRCUIT_OPEN,
                latency_ms=int((time.time() - started) * 1000),
                message="circuit breaker open",
                circuit=get_circuit_state(lender.code).__dict__,
                explanation=LenderDecisionExplanation(
                    lender_code=lender.code,
                    eligible=False,
                    rejection_reasons=["circuit breaker open"],
                    status=LenderAttemptStatus.CIRCUIT_OPEN.value,
                ),
            )

        last_error: BaseException | None = None
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            try:
                eligibility = await with_timeout(
                    adapter.check_eligibility(
                        LenderEligibilityRequest(lender=lender, input_data=input_data, profile=profile)
                    ),
                    settings.lender_timeout_ms,
                )
                latency_ms = int((time.time() - started) * 1000)
                if not eligibility.eligible:
                    breaker.record_success()
                    reason = eligibility.reason or "Lender policy not satisfied"
                    return LenderEvaluation(
                        lender_code=lender.code,
                        status=LenderAttemptStatus.INELIGIBLE,
                        latency_ms=latency_ms,
                        message=reason,
                        explanation=LenderDecisionExplanation(
                            lender_code=lender.code,
                            eligible=False,
                            rejection_reasons=eligibility.rejection_reasons or [reason],
                            profile_fit=eligibility.fit,
                            latency_ms=latency_ms,
                            status=LenderAttemptStatus.INELIGIBLE.value,
                        ),
                    )
                offer = await adapter.get_offer(
                    OfferRequest(
                        lender=lender,
                        input_data=input_data,
                        risk=risk,
                        profile=profile,
                        fit=eligibility.fit,
                    )
                )
                offer.latency_ms = latency_ms
                breaker.record_success()
                return LenderEvaluation(
                    lender_code=lender.code,
                    status=LenderAttemptStatus.SUCCESS,
                    latency_ms=latency_ms,
                    offer=offer,
                    explanation=LenderDecisionExplanation(
                        lender_code=lender.code,
                        eligible=True,
                        profile_fit=offer.profile_fit,
                        risk_contribution=float(risk.get("defaultProbability") or 0),
                        latency_ms=latency_ms,
                        status=LenderAttemptStatus.SUCCESS.value,
                    ),
                )
            except Exception as error:  # noqa: BLE001
                last_error = error
                if attempt < self.retry_policy.max_attempts and self.retry_policy.is_retryable(error):
                    await self.retry_policy.sleep(attempt)

        breaker.record_failure()
        message = str(last_error or "lender unavailable")
        status = (
            LenderAttemptStatus.FAILED_TIMEOUT
            if isinstance(last_error, TimeoutError) or "timeout" in message.lower()
            else LenderAttemptStatus.FAILED_PROVIDER
            if last_error
            else LenderAttemptStatus.FAILED
        )
        # Keep the persisted attempt status as "failed" so existing metrics stay compatible.
        return LenderEvaluation(
            lender_code=lender.code,
            status=LenderAttemptStatus.FAILED,
            latency_ms=int((time.time() - started) * 1000),
            message=message,
            circuit=get_circuit_state(lender.code).__dict__,
            explanation=LenderDecisionExplanation(
                lender_code=lender.code,
                eligible=False,
                rejection_reasons=[message],
                latency_ms=int((time.time() - started) * 1000),
                status=status.value,
            ),
        )
