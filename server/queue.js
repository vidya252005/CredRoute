import { Queue, Worker } from "bullmq";
import { redisUrl } from "./config.js";
import { isRedisConnected } from "./redis.js";
import { evaluateApplication } from "./services/applicationService.js";

let queue = null;

const connection = redisUrl ? { url: redisUrl } : null;

export const getEvaluationQueue = () => {
  if (!connection || !isRedisConnected()) return null;
  if (!queue) {
    queue = new Queue("loan-evaluations", { connection });
  }
  return queue;
};

export const enqueueEvaluation = async (payload) => {
  const evaluationQueue = getEvaluationQueue();
  if (!evaluationQueue) return null;
  const job = await evaluationQueue.add("evaluate", payload, {
    attempts: 3,
    backoff: { type: "exponential", delay: 1000 },
    removeOnComplete: 100,
    removeOnFail: 50,
  });
  return job.id;
};

export const startEvaluationWorker = () => {
  if (!connection) return null;

  const worker = new Worker(
    "loan-evaluations",
    async (job) => evaluateApplication(job.data),
    { connection },
  );

  worker.on("failed", (job, error) => {
    console.error(`Evaluation job ${job?.id} failed:`, error.message);
  });

  return worker;
};
