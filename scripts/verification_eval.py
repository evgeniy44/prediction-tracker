from __future__ import annotations

import argparse
import asyncio
import glob
import json
import logging
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env", override=True)
except ImportError:
    pass

from evaluate_detection import (
    PROVIDER_API_KEY_ENV,
    CONCURRENCY_OVERRIDES,
    MIN_CALL_INTERVAL_SECONDS,
)
from prophet_checker.llm.client import LLMClient
from prophet_checker.llm.prompts import (
    build_verification_prompt_v2,
    get_verification_system_v2,
    parse_verification_response_v2,
)

logger = logging.getLogger(__name__)

MODELS = [
    "anthropic/claude-haiku-4-5",
    "openai/gpt-5-mini",
    "gemini/gemini-3.1-flash-lite-preview",
    "deepseek/deepseek-chat",
    "groq/llama-3.3-70b-versatile",
    "gemini/gemini-2.5-pro",
    "anthropic/claude-sonnet-4-6",
    "anthropic/claude-opus-4-6",
    "openai/gpt-5",
]

COST_PER_CALL_USD = {
    "anthropic/claude-haiku-4-5": 0.001,
    "openai/gpt-5-mini": 0.001,
    "gemini/gemini-3.1-flash-lite-preview": 0.0001,
    "deepseek/deepseek-chat": 0.0003,
    "groq/llama-3.3-70b-versatile": 0.0,
    "gemini/gemini-2.5-pro": 0.003,
    "anthropic/claude-sonnet-4-6": 0.012,
    "anthropic/claude-opus-4-6": 0.025,
    "openai/gpt-5": 0.010,
}

STATUS_LABELS = ("confirmed", "refuted", "unresolved", "premature")
STRENGTH_LABELS = ("low", "medium")
VALUE_LABELS = ("low", "medium", "high")

DEFAULT_GOLD_PATH = PROJECT_ROOT / "scripts" / "data" / "verification_gold_labels.json"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "scripts" / "outputs" / "verification_eval"
PER_MODEL_SUBDIR = "per_model"
METRICS_FILENAME = "verification_eval_metrics.json"
REPORT_FILENAME = "verification_eval_report.md"

BLOCKER_REJECT_RATE = 0.10
BLOCKER_MIN_STATUS_ACC = 0.5
QUALITY_TIER_TOLERANCE = 0.1


def compute_accuracy(pairs: list[tuple]) -> float:
    if not pairs:
        return 0.0
    correct = sum(1 for gold, pred in pairs if gold == pred)
    return correct / len(pairs)


def compute_confusion_matrix(pairs: list[tuple], labels: tuple[str, ...]) -> dict[str, dict[str, int]]:
    matrix = {gold: {pred: 0 for pred in labels} for gold in labels}
    for gold, pred in pairs:
        if gold in matrix and pred in matrix[gold]:
            matrix[gold][pred] += 1
    return matrix


def calibration_stats(items: list[dict]) -> dict:
    correct = [i["confidence"] for i in items if i.get("is_correct")]
    wrong = [i["confidence"] for i in items if i.get("is_correct") is False]
    mean_correct = sum(correct) / len(correct) if correct else None
    mean_wrong = sum(wrong) / len(wrong) if wrong else None
    gap = (mean_correct - mean_wrong) if (mean_correct is not None and mean_wrong is not None) else None
    return {
        "mean_conf_correct": mean_correct,
        "mean_conf_wrong": mean_wrong,
        "gap": gap,
    }


def filter_blockers(per_model: dict) -> tuple[dict, list[dict]]:
    survivors = {}
    filtered = []
    for model, metrics in per_model.items():
        reject = metrics.get("parser_reject_rate", 0.0)
        status_acc = metrics.get("status", {}).get("accuracy", 0.0)
        if reject > BLOCKER_REJECT_RATE:
            filtered.append({"model": model, "reason": f"parser_reject_rate={reject:.3f} > {BLOCKER_REJECT_RATE:.2f}"})
            continue
        if status_acc < BLOCKER_MIN_STATUS_ACC:
            filtered.append({"model": model, "reason": f"status_accuracy={status_acc:.3f} < {BLOCKER_MIN_STATUS_ACC}"})
            continue
        survivors[model] = metrics
    return survivors, filtered


def find_quality_tier(per_model: dict) -> tuple[list[str], float]:
    if not per_model:
        return [], 0.0
    accs = {m: metrics["status"]["accuracy"] for m, metrics in per_model.items()}
    max_acc = max(accs.values())
    threshold = max_acc - QUALITY_TIER_TOLERANCE
    tier = [m for m, acc in accs.items() if acc >= threshold]
    return tier, max_acc


def tie_break_within_tier(tier: list[str], per_model: dict) -> str | None:
    if not tier:
        return None

    def sort_key(model: str) -> tuple:
        m = per_model[model]
        cost = m.get("cost_total_usd", 0.0)
        latency = m.get("latency_mean_seconds", 0.0)
        sv_sum = m.get("prediction_strength", {}).get("accuracy", 0.0) + m.get("prediction_value", {}).get("accuracy", 0.0)
        return (cost, latency, -sv_sum)

    return sorted(tier, key=sort_key)[0]


def apply_decision_framework(per_model: dict) -> dict:
    survivors, filtered = filter_blockers(per_model)
    if not survivors:
        return {
            "step1_filtered_out": filtered,
            "step2_max_status_acc": 0.0,
            "step2_quality_tier": [],
            "step3_winner": None,
            "step3_rationale": "no models passed blocker filter",
        }
    tier, max_acc = find_quality_tier(survivors)
    winner = tie_break_within_tier(tier, survivors)
    if winner is None:
        rationale = "no winner — empty quality tier"
    else:
        w = survivors[winner]
        rationale = f"Tier-1 winner: lowest cost (${w['cost_total_usd']:.2f}), latency {w['latency_mean_seconds']:.2f}s"
    return {
        "step1_filtered_out": filtered,
        "step2_max_status_acc": max_acc,
        "step2_quality_tier": tier,
        "step3_winner": winner,
        "step3_rationale": rationale,
    }


def filename_for_model(model_id: str) -> str:
    safe = model_id.replace("/", "_")
    return f"{safe}.json"


def list_existing_per_model_files(per_model_dir: Path) -> list[str]:
    if not per_model_dir.exists():
        return []
    found = []
    for path in per_model_dir.glob("*.json"):
        stem = path.stem
        if "_" not in stem:
            continue
        provider, _, model = stem.partition("_")
        if provider in PROVIDER_API_KEY_ENV:
            found.append(f"{provider}/{model}")
    return found
