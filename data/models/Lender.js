import mongoose from "mongoose";

const lenderSchema = new mongoose.Schema(
  {
    code: { type: String, required: true, unique: true, index: true },
    name: { type: String, required: true },
    category: {
      type: String,
      enum: ["bank", "nbfc", "fintech", "co_lending"],
      required: true,
    },
    description: { type: String, default: "" },
    minIncome: { type: Number, required: true },
    minCreditScore: { type: Number, required: true, index: true },
    maxAmount: { type: Number, required: true },
    maxFoir: { type: Number, required: true, min: 0, max: 1 },
    baseInterestRate: { type: Number, required: true },
    processingFee: { type: Number, required: true },
    successRate: { type: Number, required: true, min: 0, max: 1 },
    journeyScore: { type: Number, required: true, min: 0, max: 1 },
    servesPrime: { type: Boolean, default: false },
    servesNearPrime: { type: Boolean, default: false },
    servesThinFile: { type: Boolean, default: false },
    incomeTypes: [{ type: String }],
    cityTiers: [{ type: Number }],
    active: { type: Boolean, default: true, index: true },
    simulatedLatencyMs: { type: Number, default: 120 },
  },
  { timestamps: true },
);

export default mongoose.models.Lender || mongoose.model("Lender", lenderSchema);
