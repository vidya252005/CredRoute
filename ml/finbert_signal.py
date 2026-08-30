"""Optional FinBERT-India auxiliary financial text signal."""

from __future__ import annotations

import re

STRESS_TERMS = {
    "inconsistent income": 0.18,
    "missed payment": 0.22,
    "medical expense": 0.12,
    "job loss": 0.25,
    "overdraft": 0.16,
    "thin file": 0.1,
    "gig worker": 0.08,
    "stable salary": -0.12,
    "promotion": -0.1,
    "savings": -0.08,
}

_model = None
_tokenizer = None


def _load_finbert():
    global _model, _tokenizer
    if _model is not None:
        return True
    try:
        from transformers import AutoModel, AutoTokenizer
        import torch

        model_name = "Vansh180/FinBERT-India-v1"
        _tokenizer = AutoTokenizer.from_pretrained(model_name)
        _model = AutoModel.from_pretrained(model_name)
        _model.eval()
        return True
    except Exception:
        return False


def keyword_signal(text: str) -> dict:
    lowered = text.lower()
    score = 0.5
    matched = []
    for term, weight in STRESS_TERMS.items():
        if term in lowered:
            score += weight
            matched.append(term)
    score = max(0.0, min(1.0, score))
    return {
        "stressScore": round(score, 3),
        "signalSource": "keyword-fallback",
        "matchedTerms": matched,
    }


def finbert_signal(text: str | None) -> dict:
    if not text or not text.strip():
        return {
            "stressScore": 0.5,
            "signalSource": "none",
            "detail": "No financial text supplied.",
        }

    if not _load_finbert():
        result = keyword_signal(text)
        result["detail"] = "FinBERT unavailable; keyword heuristic used."
        return result

    import torch

    tokens = _tokenizer(text, return_tensors="pt", truncation=True, max_length=128)
    with torch.no_grad():
        outputs = _model(**tokens)
    embedding = outputs.last_hidden_state[:, 0, :]
    norm = torch.norm(embedding, dim=1).item()
    # Auxiliary representation magnitude mapped to a bounded stress proxy — not a credit decision.
    stress = max(0.0, min(1.0, norm / 20.0))
    return {
        "stressScore": round(stress, 3),
        "signalSource": "finbert-india-v1",
        "detail": "Auxiliary financial-text representation only.",
    }
