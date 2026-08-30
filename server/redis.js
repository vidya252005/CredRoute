import Redis from "ioredis";
import { redisUrl } from "./config.js";

let client = null;
let connected = false;

export const connectRedis = async () => {
  if (!redisUrl) return false;

  const probe = new Redis(redisUrl, {
    maxRetriesPerRequest: 1,
    connectTimeout: 2500,
    lazyConnect: true,
    retryStrategy: () => null,
    enableOfflineQueue: false,
  });

  probe.on("error", () => {
    // Suppress noisy connection errors when Redis is not running locally.
  });

  try {
    await probe.connect();
    await probe.ping();
    client = probe;
    connected = true;
    return true;
  } catch (error) {
    probe.disconnect();
    console.warn(
      "Redis is unavailable. CredRoute will skip cache, rate limiting, and queue features.",
      error instanceof Error ? error.message : error,
    );
    client = null;
    connected = false;
    return false;
  }
};

export const isRedisConnected = () => connected && client !== null;

export const getRedis = () => client;

export const cacheGet = async (key) => {
  if (!isRedisConnected()) return null;
  try {
    const value = await client.get(key);
    return value ? JSON.parse(value) : null;
  } catch {
    return null;
  }
};

export const cacheSet = async (key, value, ttlSeconds = 300) => {
  if (!isRedisConnected()) return;
  try {
    await client.set(key, JSON.stringify(value), "EX", ttlSeconds);
  } catch {
    // Cache writes are best-effort.
  }
};

export const incrementRateLimit = async (key, windowSeconds, maxRequests) => {
  if (!isRedisConnected()) return { allowed: true, count: 0, remaining: maxRequests };

  try {
    const count = await client.incr(key);
    if (count === 1) await client.expire(key, windowSeconds);
    return {
      allowed: count <= maxRequests,
      count,
      remaining: Math.max(0, maxRequests - count),
    };
  } catch {
    return { allowed: true, count: 0, remaining: maxRequests };
  }
};
