import mongoose from "mongoose";

const userSchema = new mongoose.Schema(
  {
    name: { type: String, required: true, trim: true },
    pan: { type: String, required: true, trim: true, uppercase: true, index: true },
    age: { type: Number, required: true, min: 21, max: 60 },
    monthlyIncome: { type: Number, required: true, min: 0 },
    incomeType: {
      type: String,
      enum: ["salaried", "self_employed", "msme", "gig"],
      required: true,
    },
    cibilScore: { type: Number, min: 300, max: 900, default: null, index: true },
    existingEmis: { type: Number, required: true, min: 0, default: 0 },
    bankStatementAvgBalance: { type: Number, min: 0, default: 0 },
    cityTier: { type: Number, enum: [1, 2, 3], default: 1 },
  },
  { timestamps: true },
);

export default mongoose.models.User || mongoose.model("User", userSchema);
