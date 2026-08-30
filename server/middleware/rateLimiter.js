import { rateLimitMax, rateLimitWindowSec } from "../config.js";
import { incrementRateLimit } from "../redis.js";

export const rateLimitByIp = async (req, res, next) => {
  const key = `ratelimit:${req.ip || "unknown"}`;
  const result = await incrementRateLimit(key, rateLimitWindowSec, rateLimitMax);

  res.set("X-RateLimit-Limit", String(rateLimitMax));
  res.set("X-RateLimit-Remaining", String(result.remaining));

  if (!result.allowed) {
    return res.status(429).json({
      error: `Rate limit exceeded. Maximum ${rateLimitMax} requests per ${rateLimitWindowSec} seconds.`,
    });
  }

  return next();
};
