import mongoose from "mongoose";

const idempotencyKeySchema = new mongoose.Schema(
  {
    key: { type: String, required: true, unique: true, index: true },
    response: { type: mongoose.Schema.Types.Mixed, required: true },
  },
  { timestamps: true },
);

export default mongoose.models.IdempotencyKey ||
  mongoose.model("IdempotencyKey", idempotencyKeySchema);