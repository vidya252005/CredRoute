import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { classifyProfile } from "../services/indiaProfile.js";
import { lenderSeedData } from "../../data/lenders.js";
import { queryLendersInParallel } from "../services/lenderSimulator.js";
import { checkHardPolicyGates, normalizeLenderPolicy } from "../services/lenderPolicy.js";

const borderlineInput = {
  name: "Borderline Applicant",
  pan: "ABCDE1234F",
  age: 29,
  monthlyIncome: 22000,
  incomeType: "salaried",
  cibilScore: 615,
  existingEmis: 0,
  bankStatementAvgBalance: 20000,
  cityTier: 1,
  amount: 300000,
  tenureMonths: 24,
};

describe("lender policy gates", () => {
  it("rejects when required thresholds are missing", () => {
    const result = checkHardPolicyGates(normalizeLenderPolicy({ name: "BrokenMock" }), borderlineInput, "BrokenMock");
    assert.equal(result?.eligible, false);
    assert.match(result?.reason || "", /policy incomplete/i);
  });

  it("rejects AxisBankMock for low income and low CIBIL", () => {
    const axis = lenderSeedData.find((lender) => lender.code === "AXISBANK-MOCK");
    const result = checkHardPolicyGates(normalizeLenderPolicy(axis), borderlineInput, axis.name);
    assert.equal(result?.eligible, false);
    assert.match(result?.reason || "", /income below/i);
  });

  it("only LenderCMock approves the borderline profile", async () => {
    const profile = classifyProfile(borderlineInput);
    const risk = { defaultProbability: 0.2 };
    const lenders = lenderSeedData.map((lender) => ({ ...lender, id: lender.code, active: true }));
    const attempts = await queryLendersInParallel(lenders, borderlineInput, risk, profile);

    const approved = attempts.filter((attempt) => attempt.status === "success").map((attempt) => attempt.lenderCode);
    const rejected = attempts.filter((attempt) => attempt.status === "ineligible");

    assert.deepEqual(approved, ["LENDER-C-MOCK"]);
    assert.equal(rejected.length, 4);
    assert.ok(rejected.some((attempt) => attempt.lenderCode === "AXISBANK-MOCK"));
    assert.ok(rejected.some((attempt) => attempt.lenderCode === "IDFC-MOCK"));
    assert.ok(rejected.some((attempt) => attempt.lenderCode === "LENDER-B-MOCK"));
    assert.ok(rejected.some((attempt) => attempt.lenderCode === "RURAL-COLENDING-MOCK"));
  });
});
