import mongoose from "mongoose";

const loanOfferSchema = new mongoose.Schema(
  {
    applicationId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "LoanApplication",
      required: true,
      index: true,
    },
    lenderId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "Lender",
      required: true,
      index: true,
    },
    lenderCode: { type: String, required: true },
    lenderName: { type: String, required: true },
    interestRate: { type: Number, required: true },
    processingFee: { type: Number, required: true },
    approvalProbability: { type: Number, required: true },
    maxAmount: { type: Number, required: true },
    rank: { type: Number, required: true },
    score: { type: Number, required: true },
    monthlyPayment: { type: Number, required: true },
  },
  { timestamps: true },
);

export default mongoose.models.LoanOffer ||
  mongoose.model("LoanOffer", loanOfferSchema);