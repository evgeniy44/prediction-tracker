#!/usr/bin/env python3
"""Extraction Quality Evaluation — Task 13.5.

LLM-as-judge eval for prediction extraction quality across 3 models.
See spec: docs/2026-04-21-extraction-quality-eval-design.md
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from extraction_judge_prompts import (
    JUDGE_SYSTEM,
    VERDICT_ORDINAL,
    VERDICT_VALUES,
    build_judge_prompt,
    parse_judge_response,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Aggregation (pure)
# =============================================================================


def _empty_distribution() -> dict[str, int]:
    return {v: 0 for v in VERDICT_VALUES}


def aggregate_metrics(
    judgements: dict, gold_labels: list[dict]
) -> dict:
    """Compute per-model summary report from judgements + gold labels.

    Args:
        judgements: {extractor_id: {post_id: {per_claim: [...], missed_predictions: [...], parse_error: str|None}}}
        gold_labels: list of {"id": str, "has_prediction": bool}

    Returns:
        {"per_model": {extractor_id: {...metrics...}}}

    Posts with `parse_error` set (judge JSON malformed) are counted in
    `parse_error_count` but EXCLUDED from gold_agreement matrix — the
    failure is on the judge infrastructure, not the extractor model, so
    counting them as "no valid extractions" would unfairly penalize the
    extractor.
    """
    gold_index = {g["id"]: g["has_prediction"] for g in gold_labels}
    per_model: dict[str, dict] = {}

    for extractor_id, posts in judgements.items():
        verdict_counts = _empty_distribution()
        invalid_count = 0
        parse_error_count = 0
        ordinal_sum = 0
        ordinal_n = 0
        missed_total = 0
        gold_yes_with_valid = 0
        gold_yes_no_valid = 0
        gold_no_with_valid = 0
        gold_no_no_valid = 0

        for post_id, j in posts.items():
            # Skip parse-error posts entirely (infra failure, not model failure).
            # Counted for visibility but excluded from gold_agreement matrix.
            if j.get("parse_error") is not None:
                parse_error_count += 1
                continue

            claims = j.get("per_claim", [])
            missed = j.get("missed_predictions", [])
            missed_total += len(missed)

            has_valid_extraction = False
            for c in claims:
                v = c.get("verdict")
                if c.get("verdict_invalid") or v not in VERDICT_VALUES:
                    invalid_count += 1
                    continue
                verdict_counts[v] += 1
                ordinal_sum += VERDICT_ORDINAL[v]
                ordinal_n += 1
                if VERDICT_ORDINAL[v] >= 2:  # exact_match, faithful_paraphrase, valid_but_metadata_error
                    has_valid_extraction = True

            gold_yes = gold_index.get(post_id)
            if gold_yes is True:
                if has_valid_extraction:
                    gold_yes_with_valid += 1
                else:
                    gold_yes_no_valid += 1
            elif gold_yes is False:
                if has_valid_extraction:
                    gold_no_with_valid += 1
                else:
                    gold_no_no_valid += 1

        total_claims = sum(verdict_counts.values()) + invalid_count
        avg_score = (ordinal_sum / ordinal_n) if ordinal_n > 0 else 0.0
        hallucination_rate = (
            verdict_counts["hallucination"] / total_claims
            if total_claims > 0
            else 0.0
        )
        gold_yes_total = gold_yes_with_valid + gold_yes_no_valid
        missed_rate = (missed_total / gold_yes_total) if gold_yes_total > 0 else 0.0

        per_model[extractor_id] = {
            "total_claims": total_claims,
            "invalid_verdict_count": invalid_count,
            "parse_error_count": parse_error_count,
            "verdict_distribution": verdict_counts,
            # Float values stored at full precision; rounding happens only
            # in the CLI display layer to avoid lossy aggregation.
            "avg_quality_score": avg_score,
            "hallucination_rate": hallucination_rate,
            "missed_predictions_count": missed_total,
            "missed_rate": missed_rate,
            "gold_agreement": {
                "gold_YES_with_valid_extraction": gold_yes_with_valid,
                "gold_YES_no_valid_extraction": gold_yes_no_valid,
                "gold_NO_with_extractions_labeled_valid": gold_no_with_valid,
                "gold_NO_without_valid_extractions": gold_no_no_valid,
            },
        }

    return {"per_model": per_model}


# =============================================================================
# Stage 1 — extraction orchestration
# =============================================================================


def _serialize_prediction(p) -> dict:
    """Convert a Prediction domain object to JSON-friendly dict."""
    return {
        "claim_text": p.claim_text,
        "prediction_date": p.prediction_date.isoformat() if p.prediction_date else None,
        "target_date": p.target_date.isoformat() if p.target_date else None,
        "topic": p.topic,
    }


async def run_stage1_extraction(
    extractors: list[str],
    posts: list[dict],
    author_filter: str,
    output_path: Path,
    extractor_factory: Callable,
    concurrency: int = 5,
) -> None:
    """Run each extractor over filtered posts, save full extractions to disk.

    Errors during extraction are logged into a separate `errors` map per model;
    the post still appears in `extractions` with an empty claims list.
    """
    filtered_posts = [p for p in posts if p["person_name"] == author_filter]
    extractions: dict[str, dict[str, list[dict]]] = {m: {} for m in extractors}
    errors: dict[str, dict[str, str]] = {m: {} for m in extractors}

    for model_id in extractors:
        extractor = extractor_factory(model_id)
        sem = asyncio.Semaphore(concurrency)

        async def process(post: dict) -> tuple[str, list[dict], str | None]:
            async with sem:
                try:
                    preds = await extractor.extract(
                        text=post["text"],
                        person_id=post["person_name"],
                        document_id=post["id"],
                        person_name=post["person_name"],
                        published_date=post["published_at"],
                    )
                    return post["id"], [_serialize_prediction(p) for p in preds], None
                except Exception as e:
                    logger.exception(
                        "Extraction failed for %s on %s", model_id, post["id"]
                    )
                    return post["id"], [], f"{type(e).__name__}: {e}"

        results = await asyncio.gather(*(process(p) for p in filtered_posts))
        for post_id, claims, err in results:
            extractions[model_id][post_id] = claims
            if err:
                errors[model_id][post_id] = err

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            {
                "metadata": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "dataset_size": len(filtered_posts),
                    "extractors": list(extractors),
                    "author_filter": author_filter,
                },
                "extractions": extractions,
                "errors": errors,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


# =============================================================================
# Stage 2 — judge orchestration
# =============================================================================


async def run_stage2_judge(
    judge_model: str,
    extractions_path: Path,
    posts: list[dict],
    output_path: Path,
    judge_factory: Callable,
    concurrency: int = 1,
    min_call_interval_seconds: float = 0.0,
) -> None:
    """For each (extractor, post, claims) call the judge and save verdicts.

    Posts that errored in Stage 1 are skipped (marked in judgements artifact).
    Judge response parse failures preserve `parse_error` field.

    After completion, prints per-extractor parse-error counts to stderr+console
    so the user can see infra issues at a glance (per Task 13.5 plan revision).
    """
    extractions_artifact = json.loads(extractions_path.read_text(encoding="utf-8"))
    extractions = extractions_artifact["extractions"]
    errors_map = extractions_artifact.get("errors", {})
    posts_by_id = {p["id"]: p for p in posts}

    judge_client = judge_factory(judge_model)
    judgements: dict[str, dict[str, dict]] = {m: {} for m in extractions}

    sem = asyncio.Semaphore(concurrency)

    async def judge_one(
        model_id: str, post_id: str, claims: list[dict]
    ) -> tuple[str, str, dict]:
        # Skip posts that errored in Stage 1
        if post_id in errors_map.get(model_id, {}):
            return model_id, post_id, {
                "skipped_due_to_extraction_error": True,
                "per_claim": [],
                "missed_predictions": [],
            }

        post = posts_by_id.get(post_id)
        if post is None:
            return model_id, post_id, {
                "skipped_post_not_found": True,
                "per_claim": [],
                "missed_predictions": [],
            }

        prompt = build_judge_prompt(
            post_text=post["text"],
            published_date=post["published_at"],
            extracted_claims=claims,
        )
        async with sem:
            try:
                raw = await judge_client.complete(prompt, system=JUDGE_SYSTEM)
            except Exception as e:
                logger.exception(
                    "Judge call failed: %s / %s", model_id, post_id
                )
                return model_id, post_id, {
                    "judge_error": f"{type(e).__name__}: {e}",
                    "per_claim": [],
                    "missed_predictions": [],
                }
            if min_call_interval_seconds > 0:
                await asyncio.sleep(min_call_interval_seconds)

        parsed = parse_judge_response(raw)
        return model_id, post_id, parsed

    tasks = [
        judge_one(m, pid, claims)
        for m, posts_dict in extractions.items()
        for pid, claims in posts_dict.items()
    ]
    results = await asyncio.gather(*tasks)
    for model_id, post_id, parsed in results:
        judgements[model_id][post_id] = parsed

    # Surface parse_error count to console for visibility (infra signal,
    # not model-quality signal). Aggregator excludes these from gold_agreement.
    parse_error_summary: dict[str, int] = {}
    for model_id, posts_dict in judgements.items():
        n_errors = sum(1 for p in posts_dict.values() if p.get("parse_error"))
        if n_errors > 0:
            parse_error_summary[model_id] = n_errors
    if parse_error_summary:
        logger.warning(
            "Judge parse failures: %s. Excluded from gold_agreement matrix.",
            parse_error_summary,
        )
        print(f"  [stage2] judge parse failures: {parse_error_summary}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            {
                "metadata": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "judge": judge_model,
                    "source_extractions": str(extractions_path),
                },
                "judgements": judgements,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


# =============================================================================
# Stage 3 — aggregate report
# =============================================================================


def run_stage3_aggregate(
    judgements_path: Path,
    gold_labels_path: Path,
    output_path: Path,
) -> dict:
    """Load judgements + gold, compute per-model report, save to disk.

    Returns the report dict for in-process use (CLI prints summary table).
    """
    judgements_artifact = json.loads(judgements_path.read_text(encoding="utf-8"))
    judgements = judgements_artifact["judgements"]
    gold_labels = json.loads(gold_labels_path.read_text(encoding="utf-8"))

    report = aggregate_metrics(judgements=judgements, gold_labels=gold_labels)
    report["metadata"] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source_judgements": str(judgements_path),
        "source_gold": str(gold_labels_path),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report
