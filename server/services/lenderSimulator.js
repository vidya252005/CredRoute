import { lenderMaxRetries, lenderTimeoutMs } from "../config.js";
import {
  calculateFoir,
  lenderFitScore,
} from "./indiaProfile.js";
import {
  checkHardPolicyGates,
  normalizeLenderPolicy,
  resolveCibil,
} from "./lenderPolicy.js";
import {
  getCircuitState,
  isCircuitOpen,
  recordFailure,
  recordSuccess,
} from "./circuitBreaker.js";

const wait = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));

const withTimeout = (promise, timeoutMs) =>
  Promise.race([
    promise,
    new Promise((_, reject) =>
      setTimeout(() => reject(new Error("simulated lender timeout")), timeoutMs),
    ),
  ]);

const hasAlternateData = (input) =>
  (input.bankStatementAvgBalance || 0) >= input.monthlyIncome * 0.8;

const simulateLenderBehavior = async (lender, input, profile) => {
  const latency = Math.min(lender.simulatedLatencyMs || 120, 220);
  await wait(latency);
  const policy = normalizeLenderPolicy(lender);

  if (lender.code === "RURAL-COLENDING-MOCK" && input.amount > 350000) {
    throw new Error("simulated lender timeout");
  }

  const policyFailure = checkHardPolicyGates(policy, input, lender.name);
  if (policyFailure) return policyFailure;

  if (policy.incomeTypes?.length && !policy.incomeTypes.includes(input.incomeType)) {
    return { eligible: false, reason: `${lender.name} does not serve ${input.incomeType} profiles` };
  }

  if (policy.cityTiers?.length && !policy.cityTiers.includes(input.cityTier)) {
    return { eligible: false, reason: `${lender.name} does not serve tier-${input.cityTier} cities` };
  }

  const fit = lenderFitScore({ ...lender, ...policy }, input, profile);
  if (fit < 0.4) {
    return {
      eligible: false,
      reason: `${lender.name} is not a fit for ${profile.label} applicants`,
    };
  }

  if (profile.segment === "thin_file" && policy.servesThinFile && !hasAlternateData(input)) {
    return {
      eligible: false,
      reason: "Insufficient alternate bank-statement data for thin-file routing",
    };
  }

  const foir = calculateFoir(input, policy.baseInterestRate);
  if (foir.foir > policy.maxFoir) {
    return {
      eligible: false,
      reason: `FOIR ${foir.foirPercent}% exceeds ${lender.name} cap`,
    };
  }

  return { eligible: true, fit };
};

const buildOffer = (lender, input, risk, profile, fit, started) => {
  const policy = normalizeLenderPolicy(lender);
  const cibil = resolveCibil(input) ?? 650;
  const scoreLift = Math.max(0, (cibil - Math.max(policy.minCreditScore ?? 600, 600)) / 1000);
  const alternateBoost =
    profile.segment === "thin_file" && hasAlternateData(input) ? 0.08 : 0;
  const approvalProbability = Number(
    Math.min(
      0.98,
      Math.max(
        0.35,
        lender.successRate * fit + scoreLift + alternateBoost - risk.defaultProbability * 0.2,
      ),
    ).toFixed(3),
  );

  return {
    lenderId: lender._id || lender.id,
    lenderCode: lender.code,
    lenderName: lender.name,
    lenderCategory: lender.category,
    interestRate: Number(
      Math.max(10.5, lender.baseInterestRate + risk.defaultProbability * 2).toFixed(2),
    ),
    processingFee: lender.processingFee,
    approvalProbability,
    maxAmount: policy.maxAmount ?? lender.maxAmount,
    successRate: lender.successRate,
    journeyScore: lender.journeyScore,
    profileFit: Number(fit.toFixed(3)),
    latencyMs: Date.now() - started,
  };
};

export const queryLender = async (lender, input, risk, profile) => {
  const started = Date.now();

  if (isCircuitOpen(lender.code)) {
    throw new Error("circuit breaker open");
  }

  let lastError = null;

  for (let attempt = 1; attempt <= lenderMaxRetries; attempt += 1) {
    try {
      const result = await withTimeout(
        simulateLenderBehavior(lender, input, profile),
        lenderTimeoutMs,
      );

      if (!result.eligible) {
        recordSuccess(lender.code);
        return {
          status: "ineligible",
          lenderCode: lender.code,
          reason: result.reason,
          latencyMs: Date.now() - started,
        };
      }

      const offer = buildOffer(lender, input, risk, profile, result.fit, started);
      recordSuccess(lender.code);
      return { status: "success", ...offer };
    } catch (error) {
      lastError = error;
      if (attempt < lenderMaxRetries) await wait(40 * attempt);
    }
  }

  recordFailure(lender.code);
  throw lastError instanceof Error ? lastError : new Error("lender unavailable");
};

export const queryLendersInParallel = async (lenders, input, risk, profile) =>
  Promise.all(
    lenders.map(async (lender) => {
      const started = Date.now();
      try {
        const offer = await queryLender(lender, input, risk, profile);
        if (offer.status === "ineligible") {
          return {
            status: "ineligible",
            lenderCode: lender.code,
            latencyMs: offer.latencyMs || Date.now() - started,
            message: offer.reason,
          };
        }
        return {
          status: "success",
          lenderCode: lender.code,
          latencyMs: offer.latencyMs || Date.now() - started,
          offer,
        };
      } catch (error) {
        return {
          status: "failed",
          lenderCode: lender.code,
          latencyMs: Date.now() - started,
          message: error instanceof Error ? error.message : "lender unavailable",
          circuit: getCircuitState(lender.code),
        };
      }
    }),
  );
