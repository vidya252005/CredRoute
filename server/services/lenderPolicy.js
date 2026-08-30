export const resolveCibil = (input) => {
  const score = input.cibilScore ?? input.creditScore;
  if (score === "" || score == null) return null;
  const parsed = Number(score);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
};

export const normalizeLenderPolicy = (lender) => ({
  minIncome: lender.minIncome ?? lender.min_income,
  minCreditScore: lender.minCreditScore ?? lender.min_credit_score,
  maxAmount: lender.maxAmount ?? lender.max_amount,
  maxFoir: lender.maxFoir ?? lender.max_foir ?? 0.6,
  baseInterestRate: lender.baseInterestRate ?? lender.base_interest_rate ?? 14,
  incomeTypes: lender.incomeTypes ?? lender.income_types,
  cityTiers: lender.cityTiers ?? lender.city_tiers,
  servesPrime: lender.servesPrime ?? lender.serves_prime ?? false,
  servesNearPrime: lender.servesNearPrime ?? lender.serves_near_prime ?? false,
  servesThinFile: lender.servesThinFile ?? lender.serves_thin_file ?? false,
});

export const checkHardPolicyGates = (policy, input, lenderName) => {
  const missing = [];
  if (policy.minIncome == null) missing.push("minIncome");
  if (policy.maxAmount == null) missing.push("maxAmount");
  if (policy.minCreditScore == null) missing.push("minCreditScore");

  if (missing.length) {
    return {
      eligible: false,
      reason: `${lenderName} policy incomplete (${missing.join(", ")})`,
    };
  }

  if (input.amount > policy.maxAmount) {
    return {
      eligible: false,
      reason: `Requested amount exceeds ${lenderName} max ticket size (₹${policy.maxAmount.toLocaleString("en-IN")})`,
    };
  }

  if (input.monthlyIncome < policy.minIncome) {
    return {
      eligible: false,
      reason: `Monthly income below ${lenderName} minimum (₹${policy.minIncome.toLocaleString("en-IN")})`,
    };
  }

  const cibil = resolveCibil(input);
  if (cibil != null && policy.minCreditScore > 0 && cibil < policy.minCreditScore) {
    return {
      eligible: false,
      reason: `CIBIL ${cibil} below ${lenderName} threshold (${policy.minCreditScore})`,
    };
  }

  return null;
};
