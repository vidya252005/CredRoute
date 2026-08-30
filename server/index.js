import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import express from "express";
import cors from "cors";
import { createServer as createViteServer } from "vite";
import routes from "./routes.js";
import { connectDatabase } from "./db.js";
import { connectRedis } from "./redis.js";
import { metricsMiddleware } from "./middleware/metrics.js";
import { isProduction, port } from "./config.js";
import { syncLenders } from "../data/lenders.js";
import { Lender } from "../data/models/index.js";
import { initializeRiskModel } from "./services/riskModel.js";
import { isMongoConnected } from "./db.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const rootDir = path.resolve(__dirname, "..");
const clientDir = path.join(rootDir, "client");
const clientDist = path.join(clientDir, "dist");
const useFastApi = process.env.USE_FASTAPI !== "false";
const fastApiTarget = new URL(process.env.FASTAPI_URL || "http://127.0.0.1:8000");
const app = express();

app.use(cors());
app.use(metricsMiddleware);

if (useFastApi) {
  const hopByHop = new Set([
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "content-length",
    "host",
  ]);

  const copyHeaders = (headers) => {
    const next = {};
    for (const [key, value] of Object.entries(headers || {})) {
      if (value == null || hopByHop.has(key.toLowerCase())) continue;
      next[key] = value;
    }
    return next;
  };

  app.use("/api", (req, res) => {
    const bodyChunks = [];
    req.on("data", (chunk) => bodyChunks.push(chunk));
    req.on("end", () => {
      const body = Buffer.concat(bodyChunks);
      const proxyReq = http.request(
        {
          protocol: fastApiTarget.protocol,
          hostname: fastApiTarget.hostname,
          port: fastApiTarget.port || (fastApiTarget.protocol === "https:" ? 443 : 80),
          path: req.originalUrl,
          method: req.method,
          headers: {
            ...copyHeaders(req.headers),
            host: fastApiTarget.host,
            ...(body.length ? { "content-length": String(body.length) } : {}),
          },
          timeout: 20000,
        },
        (proxyRes) => {
          if (res.headersSent) return;
          res.writeHead(proxyRes.statusCode || 500, copyHeaders(proxyRes.headers));
          proxyRes.pipe(res, { end: true });
        },
      );
      proxyReq.on("timeout", () => proxyReq.destroy(new Error("proxy timeout")));
      proxyReq.on("error", () => {
        if (res.headersSent) return;
        res.status(503).json({
          error: {
            code: "API_UNAVAILABLE",
            message: "FastAPI backend is unavailable. Start it with docker compose up api, or npm run dev:api.",
          },
        });
      });
      if (body.length) proxyReq.write(body);
      proxyReq.end();
    });
  });
} else {
  app.use(express.json({ limit: "1mb" }));
  app.use("/api", routes);
}

if (isProduction) {
  const indexPath = path.join(clientDist, "index.html");
  if (!fs.existsSync(indexPath)) {
    console.error("Production frontend missing. Run `npm run build` first.");
    process.exit(1);
  }
  app.use(express.static(clientDist));
  app.use((req, res, next) => {
    if (req.path.startsWith("/api")) return next();
    res.sendFile(indexPath);
  });
} else {
  const vite = await createViteServer({
    root: clientDir,
    server: { middlewareMode: true, hmr: false },
    appType: "spa",
  });
  app.use(vite.middlewares);
}

if (!useFastApi) {
  const mongoConnected = await connectDatabase();
  const redisConnected = await connectRedis();
  await initializeRiskModel();
  if (mongoConnected) {
    const { count } = await syncLenders(Lender);
    console.log(`Synced ${count} India lender partners.`);
  }
  app.listen(port, "0.0.0.0", () => {
    console.log(`CredRoute Node API running on port ${port}.`);
    console.log(`Storage: ${mongoConnected ? "MongoDB" : "in-memory demo mode"}.`);
  });
} else {
  app.listen(port, "0.0.0.0", () => {
    console.log(`CredRoute frontend gateway on port ${port}.`);
    console.log(`Proxying /api -> ${fastApiTarget.origin}`);
  });
}
