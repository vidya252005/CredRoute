export const FOIR_CAP = 0.6;

export const estimateEmi = (amount, annualRate, tenureMonths) => {
  const monthlyRate = annualRate / 100 / 12;
  if (!monthlyRate) return amount / tenureMonths;
  return (
    (amount * monthlyRate * (1 + monthlyRate) ** tenureMonths) /
    ((1 + monthlyRate) ** tenureMonths - 1)
  );
};

export const calculateFoir = (input, estimatedRate = 14) => {
  const proposedEmi = estimateEmi(input.amount, estimatedRate, input.tenureMonths);
  const totalEmi = (input.existingEmis || 0) + proposedEmi;
  const foir = totalEmi / Math.max(input.monthlyIncome, 1);
  return {
    foir: Number(foir.toFixed(3)),
    proposedEmi: Math.round(proposedEmi),
    totalEmi: Math.round(totalEmi),
    foirPercent: Number((foir * 100).toFixed(1)),
  };
};

export const classifyProfile = (input) => {
  const hasCibil = input.cibilScore != null && input.cibilScore > 0;

  if (!hasCibil || input.cibilScore < 650) {
    return {
      segment: "thin_file",
      label: "Thin-file",
      detail: hasCibil
        ? `CIBIL ${input.cibilScore} — below prime bureau threshold`
        : "No CIBIL score — new-to-credit applicant",
    };
  }

  if (input.cibilScore >= 750 && input.incomeType === "salaried") {
    return {
      segment: "prime",
      label: "Prime",
      detail: `CIBIL ${input.cibilScore} salaried applicant`,
    };
  }

  return {
    segment: "near_prime",
    label: "Near-prime",
    detail: `CIBIL ${input.cibilScore} ${input.incomeType.replace("_", " ")} applicant`,
  };
};

export const lenderFitScore = (lender, input, profile) => {
  if (lender.servesThinFile && profile.segment === "thin_file") return 1;
  if (lender.servesPrime && profile.segment === "prime") return 1;
  if (lender.servesNearPrime && profile.segment === "near_prime") return 0.95;
  if (lender.servesThinFile && profile.segment === "near_prime") return 0.55;
  if (lender.servesNearPrime && profile.segment === "thin_file") return 0.35;
  if (lender.servesPrime && profile.segment === "near_prime") return 0.7;
  return 0.2;
};

export const normalizePan = (pan) => String(pan || "").trim().toUpperCase();

export const isValidPan = (pan) => /^[A-Z]{5}[0-9]{4}[A-Z]$/.test(normalizePan(pan));
