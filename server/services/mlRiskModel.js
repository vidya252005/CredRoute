import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const modelDir = path.resolve(__dirname, "../../ml/models");
const modelPath = path.join(modelDir, "credit_risk.onnx");
const metadataPath = path.join(modelDir, "metadata.json");
const predictScript = path.resolve(__dirname, "../../ml/predict.py");

let metadata = null;
let modelAvailable = false;

const loadMetadata = () => {
  if (metadata) return metadata;
  if (!fs.existsSync(metadataPath)) return null;
  metadata = JSON.parse(fs.readFileSync(metadataPath, "utf8"));
  return metadata;
};

export const initializeRiskModel = async () => {
  modelAvailable = fs.existsSync(modelPath) && fs.existsSync(predictScript);
  if (!modelAvailable) {
    console.warn("ML risk model not found. Run `npm run ml:setup` to train it from Hugging Face.");
    return false;
  }

  try {
    await predictWithModel({
      age: 30,
      monthlyIncome: 50000,
      cibilScore: 720,
      existingEmis: 10000,
      amount: 100000,
      tenureMonths: 12,
      incomeType: "salaried",
      bankStatementAvgBalance: 45000,
      cityTier: 1,
      pan: "ABCDE1234F",
    });
    const info = loadMetadata();
    console.log(
      `ML risk model ready (${info?.modelType}, AUC ${info?.validationAuc}) via Hugging Face dataset.`,
    );
    return true;
  } catch (error) {
    modelAvailable = false;
    console.warn(
      "ML risk model unavailable. Falling back to heuristic scoring.",
      error instanceof Error ? error.message : error,
    );
    return false;
  }
};

export const predictWithModel = (input) =>
  new Promise((resolve, reject) => {
    if (!modelAvailable) {
      resolve(null);
      return;
    }

    const child = spawn("python3", [predictScript], { stdio: ["pipe", "pipe", "pipe"] });
    let stdout = "";
    let stderr = "";
    const timer = setTimeout(() => {
      child.kill("SIGKILL");
      reject(new Error("ML predictor timed out"));
    }, 15000);

    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });
    child.on("error", (error) => {
      clearTimeout(timer);
      reject(error);
    });
    child.on("close", (code) => {
      clearTimeout(timer);
      if (code !== 0) {
        reject(new Error(stderr || `ML predictor exited with code ${code}`));
        return;
      }

      try {
        const payload = JSON.parse(stdout);
        resolve(payload.defaultProbability);
      } catch (error) {
        reject(error);
      }
    });

    child.stdin.write(JSON.stringify(input));
    child.stdin.end();
  });

export const getModelMetadata = () => loadMetadata();
export const isModelLoaded = () => modelAvailable;

export const mapApplicantToFeatures = (input) => {
  const monthlyIncome = Math.max(input.monthlyIncome, 1);
  const cibilScore = input.cibilScore || 0;
  const existingEmis = input.existingEmis || 0;
  return {
    RevolvingUtilizationOfUnsecuredLines: Math.min(2, input.amount / (monthlyIncome * 12)),
    age: input.age,
    "NumberOfTime30-59DaysPastDueNotWorse": cibilScore > 0 && cibilScore < 680 ? 1 : 0,
    DebtRatio: Math.min(2, existingEmis / monthlyIncome),
    MonthlyIncome: input.monthlyIncome,
    NumberOfOpenCreditLinesAndLoans: Math.min(
      15,
      Math.round(existingEmis / 4000) + (input.tenureMonths >= 24 ? 2 : 1),
    ),
    NumberOfTimes90DaysLate: cibilScore > 0 && cibilScore < 620 ? 1 : 0,
    NumberRealEstateLoansOrLines: input.amount >= 500000 ? 2 : 1,
    "NumberOfTime60-89DaysPastDueNotWorse": cibilScore > 0 && cibilScore < 650 ? 1 : 0,
    NumberOfDependents: loadMetadata()?.trainingMedians?.NumberOfDependents ?? 0,
  };
};
