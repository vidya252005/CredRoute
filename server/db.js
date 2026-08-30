import mongoose from "mongoose";
import { mongoUri } from "./config.js";

let connected = false;

export const connectDatabase = async () => {
  if (!mongoUri) return false;

  try {
    await mongoose.connect(mongoUri, { serverSelectionTimeoutMS: 2500 });
    connected = true;
    return true;
  } catch (error) {
    console.warn(
      "MongoDB is unavailable. CredRoute is running with clearly-labelled in-memory demo storage.",
      error instanceof Error ? error.message : error,
    );
    return false;
  }
};

export const isMongoConnected = () => connected;