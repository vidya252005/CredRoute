import { User } from "../../data/models/index.js";
import { isMongoConnected } from "../db.js";
import { normalizePan } from "./indiaProfile.js";

const WINDOW_MS = 24 * 60 * 60 * 1000;
const memoryApplicationsByPan = new Map();

const isStackingEnabled = () =>
  process.env.STACKING_ENABLED
    ? process.env.STACKING_ENABLED === "true"
    : process.env.NODE_ENV === "production";

const getStackingLimit = () => Number(process.env.STACKING_LIMIT || 20);

export const checkLoanStacking = async (pan) => {
  const normalizedPan = normalizePan(pan);
  const limit = getStackingLimit();

  if (!isStackingEnabled()) {
    return { allowed: true, recentCount: 0, limit, pan: normalizedPan };
  }

  const since = new Date(Date.now() - WINDOW_MS);

  if (isMongoConnected()) {
    const recentCount = await User.countDocuments({
      pan: normalizedPan,
      createdAt: { $gte: since },
    });
    return {
      allowed: recentCount < limit,
      recentCount,
      limit,
      pan: normalizedPan,
    };
  }

  const timestamps = memoryApplicationsByPan.get(normalizedPan) || [];
  const recentCount = timestamps.filter((value) => value >= since.getTime()).length;
  return {
    allowed: recentCount < limit,
    recentCount,
    limit,
    pan: normalizedPan,
  };
};

export const recordPanApplication = (pan) => {
  if (!isStackingEnabled()) return;
  const normalizedPan = normalizePan(pan);
  const timestamps = memoryApplicationsByPan.get(normalizedPan) || [];
  timestamps.push(Date.now());
  memoryApplicationsByPan.set(normalizedPan, timestamps.slice(-20));
};
