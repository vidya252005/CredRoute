import { Router } from "express";
import { randomUUID } from "node:crypto";
import { evaluateApplication, routeToBestLender } from "./services/applicationService.js";
import { isValidPan, normalizePan } from "./services/indiaProfile.js";
import { getLenders, getMetrics, listApplications } from "./store.js";
import { rateLimitByIp } from "./middleware/rateLimiter.js";
import { getMetricsContentType, getMetricsPayload } from "./middleware/metrics.js";
import { enqueueEvaluation, getEvaluationQueue } from "./queue.js";

const router = Router();

const numberField = (value, field) => {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed < 0) {
    throw new Error(`${field} must be a non-negative number.`);
  }
  return parsed;
};

const optionalCibil = (value) => {
  if (value === "" || value == null || value === 0) return null;
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || !Number.isInteger(parsed) || parsed < 300 || parsed > 900) {
    throw new Error("cibilScore must be between 300 and 900, or left blank for thin-file.");
  }
  return parsed;
};

const normalizeInput = (body = {}) => {
  const pan = normalizePan(body.pan);
  const input = {
    name: String(body.name || "").trim(),
    pan,
    age: numberField(body.age, "age"),
    monthlyIncome: numberField(body.monthlyIncome, "monthlyIncome"),
    incomeType: String(body.incomeType || ""),
    cibilScore: optionalCibil(body.cibilScore ?? body.creditScore),
    existingEmis: numberField(
      body.existingEmis ?? body.monthlyObligations ?? 0,
      "existingEmis",
    ),
    bankStatementAvgBalance: numberField(body.bankStatementAvgBalance || 0, "bankStatementAvgBalance"),
    cityTier: numberField(body.cityTier || 1, "cityTier"),
    amount: numberField(body.amount, "amount"),
    tenureMonths: numberField(body.tenureMonths, "tenureMonths"),
  };

  if (!input.name) throw new Error("name is required.");
  if (!isValidPan(pan)) throw new Error("pan must match format ABCDE1234F.");
  if (!Number.isInteger(input.age) || input.age < 21 || input.age > 60) {
    throw new Error("age must be between 21 and 60.");
  }
  if (!Number.isInteger(input.tenureMonths)) {
    throw new Error("tenureMonths must be a whole number.");
  }
  if (!["salaried", "self_employed", "msme", "gig"].includes(input.incomeType)) {
    throw new Error("incomeType must be salaried, self_employed, msme, or gig.");
  }
  if (![1, 2, 3].includes(input.cityTier)) {
    throw new Error("cityTier must be 1, 2, or 3.");
  }
  if (![6, 9, 12, 18, 24, 36].includes(input.tenureMonths)) {
    throw new Error("tenureMonths must be one of 6, 9, 12, 18, 24, or 36.");
  }
  return input;
};

router.get("/health", (req, res) => {
  res.json({ ok: true, service: "credroute-india-api" });
});

router.get("/metrics", async (req, res, next) => {
  try {
    if (req.query.format === "prometheus") {
      res.set("Content-Type", getMetricsContentType());
      return res.send(await getMetricsPayload());
    }
    res.json(await getMetrics());
  } catch (error) {
    next(error);
  }
});

router.get("/lenders", async (req, res, next) => {
  try {
    const lenders = await getLenders();
    res.json(lenders);
  } catch (error) {
    next(error);
  }
});

router.get("/applications", async (req, res, next) => {
  try {
    res.json(await listApplications());
  } catch (error) {
    next(error);
  }
});

router.post("/applications/evaluate", rateLimitByIp, async (req, res, next) => {
  try {
    const input = normalizeInput(req.body);
    const idempotencyKey = req.get("Idempotency-Key") || randomUUID();
    const asyncMode = req.query.async === "true" && getEvaluationQueue();

    if (asyncMode) {
      const jobId = await enqueueEvaluation({ input, idempotencyKey });
      return res.status(202).json({ jobId, status: "queued" });
    }

    const { response, idempotentReplay } = await evaluateApplication({ input, idempotencyKey });
    res.status(idempotentReplay ? 200 : 201).json({ ...response, idempotentReplay });
  } catch (error) {
    next(error);
  }
});

router.post("/applications/:id/route", rateLimitByIp, async (req, res, next) => {
  try {
    const result = await routeToBestLender(req.params.id);
    res.status(result.alreadyRouted ? 200 : 201).json(result);
  } catch (error) {
    next(error);
  }
});

router.use((error, req, res, next) => {
  const message = error instanceof Error ? error.message : "Unexpected server error.";
  const status = message.includes("Rate limit")
    ? 429
    : message.includes("Loan stacking")
      ? 409
      : 400;
  res.status(status).json({ error: message });
});

export default router;
