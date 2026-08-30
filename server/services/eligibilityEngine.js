import { calculateFoir, classifyProfile, FOIR_CAP } from "./indiaProfile.js";

export { calculateRisk } from "./riskModel.js";

export const evaluateEligibility = (input) => {
  const profile = classifyProfile(input);
  const foirDetails = calculateFoir(input);
  const alternateDataOk =
    (input.bankStatementAvgBalance || 0) >= input.monthlyIncome * 0.8 ||
    input.incomeType === "salaried";

  const checks = [
    {
      label: "Age",
      passed: input.age >= 21 && input.age <= 60,
      detail: `${input.age} years; supported range is 21–60`,
    },
    {
      label: "Monthly income",
      passed: input.monthlyIncome >= 15000,
      detail: `₹${input.monthlyIncome.toLocaleString("en-IN")}; minimum is ₹15,000`,
    },
    {
      label: "FOIR",
      passed: foirDetails.foir <= FOIR_CAP,
      detail: `${foirDetails.foirPercent}% (existing EMIs ₹${input.existingEmis.toLocaleString("en-IN")} + proposed ₹${foirDetails.proposedEmi.toLocaleString("en-IN")}); cap is ${FOIR_CAP * 100}%`,
    },
    {
      label: "Profile segment",
      passed: true,
      detail: `${profile.label} — ${profile.detail}`,
    },
    {
      label: "Alternate data",
      passed: profile.segment !== "thin_file" || alternateDataOk,
      detail:
        profile.segment !== "thin_file"
          ? "Not required for bureau-backed profile"
          : `Avg bank balance ₹${(input.bankStatementAvgBalance || 0).toLocaleString("en-IN")}`,
    },
    {
      label: "Requested amount",
      passed: input.amount <= input.monthlyIncome * 24,
      detail: `₹${input.amount.toLocaleString("en-IN")}; capped at 24× monthly income`,
    },
  ];

  const failed = checks.find((check) => !check.passed);
  return {
    eligible: !failed,
    checks,
    reason: failed ? `${failed.label}: ${failed.detail}` : null,
    profile,
    foir: foirDetails,
  };
};

export const buildEligibilityCacheKey = (input) =>
  `eligibility:${input.pan}:${input.amount}:${input.tenureMonths}:${input.monthlyIncome}:${input.cibilScore ?? "na"}`;
