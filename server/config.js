import "dotenv/config";

export const port = Number(process.env.PORT || 5000);
export const mongoUri = process.env.MONGODB_URI || "";
export const redisUrl = process.env.REDIS_URL || "";
export const isProduction = process.env.NODE_ENV === "production";
export const rateLimitMax = Number(process.env.RATE_LIMIT_MAX || 20);
export const rateLimitWindowSec = Number(process.env.RATE_LIMIT_WINDOW_SEC || 60);
export const lenderTimeoutMs = Number(process.env.LENDER_TIMEOUT_MS || 3000);
export const lenderMaxRetries = Number(process.env.LENDER_MAX_RETRIES || 2);
export const stackingLimit = Number(process.env.STACKING_LIMIT || 20);
export const stackingEnabled = process.env.STACKING_ENABLED
  ? process.env.STACKING_ENABLED === "true"
  : isProduction;
