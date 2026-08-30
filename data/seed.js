import "dotenv/config";
import mongoose from "mongoose";
import { Lender } from "./models/index.js";
import { syncLenders } from "./lenders.js";

const run = async () => {
  if (!process.env.MONGODB_URI) {
    throw new Error("MONGODB_URI is required to seed MongoDB.");
  }

  await mongoose.connect(process.env.MONGODB_URI);
  await Lender.deleteMany({});
  const { count } = await syncLenders(Lender);
  console.log(`Synced ${count} lender partners.`);
  await mongoose.disconnect();
};

run().catch((error) => {
  console.error(error);
  process.exit(1);
});
