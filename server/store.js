import { randomUUID } from "node:crypto";
import {
  ApplicationEvent,
  IdempotencyKey,
  Lender,
  LoanApplication,
  LoanOffer,
  User,
} from "../data/models/index.js";
import { lenderSeedData } from "../data/lenders.js";
import { isMongoConnected } from "./db.js";
import { cacheGet, cacheSet } from "./redis.js";
import { recordCacheHit, recordCacheMiss, getCacheStats } from "./middleware/metrics.js";
import { getCircuitSnapshot } from "./services/circuitBreaker.js";

const APPLICATION_LIST_LIMIT = 25;

const memory = {
  users: [],
  lenders: lenderSeedData.map((lender) => ({ ...lender, id: lender.code, active: true })),
  applications: [],
  offers: [],
  events: [],
  idempotency: new Map(),
};

const lenderRulesCacheKey = (lenderId) => `lender_rules:${lenderId}`;

export const getLenders = async () => {
  if (isMongoConnected()) {
    const lenders = await Lender.find({ active: true }).lean();
    await Promise.all(
      lenders.map(async (lender) => {
        const cached = await cacheGet(lenderRulesCacheKey(lender._id));
        if (cached) recordCacheHit("lender_rules");
        else {
          recordCacheMiss("lender_rules");
          await cacheSet(lenderRulesCacheKey(lender._id), lender, 600);
        }
      }),
    );
    return lenders;
  }
  return memory.lenders.filter((lender) => lender.active);
};

export const getIdempotentResponse = async (key) => {
  if (!key) return null;

  const redisCached = await cacheGet(`idempotency:${key}`);
  if (redisCached) {
    recordCacheHit("idempotency");
    return redisCached;
  }
  recordCacheMiss("idempotency");

  if (isMongoConnected()) {
    const record = await IdempotencyKey.findOne({ key }).lean();
    return record?.response || null;
  }
  return memory.idempotency.get(key) || null;
};

export const saveApplication = async ({
  input,
  eligibility,
  risk,
  offers,
  lenderAttempts,
  idempotencyKey,
}) => {
  if (isMongoConnected()) {
    const user = await User.create({
      name: input.name,
      pan: input.pan,
      age: input.age,
      monthlyIncome: input.monthlyIncome,
      incomeType: input.incomeType,
      cibilScore: input.cibilScore,
      existingEmis: input.existingEmis,
      bankStatementAvgBalance: input.bankStatementAvgBalance,
      cityTier: input.cityTier,
    });
    const application = await LoanApplication.create({
      userId: user._id,
      amount: input.amount,
      tenureMonths: input.tenureMonths,
      status: eligibility.eligible ? "offers_ready" : "ineligible",
      eligibility,
      risk,
      lenderAttempts,
    });
    const offerDocuments = offers.map((offer) => ({
      applicationId: application._id,
      lenderId: offer.lenderId,
      lenderCode: offer.lenderCode,
      lenderName: offer.lenderName,
      interestRate: offer.interestRate,
      processingFee: offer.processingFee,
      approvalProbability: offer.approvalProbability,
      maxAmount: offer.maxAmount,
      rank: offer.rank,
      score: offer.score,
      monthlyPayment: offer.monthlyPayment,
    }));
    const savedOffers = await LoanOffer.insertMany(offerDocuments);
    const response = serializeApplication(
      application.toObject(),
      savedOffers.map((offer) => offer.toObject()),
      user.toObject(),
    );
    await ApplicationEvent.create({
      applicationId: application._id,
      eventType: "application_evaluated",
      metadata: {
        segment: eligibility.profile?.segment,
        offerCount: offers.length,
        failedLenders: lenderAttempts.filter((attempt) => attempt.status === "failed").length,
      },
    });
    if (idempotencyKey) {
      await IdempotencyKey.create({ key: idempotencyKey, response });
      await cacheSet(`idempotency:${idempotencyKey}`, response, 3600);
    }
    const topOffer = savedOffers.find((offer) => offer.rank === 1);
    if (topOffer) {
      await LoanApplication.findByIdAndUpdate(application._id, {
        recommendedOfferId: topOffer._id,
      });
      response.recommendedOfferId = String(topOffer._id);
    }
    return response;
  }

  const user = { _id: randomUUID(), id: randomUUID(), ...input };
  const application = {
    _id: randomUUID(),
    id: randomUUID(),
    userId: user._id,
    amount: input.amount,
    tenureMonths: input.tenureMonths,
    status: eligibility.eligible ? "offers_ready" : "ineligible",
    eligibility,
    risk,
    lenderAttempts,
    routedLenderCode: null,
    createdAt: new Date().toISOString(),
  };
  const savedOffers = offers.map((offer) => ({
    ...offer,
    _id: randomUUID(),
    id: randomUUID(),
    applicationId: application._id,
  }));
  const topOffer = savedOffers.find((offer) => offer.rank === 1);
  if (topOffer) {
    application.recommendedOfferId = topOffer._id;
  }
  const response = serializeApplication(application, savedOffers, user);
  memory.users.push(user);
  memory.applications.push(application);
  memory.offers.push(...savedOffers);
  memory.events.push({
    _id: randomUUID(),
    applicationId: application._id,
    eventType: "application_evaluated",
    createdAt: new Date().toISOString(),
  });
  if (idempotencyKey) {
    memory.idempotency.set(idempotencyKey, response);
    await cacheSet(`idempotency:${idempotencyKey}`, response, 3600);
  }
  return response;
};

export const routeApplication = async (applicationId) => {
  const applications = await listApplications();
  const application = applications.find((item) => item.id === applicationId);
  if (!application) throw new Error("Application not found.");
  if (application.status === "routed") {
    return { application, alreadyRouted: true };
  }
  const recommended = application.offers.find((offer) => offer.rank === 1);
  if (!recommended) throw new Error("No ranked offer available to route.");

  if (isMongoConnected()) {
    await LoanApplication.findByIdAndUpdate(applicationId, {
      status: "routed",
      routedLenderCode: recommended.lenderCode,
      recommendedOfferId: recommended.id,
    });
    await ApplicationEvent.create({
      applicationId,
      eventType: "application_routed",
      metadata: {
        lenderCode: recommended.lenderCode,
        lenderName: recommended.lenderName,
      },
    });
  } else {
    const target = memory.applications.find((item) => item._id === applicationId);
    if (target) {
      target.status = "routed";
      target.routedLenderCode = recommended.lenderCode;
      target.recommendedOfferId = recommended.id;
    }
  }

  return {
    application: {
      ...application,
      status: "routed",
      routedLenderCode: recommended.lenderCode,
    },
    routedOffer: recommended,
    alreadyRouted: false,
  };
};

export const listApplications = async () => {
  if (isMongoConnected()) {
    const applications = await LoanApplication.find()
      .populate("userId")
      .sort({ createdAt: -1 })
      .limit(APPLICATION_LIST_LIMIT)
      .lean();
    const ids = applications.map((application) => application._id);
    const offers = await LoanOffer.find({ applicationId: { $in: ids } })
      .sort({ rank: 1 })
      .lean();
    return applications.map((application) =>
      serializeApplication(
        application,
        offers.filter((offer) => String(offer.applicationId) === String(application._id)),
        application.userId,
      ),
    );
  }
  return memory.applications
    .slice()
    .sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt))
    .slice(0, APPLICATION_LIST_LIMIT)
    .map((application) =>
      serializeApplication(
        application,
        memory.offers.filter((offer) => offer.applicationId === application._id),
        memory.users.find((user) => user._id === application.userId),
      ),
    );
};

export const getMetrics = async () => {
  let attemptSource = [];
  let applicationCount = 0;
  let offerCount = 0;

  if (isMongoConnected()) {
    applicationCount = await LoanApplication.countDocuments();
    offerCount = await LoanOffer.countDocuments();
    attemptSource = await LoanApplication.find().select("lenderAttempts").lean();
  } else {
    applicationCount = memory.applications.length;
    offerCount = memory.offers.length;
    attemptSource = memory.applications;
  }

  const attempts = attemptSource.flatMap((application) => application.lenderAttempts || []);
  const successful = attempts.filter((attempt) => attempt.status === "success");
  const failed = attempts.filter((attempt) => attempt.status === "failed");
  const latencies = attempts.map((attempt) => attempt.latencyMs).filter(Boolean);
  const { hits: cacheHits, misses: cacheMisses } = getCacheStats();
  const cacheTotal = cacheHits + cacheMisses;

  return {
    applications: applicationCount,
    offers: offerCount,
    lenderSuccessRate: attempts.length ? successful.length / attempts.length : 0,
    lenderFailureRate: attempts.length ? failed.length / attempts.length : 0,
    averageLatencyMs: latencies.length
      ? Math.round(latencies.reduce((total, value) => total + value, 0) / latencies.length)
      : 0,
    cacheHitRate: cacheTotal ? cacheHits / cacheTotal : 0,
    circuitBreakers: getCircuitSnapshot(),
    storage: isMongoConnected() ? "mongodb" : "memory-demo",
  };
};

const serializeApplication = (application, offers, user) => ({
  id: String(application._id || application.id),
  createdAt: application.createdAt,
  amount: application.amount,
  tenureMonths: application.tenureMonths,
  status: application.status,
  routedLenderCode: application.routedLenderCode || null,
  recommendedOfferId: application.recommendedOfferId
    ? String(application.recommendedOfferId)
    : null,
  applicant: user
    ? {
        name: user.name,
        pan: user.pan,
        age: user.age,
        monthlyIncome: user.monthlyIncome,
        incomeType: user.incomeType,
        cibilScore: user.cibilScore,
        existingEmis: user.existingEmis,
        bankStatementAvgBalance: user.bankStatementAvgBalance,
        cityTier: user.cityTier,
      }
    : null,
  eligibility: application.eligibility,
  risk: application.risk,
  lenderAttempts: application.lenderAttempts || [],
  offers: offers
    .map((offer) => ({
      id: String(offer._id || offer.id),
      lenderCode: offer.lenderCode,
      lenderName: offer.lenderName,
      interestRate: offer.interestRate,
      processingFee: offer.processingFee,
      approvalProbability: offer.approvalProbability,
      maxAmount: offer.maxAmount,
      rank: offer.rank,
      score: offer.score,
      monthlyPayment: offer.monthlyPayment,
      routingReason: offer.routingReason,
    }))
    .sort((a, b) => a.rank - b.rank),
});
