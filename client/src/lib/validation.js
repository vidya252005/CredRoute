const PAN_PATTERN = /^[A-Z]{5}[0-9]{4}[A-Z]$/;
const VALID_INCOME_TYPES = ["salaried", "self_employed", "msme", "gig"];
const VALID_TENURES = [6, 9, 12, 18, 24, 36];

export const validateForm = (form) => {
  const errors = {};
  const pan = String(form.pan || "").trim().toUpperCase();

  if (!String(form.name || "").trim()) {
    errors.name = "Enter the applicant's full name.";
  }

  if (!PAN_PATTERN.test(pan)) {
    errors.pan = "PAN must match the format ABCDE1234F.";
  }

  if (!Number.isInteger(Number(form.age)) || Number(form.age) < 21 || Number(form.age) > 60) {
    errors.age = "Age must be between 21 and 60.";
  }

  if (!VALID_INCOME_TYPES.includes(form.incomeType)) {
    errors.incomeType = "Choose a valid income type.";
  }

  if (!Number.isFinite(Number(form.monthlyIncome)) || Number(form.monthlyIncome) < 15000) {
    errors.monthlyIncome = "Monthly income must be at least ₹15,000.";
  }

  if (form.cibilScore !== "" && form.cibilScore != null) {
    const cibil = Number(form.cibilScore);
    if (!Number.isInteger(cibil) || cibil < 300 || cibil > 900) {
      errors.cibilScore = "CIBIL must be between 300 and 900, or left blank.";
    }
  }

  if (!Number.isFinite(Number(form.existingEmis)) || Number(form.existingEmis) < 0) {
    errors.existingEmis = "Existing EMIs cannot be negative.";
  }

  if (
    !Number.isFinite(Number(form.bankStatementAvgBalance)) ||
    Number(form.bankStatementAvgBalance) < 0
  ) {
    errors.bankStatementAvgBalance = "Average bank balance cannot be negative.";
  }

  if (![1, 2, 3].includes(Number(form.cityTier))) {
    errors.cityTier = "Select a city tier.";
  }

  if (!Number.isFinite(Number(form.amount)) || Number(form.amount) < 10000) {
    errors.amount = "Loan amount must be at least ₹10,000.";
  }

  if (!VALID_TENURES.includes(Number(form.tenureMonths))) {
    errors.tenureMonths = "Choose a supported tenure.";
  }

  if (!form.consentAltData) {
    errors.consentAltData = "Consent is required to score this application.";
  }

  return errors;
};

export const buildPayload = (form) => ({
  ...form,
  pan: String(form.pan || "").trim().toUpperCase(),
  cityTier: Number(form.cityTier),
  tenureMonths: Number(form.tenureMonths),
  cibilScore: form.cibilScore === "" || form.cibilScore == null ? null : Number(form.cibilScore),
  financialNotes: form.financialNotes || "",
  consentAltData: Boolean(form.consentAltData),
});
