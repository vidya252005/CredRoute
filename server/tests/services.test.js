import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { evaluateEligibility } from "../services/eligibilityEngine.js";
import { rankOffers } from "../services/offerRanking.js";
import { calculateRisk, initializeRiskModel } from "../services/riskModel.js";
import {
  calculateFoir,
  classifyProfile,
  isValidPan,
  lenderFitScore,
} from "../services/indiaProfile.js";
import {
  getCircuitState,
  isCircuitOpen,
  recordFailure,
  recordSuccess,
} from "../services/circuitBreaker.js";
import { checkLoanStacking, recordPanApplication } from "../services/stackingGuard.js";

const primeInput = {
  name: "Aarav Mehta",
  pan: "ABCDE1234F",
  age: 29,
  monthlyIncome: 85000,
  incomeType: "salaried",
  cibilScore: 780,
  existingEmis: 12000,
  bankStatementAvgBalance: 90000,
  cityTier: 1,
  amount: 300000,
  tenureMonths: 24,
};

const thinFileInput = {
  name: "Priya Sharma",
  pan: "FGHIJ5678K",
  age: 26,
  monthlyIncome: 28000,
  incomeType: "gig",
  cibilScore: null,
  existingEmis: 4000,
  bankStatementAvgBalance: 32000,
  cityTier: 2,
  amount: 80000,
  tenureMonths: 12,
};

describe("india profile", () => {
  it("validates PAN format", () => {
    assert.equal(isValidPan("ABCDE1234F"), true);
    assert.equal(isValidPan("INVALID"), false);
  });

  it("classifies prime and thin-file segments", () => {
    assert.equal(classifyProfile(primeInput).segment, "prime");
    assert.equal(classifyProfile(thinFileInput).segment, "thin_file");
  });

  it("calculates FOIR with proposed EMI", () => {
    const foir = calculateFoir(primeInput);
    assert.ok(foir.foir > 0);
    assert.ok(foir.proposedEmi > 0);
  });
});

describe("eligibility engine", () => {
  it("passes a prime salaried applicant", () => {
    const result = evaluateEligibility(primeInput);
    assert.equal(result.eligible, true);
    assert.equal(result.profile.segment, "prime");
  });

  it("rejects when FOIR exceeds cap", () => {
    const result = evaluateEligibility({
      ...primeInput,
      existingEmis: 45000,
      amount: 500000,
    });
    assert.equal(result.eligible, false);
    assert.match(result.reason || "", /FOIR/);
  });
});

describe("risk model", () => {
  it("returns bounded probabilities", async () => {
    await initializeRiskModel();
    const risk = await calculateRisk(primeInput);
    assert.ok(risk.defaultProbability >= 0 && risk.defaultProbability <= 1);
    assert.ok(risk.confidence > 0);
  });
});

describe("offer ranking", () => {
  it("ranks higher-fit offers first for thin-file profiles", () => {
    const profile = classifyProfile(thinFileInput);
    const ranked = rankOffers(
      [
        {
          lenderCode: "FLEXI-LOANS-MOCK",
          lenderName: "FlexiLoansMock",
          interestRate: 16.5,
          approvalProbability: 0.84,
          maxAmount: 500000,
          successRate: 0.84,
          journeyScore: 0.9,
          processingFee: 499,
          profileFit: 1,
        },
        {
          lenderCode: "HDFC-BANK-MOCK",
          lenderName: "HDFCBankMock",
          interestRate: 11.9,
          approvalProbability: 0.5,
          maxAmount: 2000000,
          successRate: 0.94,
          journeyScore: 0.92,
          processingFee: 1499,
          profileFit: 0.2,
        },
      ],
      thinFileInput,
      profile,
    );

    assert.equal(ranked[0].lenderCode, "FLEXI-LOANS-MOCK");
  });
});

describe("stacking guard", () => {
  it("blocks repeated PAN applications when enabled", async () => {
    const previousEnabled = process.env.STACKING_ENABLED;
    const previousLimit = process.env.STACKING_LIMIT;
    process.env.STACKING_ENABLED = "true";
    process.env.STACKING_LIMIT = "3";
    recordPanApplication("LMNOP9012Q");
    recordPanApplication("LMNOP9012Q");
    recordPanApplication("LMNOP9012Q");
    const result = await checkLoanStacking("LMNOP9012Q");
    process.env.STACKING_ENABLED = previousEnabled;
    process.env.STACKING_LIMIT = previousLimit;
    assert.equal(result.allowed, false);
  });
});

describe("circuit breaker", () => {
  it("opens after repeated failures and closes after success", () => {
    recordFailure("TEST-LENDER");
    recordFailure("TEST-LENDER");
    recordFailure("TEST-LENDER");
    assert.equal(isCircuitOpen("TEST-LENDER"), true);
    recordSuccess("TEST-LENDER");
    assert.equal(getCircuitState("TEST-LENDER").state, "closed");
  });
});

describe("lender fit", () => {
  it("prefers thin-file lenders for no-CIBIL applicants", () => {
    const profile = classifyProfile(thinFileInput);
    const fit = lenderFitScore(
      { servesThinFile: true, servesNearPrime: true, servesPrime: false },
      thinFileInput,
      profile,
    );
    assert.equal(fit, 1);
  });
});
