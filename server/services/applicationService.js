import {
  buildEligibilityCacheKey,
  evaluateEligibility,
} from "./eligibilityEngine.js";
import { queryLendersInParallel } from "./lenderSimulator.js";
import { rankOffers } from "./offerRanking.js";
import { calculateRisk } from "./riskModel.js";
import { checkLoanStacking, recordPanApplication } from "./stackingGuard.js";
import { cacheGet, cacheSet } from "../redis.js";
import {
  recordCacheHit,
  recordCacheMiss,
  recordLenderAttempt,
  applicationsTotal,
  offersRankedTotal,
} from "../middleware/metrics.js";
import {
  getIdempotentResponse,
  getLenders,
  saveApplication,
  routeApplication,
} from "../store.js";

export const evaluateApplication = async ({ input, idempotencyKey }) => {
  const previous = await getIdempotentResponse(idempotencyKey);
  if (previous) return { response: previous, idempotentReplay: true };

  const stacking = await checkLoanStacking(input.pan);
  if (!stacking.allowed) {
    throw new Error(
      `Loan stacking detected: PAN ${stacking.pan} has ${stacking.recentCount} applications in 24h (limit ${stacking.limit}).`,
    );
  }

  const cacheKey = buildEligibilityCacheKey(input);
  let eligibility = await cacheGet(cacheKey);
  if (eligibility) {
    recordCacheHit("eligibility");
  } else {
    recordCacheMiss("eligibility");
    eligibility = evaluateEligibility(input);
    await cacheSet(cacheKey, eligibility, 120);
  }

  const risk = await calculateRisk(input);
  const lenders = await getLenders();
  const profile = eligibility.profile;
  const attempts = await queryLendersInParallel(lenders, input, risk, profile);
  attempts.forEach(recordLenderAttempt);

  const availableOffers = eligibility.eligible
    ? rankOffers(
        attempts
          .filter((attempt) => attempt.status === "success")
          .map((attempt) => attempt.offer),
        input,
        profile,
      )
    : [];

  if (availableOffers.length) offersRankedTotal.inc(availableOffers.length);

  const response = await saveApplication({
    input,
    eligibility,
    risk,
    offers: availableOffers,
    lenderAttempts: attempts.map(({ offer, ...attempt }) => attempt),
    idempotencyKey,
  });

  recordPanApplication(input.pan);
  applicationsTotal.labels(response.status).inc();
  return { response, idempotentReplay: false };
};

export const routeToBestLender = async (applicationId) => routeApplication(applicationId);
