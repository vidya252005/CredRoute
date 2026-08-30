import json
from functools import lru_cache
from pathlib import Path

RULES_PATH = Path(__file__).resolve().parent.parent / "data" / "underwriting_rules.json"


@lru_cache
def load_underwriting_rules() -> dict:
    return json.loads(RULES_PATH.read_text(encoding="utf-8"))


def get_platform_rules() -> dict:
    return load_underwriting_rules()["platform"]


def get_decision_rules() -> dict:
    return load_underwriting_rules()["decision"]


def get_fraud_rules() -> dict:
    return load_underwriting_rules()["fraud"]


def get_alt_data_rules() -> dict:
    return load_underwriting_rules()["altData"]


def get_limit_ladder_rules() -> dict:
    return load_underwriting_rules()["limitLadder"]
