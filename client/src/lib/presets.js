export const presets = {
  prime: {
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
    financialNotes: "Stable salaried income with consistent savings.",
    consentAltData: true,
  },
  thinFile: {
    name: "Priya Sharma",
    pan: "FGHIJ5678K",
    age: 26,
    monthlyIncome: 28000,
    incomeType: "gig",
    cibilScore: "",
    existingEmis: 4000,
    bankStatementAvgBalance: 32000,
    cityTier: 2,
    amount: 80000,
    tenureMonths: 12,
    financialNotes: "Gig worker with inconsistent income from delivery platforms.",
    consentAltData: true,
  },
  nearPrime: {
    name: "Rahul Desai",
    pan: "KLMNO9012P",
    age: 34,
    monthlyIncome: 52000,
    incomeType: "self_employed",
    cibilScore: 710,
    existingEmis: 9000,
    bankStatementAvgBalance: 48000,
    cityTier: 1,
    amount: 150000,
    tenureMonths: 18,
    consentAltData: true,
  },
};

export const initialForm = presets.prime;

export const numericFields = [
  "age",
  "monthlyIncome",
  "cibilScore",
  "existingEmis",
  "bankStatementAvgBalance",
  "cityTier",
  "amount",
  "tenureMonths",
];

export const incomeTypeLabels = {
  salaried: "Salaried",
  self_employed: "Self-employed",
  msme: "MSME",
  gig: "Gig worker",
};

export const segmentLabels = {
  prime: "Prime",
  near_prime: "Near-prime",
  thin_file: "Thin-file",
};

export const categoryLabels = {
  bank: "Scheduled bank",
  nbfc: "NBFC",
  fintech: "Fintech",
  co_lending: "Co-lending",
};
