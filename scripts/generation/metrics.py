# scripts/generation/metrics.py
from __future__ import annotations

from eval_common.models import ScoredRun
from generation.gen_models import CategoryMetrics, GenerationMetrics


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _cards(run) -> dict:
    return {c.scorer: c for c in run.cards}


def aggregate(scored: list[ScoredRun]) -> GenerationMetrics:
    n_total = len(scored)
    n_errors = sum(1 for s in scored if s.run.result is None)

    faith: list[float] = []
    recall: list[float] = []
    by_cat: dict[str, dict[str, list]] = {}

    for s in scored:
        cat = s.run.case.labels.category
        bucket = by_cat.setdefault(cat, {"faith": [], "recall": [], "n": 0})
        bucket["n"] += 1
        cards = _cards(s)

        f = cards.get("faithfulness")
        if f is not None and f.score is not None:
            faith.append(f.score)
            bucket["faith"].append(f.score)

        c = cards.get("completeness")
        if c is not None and c.score is not None:
            recall.append(c.score)
            bucket["recall"].append(c.score)

    faithfulness_mean = _mean(faith)
    by_category = {
        cat: CategoryMetrics(
            n=b["n"],
            faithfulness_mean=_mean(b["faith"]),
            recall_mean=_mean(b["recall"]),
        )
        for cat, b in by_cat.items()
    }
    return GenerationMetrics(
        n_total=n_total,
        n_errors=n_errors,
        faithfulness_mean=faithfulness_mean,
        hallucination_rate=(1 - faithfulness_mean) if faithfulness_mean is not None else None,
        recall_mean=_mean(recall),
        by_category=by_category,
    )
