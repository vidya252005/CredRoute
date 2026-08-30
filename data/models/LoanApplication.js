import mongoose from "mongoose";

const loanApplicationSchema = new mongoose.Schema(
  {
    userId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "User",
      required: true,
      index: true,
    },
    amount: { type: Number, required: true },
    tenureMonths: { type: Number, required: true },
    status: {
      type: String,
      enum: ["processing", "offers_ready", "ineligible", "routed"],
      default: "processing",
      index: true,
    },
    eligibility: {
      eligible: { type: Boolean, required: true },
      checks: [{ label: String, passed: Boolean, detail: String }],
      reason: String,
      profile: {
        segment: String,
        label: String,
        detail: String,
      },
      foir: {
        foir: Number,
        proposedEmi: Number,
        totalEmi: Number,
        foirPercent: Number,
      },
    },
    risk: {
      defaultProbability: Number,
      fraudProbability: Number,
      confidence: Number,
    },
    recommendedOfferId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "LoanOffer",
      default: null,
    },
    routedLenderCode: { type: String, default: null },
    lenderAttempts: [
      {
        lenderCode: String,
        status: String,
        latencyMs: Number,
        message: String,
      },
    ],
  },
  { timestamps: true },
);

loanApplicationSchema.index({ userId: 1, createdAt: -1 });

export default mongoose.models.LoanApplication ||
  mongoose.model("LoanApplication", loanApplicationSchema);