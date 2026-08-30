import {
  getModelMetadata,
  initializeRiskModel,
  isModelLoaded,
  predictWithModel,
} from "./mlRiskModel.js";

const heuristicRisk = (input) => {
  const cibil = input.cibilScore || 650;
  const creditRisk = Math.max(0, Math.min(1, (760 - cibil) / 300));
  const obligationRisk = Math.max(
    0,
    Math.min(1, (input.existingEmis || 0) / Math.max(input.monthlyIncome, 1)),
  );
  const employmentRisk = input.incomeType === "salaried" ? 0.08 : 0.18;

  const defaultProbability = Number(
    Math.min(0.85, 0.08 + creditRisk * 0.4 + obligationRisk * 0.35 + employmentRisk).toFixed(3),
  );
  const fraudProbability = Number(
    Math.min(0.3, 0.02 + (cibil < 650 ? 0.08 : 0.02) + obligationRisk * 0.12).toFixed(3),
  );

  return {
    defaultProbability,
    fraudProbability,
    confidence: Number((0.72 + Math.min(cibil, 850) / 5000).toFixed(3)),
    modelSource: "heuristic-fallback",
  };
};

export const calculateRisk = async (input) => {
  const defaultProbability = await predictWithModel(input);

  if (defaultProbability === null) {
    return heuristicRisk(input);
  }

  const obligationRisk = Math.max(
    0,
    Math.min(1, (input.existingEmis || 0) / Math.max(input.monthlyIncome, 1)),
  );
  const employmentRisk = input.incomeType === "salaried" ? 0.05 : 0.14;
  const cibil = input.cibilScore || 650;
  const fraudProbability = Number(
    Math.min(
      0.35,
      defaultProbability * 0.45 +
        obligationRisk * 0.2 +
        employmentRisk +
        (cibil < 640 ? 0.05 : 0),
    ).toFixed(3),
  );
  const confidence = Number(
    Math.min(0.98, 0.55 + (getModelMetadata()?.validationAuc || 0.79) * 0.35).toFixed(3),
  );

  return {
    defaultProbability: Number(defaultProbability.toFixed(3)),
    fraudProbability,
    confidence,
    modelSource: "huggingface-onnx",
    modelDataset: getModelMetadata()?.sourceDataset || null,
    modelAuc: getModelMetadata()?.validationAuc || null,
  };
};

export { initializeRiskModel, isModelLoaded, getModelMetadata };
