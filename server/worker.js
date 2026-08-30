import "dotenv/config";
import { connectDatabase } from "./db.js";
import { connectRedis } from "./redis.js";
import { startEvaluationWorker } from "./queue.js";

await connectDatabase();
await connectRedis();
startEvaluationWorker();
console.log("CredRoute evaluation worker is running.");
