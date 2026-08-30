import client from "prom-client";

client.collectDefaultMetrics({ prefix: "credroute_" });

export const httpRequestDuration = new client.Histogram({
  name: "credroute_http_request_duration_seconds",
  help: "HTTP request latency in seconds",
  labelNames: ["method", "route", "status_code"],
  buckets: [0.05, 0.1, 0.25, 0.5, 1, 2, 5],
});

export const lenderRequestTotal = new client.Counter({
  name: "credroute_lender_requests_total",
  help: "Total lender integration attempts",
  labelNames: ["lender_code", "status"],
});

export const lenderRequestDuration = new client.Histogram({
  name: "credroute_lender_request_duration_seconds",
  help: "Lender integration latency in seconds",
  labelNames: ["lender_code", "status"],
  buckets: [0.05, 0.1, 0.25, 0.5, 1, 2, 5],
});

export const cacheHitTotal = new client.Counter({
  name: "credroute_cache_hits_total",
  help: "Redis cache hits",
  labelNames: ["cache_type"],
});

export const cacheMissTotal = new client.Counter({
  name: "credroute_cache_misses_total",
  help: "Redis cache misses",
  labelNames: ["cache_type"],
});

const cacheStats = { hits: 0, misses: 0 };

export const applicationsTotal = new client.Counter({
  name: "credroute_applications_total",
  help: "Loan applications evaluated",
  labelNames: ["status"],
});

export const offersRankedTotal = new client.Counter({
  name: "credroute_offers_ranked_total",
  help: "Offers ranked after lender matching",
});

export const metricsMiddleware = (req, res, next) => {
  const started = process.hrtime.bigint();
  res.on("finish", () => {
    const elapsed = Number(process.hrtime.bigint() - started) / 1e9;
    httpRequestDuration
      .labels(req.method, req.route?.path || req.path, String(res.statusCode))
      .observe(elapsed);
  });
  next();
};

export const getMetricsPayload = async () => client.register.metrics();

export const getMetricsContentType = () => client.register.contentType;

export const recordLenderAttempt = (attempt) => {
  lenderRequestTotal.labels(attempt.lenderCode, attempt.status).inc();
  lenderRequestDuration
    .labels(attempt.lenderCode, attempt.status)
    .observe((attempt.latencyMs || 0) / 1000);
};

export const recordCacheHit = (cacheType) => {
  cacheStats.hits += 1;
  cacheHitTotal.labels(cacheType).inc();
};

export const recordCacheMiss = (cacheType) => {
  cacheStats.misses += 1;
  cacheMissTotal.labels(cacheType).inc();
};

export const getCacheStats = () => ({ ...cacheStats });
