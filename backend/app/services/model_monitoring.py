import json

from app.core.paths import ml_dir
from app.services.feature_engineering import engineer_features


def population_stability_index(reference: dict[str, float], current: dict[str, float]) -> float:
    keys = set(reference) & set(current)
    if not keys:
        return 0.0

    total = 0.0
    for key in keys:
        expected = max(reference[key], 1e-6)
        actual = max(current[key], 1e-6)
        total += (actual - expected) * __import__("math").log(actual / expected)
    return round(abs(total) / len(keys), 4)


def load_model_metadata() -> dict:
    metadata_path = ml_dir() / "models" / "metadata.json"
    if not metadata_path.exists():
        return {}
    return json.loads(metadata_path.read_text(encoding="utf-8"))


def load_experiment_comparison() -> dict:
    comparison_path = ml_dir() / "experiments" / "comparison.json"
    if not comparison_path.exists():
        return {}
    return json.loads(comparison_path.read_text(encoding="utf-8"))


def evaluate_drift(input_data: dict) -> dict:
    metadata = load_model_metadata()
    medians = metadata.get("trainingMedians", {})
    features = engineer_features(input_data)
    structured = features["structuredFeatures"]

    drift_scores = {}
    for key, reference in medians.items():
        if key not in structured:
            continue
        ref = float(reference)
        cur = float(structured[key])
        drift_scores[key] = round(abs(cur - ref) / max(abs(ref), 1e-6), 4)

    avg_drift = round(sum(drift_scores.values()) / len(drift_scores), 4) if drift_scores else 0.0
    alert = avg_drift >= 0.35

    return {
        "averageFeatureDrift": avg_drift,
        "driftAlert": alert,
        "featureDrift": drift_scores,
        "reference": "trainingMedians",
    }


def get_ml_dashboard() -> dict:
    metadata = load_model_metadata()
    comparison = load_experiment_comparison()
    return {
        "activeModel": metadata.get("activeModel"),
        "sourceDataset": metadata.get("sourceDataset"),
        "datasetKind": metadata.get("datasetKind"),
        "defaultRate": metadata.get("defaultRate"),
        "models": metadata.get("models", {}),
        "comparison": comparison,
        "featureColumns": metadata.get("featureColumns", []),
        "finbertModel": metadata.get("finbertModel"),
        "modelCard": metadata.get("modelCard"),
    }
