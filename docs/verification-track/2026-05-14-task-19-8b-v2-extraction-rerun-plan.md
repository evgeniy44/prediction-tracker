# Task 19.8b — V2 Extraction Re-run + Quality Re-eval + Fresh Gold Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **Note:** Tasks 2, 4, 5, 6, 7 are OPERATIONAL — they execute scripts, apply decision rules, or coordinate inline labeling. Only Tasks 1 and 3 follow TDD code-writing pattern.

**Goal:** Run V2 extraction prompt (з context field) через Gemini Flash Lite на 17 Arestovich постах, оцінити quality через Opus judge (Task 13.5 methodology), застосувати decision rule, і запустити inline re-labeling нового gold dataset для downstream Task 19.7b verification eval.

**Architecture:** Two new standalone scripts (`v2_extraction_run.py`, `v2_quality_eval.py`) що reuse інфраструктуру з `evaluate_detection.py` + `extraction_quality_eval.py`. Extraction script bypass'ить `PredictionExtractor` і використовує `parse_extraction_response` напряму щоб дістати context field з parsed dict. Quality eval reuse'ить Task 13.5 judge prompts і aggregation pure functions. Re-labeling — inline chat manual phase (не код).

**Tech Stack:** Python 3.12, asyncio, LiteLLM (via LLMClient), Anthropic Opus 4.6 (judge), Gemini Flash Lite (extractor). Working dir: `/Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker`. Use `.venv/bin/python`.

**Spec:** [`2026-05-14-task-19-8b-v2-extraction-rerun-design.md`](2026-05-14-task-19-8b-v2-extraction-rerun-design.md)

**Prerequisites:** ✅ Task 19.8a landed (commits `fe1f114..ef7f8f2`). `EXTRACTION_TEMPLATE` має context field; `validate_context_in_post` доступний у `prophet_checker.llm.prompts`.

---

## File Structure

| File | Role | LOC est. |
|---|---|---|
| `scripts/v2_extraction_run.py` | NEW. Stage 1 runner — V2 extraction на 17 Arestovich постах, substring validation, JSON output. | ~150 |
| `scripts/v2_quality_eval.py` | NEW. Stage 2 runner — Opus judge на V2 outputs, aggregation, markdown report. | ~150 |
| `tests/test_v2_extraction_run.py` | NEW. Pure-function tests (filter posts, drop hallucinations). | ~50 |
| `scripts/outputs/verification_eval/v2_extraction_outputs.json` | NEW artifact. Output of Stage 1. Gitignored. |  |
| `scripts/outputs/verification_eval/v2_judgements.json` | NEW artifact. Output of Stage 2 (Opus judge). Gitignored. |  |
| `scripts/outputs/verification_eval/v2_quality_eval_report.md` | NEW artifact. Decision-rule comparison report. Gitignored. |  |
| `scripts/data/_legacy/verification_gold_labels_v1.json` | NEW location for archived gold. Committed. |  |
| `scripts/data/verification_gold_labels.json` | UPDATED. Fresh V2 schema з context. Committed. |  |

---

## V1 baseline (Gemini Flash Lite) для Decision Rule

З `scripts/outputs/extraction_eval/extraction_eval_report.json`:

| Metric | V1 Value |
|---|---|
| `avg_quality_score` (ordinal mean) | **2.029** |
| `hallucination_rate` | **0.000** |
| `total_claims` | 35 |
| `missed_predictions_count` | 33 |
| `verdict_distribution` | exact=6, faithful=12, valid_metadata_err=0, not_pred=17, truncated=0, halluc=0 |

**Decision thresholds:**
- ✅ Accept V2: `avg_quality_score ∈ [1.829, 2.229]` AND `hallucination_rate ≤ 0.05`
- ⚠️ Tune V2 prompt: ordinal regression > 0.2 OR hallucination > 5pp
- ❌ Reject V2: catastrophic (e.g. ordinal < 1.5 or hallucination > 0.20)

---

## Task 1: Create `scripts/v2_extraction_run.py`

**Files:**
- Create: `scripts/v2_extraction_run.py`
- Create: `tests/test_v2_extraction_run.py`

### Approach: bypass PredictionExtractor

`PredictionExtractor.extract()` (production code) повертає `Prediction` Pydantic objects без `context` field (не оновлено в 19.8a — поза scope). Для 19.8b script ми викликаємо LLM напряму, parse'имо response, і працюємо з raw dict (де `context` присутній автоматично).

- [ ] **Step 1: Створити skeleton `scripts/v2_extraction_run.py`**

Створити файл з вмістом:

```python
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env", override=True)
except ImportError:
    pass

from evaluate_detection import (
    PROVIDER_API_KEY_ENV,
    MIN_CALL_INTERVAL_SECONDS,
    CONCURRENCY_OVERRIDES,
)
from prophet_checker.llm.client import LLMClient
from prophet_checker.llm.prompts import (
    build_extraction_prompt,
    get_extraction_system,
    parse_extraction_response,
    validate_context_in_post,
)

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini/gemini-3.1-flash-lite-preview"
SAMPLE_POSTS_PATH = PROJECT_ROOT / "scripts" / "data" / "sample_posts.json"
V1_EXTRACTIONS_PATH = PROJECT_ROOT / "scripts" / "outputs" / "extraction_eval" / "extraction_outputs.json"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "scripts" / "outputs" / "verification_eval" / "v2_extraction_outputs.json"


def select_posts_for_v2(posts: list[dict], v1_extractions: dict, model_id: str, author: str) -> list[dict]:
    v1_model_outputs = v1_extractions.get("extractions", {}).get(model_id, {})
    target_post_ids = {pid for pid, claims in v1_model_outputs.items() if claims}
    return [p for p in posts if p["id"] in target_post_ids and p["person_name"] == author]


def build_llm_client(model_id: str) -> LLMClient:
    if "/" not in model_id:
        raise ValueError(f"model_id must be 'provider/model', got {model_id!r}")
    provider, model = model_id.split("/", 1)
    env_var = PROVIDER_API_KEY_ENV.get(provider)
    if not env_var:
        raise ValueError(f"Unknown provider {provider!r}")
    api_key = os.environ.get(env_var)
    if not api_key:
        raise RuntimeError(f"Missing API key for {provider!r}: set {env_var}")
    return LLMClient(provider=provider, model=model, api_key=api_key, temperature=0.0)


async def extract_v2(llm: LLMClient, post: dict) -> list[dict]:
    prompt = build_extraction_prompt(
        text=post["text"],
        person_name=post["person_name"],
        published_date=post["published_at"],
    )
    try:
        response = await llm.complete(prompt, system=get_extraction_system())
    except Exception as e:
        logger.exception("LLM call failed for post %s", post["id"])
        return []
    return parse_extraction_response(response)


def validate_and_drop(raw_claims: list[dict], post_text: str) -> tuple[list[dict], int]:
    kept: list[dict] = []
    drops = 0
    for claim in raw_claims:
        ctx = claim.get("context", "")
        if validate_context_in_post(ctx, post_text):
            kept.append({**claim, "context_validated": True})
        else:
            drops += 1
            logger.warning(
                "Drop hallucinated context: claim=%r ctx_preview=%r",
                claim.get("claim_text", "")[:60],
                ctx[:60],
            )
    return kept, drops


async def run_extraction(model_id: str, posts: list[dict], min_interval: float) -> tuple[list[dict], dict]:
    llm = build_llm_client(model_id)
    extractions: list[dict] = []
    total_raw = 0
    total_drops = 0

    for post in posts:
        raw_claims = await extract_v2(llm, post)
        total_raw += len(raw_claims)
        kept, drops = validate_and_drop(raw_claims, post["text"])
        total_drops += drops
        extractions.append({
            "post_id": post["id"],
            "post_published_at": post["published_at"],
            "post_text": post["text"],
            "claims": kept,
        })
        if min_interval > 0:
            await asyncio.sleep(min_interval)

    stats = {
        "posts_processed": len(posts),
        "claims_raw": total_raw,
        "claims_kept": total_raw - total_drops,
        "claims_hallucinated_drop": total_drops,
    }
    return extractions, stats


def save_artifact(extractions: list[dict], stats: dict, model_id: str, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    artifact = {
        "metadata": {
            "model": model_id,
            "prompt_version": "v2",
            "run_at": datetime.now(timezone.utc).isoformat(),
            **stats,
        },
        "extractions": extractions,
    }
    output_path.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8"
    )


async def main_async(args: argparse.Namespace) -> None:
    posts = json.loads(SAMPLE_POSTS_PATH.read_text(encoding="utf-8"))
    v1_extractions = json.loads(V1_EXTRACTIONS_PATH.read_text(encoding="utf-8"))
    selected = select_posts_for_v2(posts, v1_extractions, args.model, args.author)
    if args.limit:
        selected = selected[: args.limit]
    print(f"V2 extraction model: {args.model}")
    print(f"Selected {len(selected)} posts (author={args.author})")

    min_interval = MIN_CALL_INTERVAL_SECONDS.get(args.model, 0.0)
    if min_interval > 0:
        est_min = len(selected) * min_interval / 60
        print(f"Throttle: {min_interval}s/call → ~{est_min:.1f} min")

    extractions, stats = await run_extraction(args.model, selected, min_interval)
    print(f"Stats: {stats}")
    save_artifact(extractions, stats, args.model, args.output)
    print(f"Saved → {args.output}")


def main() -> None:
    parser = argparse.ArgumentParser(description="V2 extraction run (Task 19.8b Stage 1)")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--author", default="Арестович")
    parser.add_argument("--limit", type=int, default=0, help="Process first N posts (0=all)")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Створити failing tests `tests/test_v2_extraction_run.py`**

```python
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


def test_select_posts_for_v2_keeps_only_posts_with_v1_claims():
    from v2_extraction_run import select_posts_for_v2
    posts = [
        {"id": "A", "person_name": "Арестович"},
        {"id": "B", "person_name": "Арестович"},
        {"id": "C", "person_name": "Арестович"},
        {"id": "D", "person_name": "Інший Автор"},
    ]
    v1_extractions = {
        "extractions": {
            "model-x": {
                "A": [{"claim_text": "Some claim"}],
                "B": [],
                "C": [{"claim_text": "Another"}],
                "D": [{"claim_text": "Other author"}],
            }
        }
    }
    result = select_posts_for_v2(posts, v1_extractions, "model-x", "Арестович")
    assert [p["id"] for p in result] == ["A", "C"]


def test_select_posts_for_v2_filters_by_author():
    from v2_extraction_run import select_posts_for_v2
    posts = [
        {"id": "A", "person_name": "Арестович"},
        {"id": "B", "person_name": "Подоляк"},
    ]
    v1_extractions = {
        "extractions": {
            "m": {"A": [{"claim_text": "X"}], "B": [{"claim_text": "Y"}]}
        }
    }
    result = select_posts_for_v2(posts, v1_extractions, "m", "Арестович")
    assert [p["id"] for p in result] == ["A"]


def test_validate_and_drop_keeps_valid_claims():
    from v2_extraction_run import validate_and_drop
    post_text = "Це повний текст посту з конкретним фрагментом усередині. Кінець."
    raw_claims = [
        {"claim_text": "claim 1", "context": "конкретним фрагментом усередині"},
        {"claim_text": "claim 2", "context": "цього тексту немає у пості"},
    ]
    kept, drops = validate_and_drop(raw_claims, post_text)
    assert drops == 1
    assert len(kept) == 1
    assert kept[0]["claim_text"] == "claim 1"
    assert kept[0]["context_validated"] is True


def test_validate_and_drop_handles_empty_context():
    from v2_extraction_run import validate_and_drop
    raw_claims = [{"claim_text": "x", "context": ""}]
    kept, drops = validate_and_drop(raw_claims, "post text")
    assert drops == 1
    assert kept == []
```

- [ ] **Step 3: Run tests — verify pass**

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker && .venv/bin/python -m pytest tests/test_v2_extraction_run.py -v
```

Expected: 4 PASS

- [ ] **Step 4: Full suite check**

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker && .venv/bin/python -m pytest 2>&1 | tail -3
```

Expected: `154 passed` (150 baseline + 4 new)

- [ ] **Step 5: Smoke test — dry run з `--limit 1`**

Спершу перевір що script хоча б завантажується без API call (просто help):

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker && .venv/bin/python scripts/v2_extraction_run.py --help
```

Expected: argparse help text з прапорами `--model`, `--author`, `--limit`, `--output`.

- [ ] **Step 6: Commit**

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker && git add scripts/v2_extraction_run.py tests/test_v2_extraction_run.py && git commit -m "feat(scripts): v2_extraction_run.py — V2 extraction з context validation"
```

---

## Task 2: Execute V2 extraction (operational)

**Files:** none modified — produces `scripts/outputs/verification_eval/v2_extraction_outputs.json`

- [ ] **Step 1: Перевірити що GEMINI_API_KEY встановлено**

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker && .venv/bin/python -c "
import os
from pathlib import Path
try:
    from dotenv import load_dotenv
    load_dotenv(Path('.env'), override=True)
except ImportError:
    pass
key = os.environ.get('GEMINI_API_KEY', '')
print('GEMINI_API_KEY set:', bool(key), f'(length={len(key)})')
"
```

Expected: `GEMINI_API_KEY set: True (length=39)` (Google AI keys are typically ~39 chars). Якщо False — set у `.env` файлі і повтори.

- [ ] **Step 2: Smoke run з `--limit 1` (1 пост, ~10s)**

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker && .venv/bin/python scripts/v2_extraction_run.py --limit 1 --output scripts/outputs/verification_eval/_smoke_v2_extract.json
```

Expected output: щось схоже на
```
V2 extraction model: gemini/gemini-3.1-flash-lite-preview
Selected 1 posts (author=Арестович)
Throttle: 7.0s/call → ~0.1 min
Stats: {'posts_processed': 1, 'claims_raw': N, 'claims_kept': N-K, 'claims_hallucinated_drop': K}
Saved → scripts/outputs/verification_eval/_smoke_v2_extract.json
```

Перевір артефакт:
```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker && .venv/bin/python -c "
import json
d = json.load(open('scripts/outputs/verification_eval/_smoke_v2_extract.json'))
print('Posts:', len(d['extractions']))
post = d['extractions'][0]
print('Post:', post['post_id'])
print('Claims:', len(post['claims']))
if post['claims']:
    c = post['claims'][0]
    print('Sample claim keys:', list(c.keys()))
    print('Sample context length:', len(c.get('context', '')))
"
```

Expected: claims present, кожен claim має ключі `claim_text, prediction_date, target_date, topic, context, context_validated`. Якщо `context` key відсутній — модель не дотримала prompt. Якщо `context_validated: True` для всіх — substring check pass.

- [ ] **Step 3: Прибрати smoke artifact**

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker && rm scripts/outputs/verification_eval/_smoke_v2_extract.json
```

- [ ] **Step 4: Full run на 17 постах (~3 min wall з 7s throttle)**

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker && .venv/bin/python scripts/v2_extraction_run.py
```

Expected:
```
V2 extraction model: gemini/gemini-3.1-flash-lite-preview
Selected 17 posts (author=Арестович)
Throttle: 7.0s/call → ~2.0 min
Stats: {'posts_processed': 17, 'claims_raw': ~33-37, 'claims_kept': ≥28, 'claims_hallucinated_drop': <8}
Saved → scripts/outputs/verification_eval/v2_extraction_outputs.json
```

- [ ] **Step 5: Sanity check артефакту**

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker && .venv/bin/python -c "
import json
d = json.load(open('scripts/outputs/verification_eval/v2_extraction_outputs.json'))
m = d['metadata']
print(f'Model: {m[\"model\"]}')
print(f'Posts: {m[\"posts_processed\"]}')
print(f'Raw claims: {m[\"claims_raw\"]}')
print(f'Kept: {m[\"claims_kept\"]}')
print(f'Dropped (hallucinated): {m[\"claims_hallucinated_drop\"]}')
drop_rate = m['claims_hallucinated_drop'] / max(m['claims_raw'], 1)
print(f'Drop rate: {drop_rate:.1%}')
print(f'Expected drop_rate <30% threshold: {drop_rate < 0.30}')
"
```

Expected: drop_rate < 30%. Якщо drop_rate ≥ 30% — investigate (можливо problem з prompt instruction, або whitespace normalize too strict). DONE_WITH_CONCERNS — escalate to user before continuing.

- [ ] **Step 6: Smoke — кожен kept claim має context_validated=True**

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker && .venv/bin/python -c "
import json
d = json.load(open('scripts/outputs/verification_eval/v2_extraction_outputs.json'))
all_validated = all(
    c.get('context_validated') is True
    for ext in d['extractions']
    for c in ext['claims']
)
print(f'All kept claims have context_validated=True: {all_validated}')
"
```

Expected: True

Stage 1 DONE. Артефакт `v2_extraction_outputs.json` готовий для Stage 2.

---

## Task 3: Create `scripts/v2_quality_eval.py`

**Files:**
- Create: `scripts/v2_quality_eval.py`

Цей скрипт reuse'ить existing infrastructure з `scripts/extraction_quality_eval.py` для judge-based evaluation, але працює зі звичайним V2 artifact format (наш schema `{metadata, extractions: [{post_id, claims: [...]}]}`) а не з Task 13.5 format (`{extractions: {model: {post_id: [claims]}}}`).

- [ ] **Step 1: Створити skeleton `scripts/v2_quality_eval.py`**

Створити файл:

```python
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env", override=True)
except ImportError:
    pass

from extraction_judge_prompts import (
    JUDGE_SYSTEM,
    VERDICT_ORDINAL,
    VERDICT_VALUES,
    build_judge_prompt,
    parse_judge_response,
)
from evaluate_detection import PROVIDER_API_KEY_ENV
from extraction_quality_eval import aggregate_metrics
from prophet_checker.llm.client import LLMClient

logger = logging.getLogger(__name__)

DEFAULT_JUDGE = "anthropic/claude-opus-4-6"
DEFAULT_MODEL_LABEL = "gemini-flash-lite-v2"
JUDGE_MIN_INTERVAL = 8.0
V1_REPORT_PATH = PROJECT_ROOT / "scripts" / "outputs" / "extraction_eval" / "extraction_eval_report.json"
DEFAULT_V2_EXTRACTIONS = PROJECT_ROOT / "scripts" / "outputs" / "verification_eval" / "v2_extraction_outputs.json"
DEFAULT_JUDGEMENTS_OUT = PROJECT_ROOT / "scripts" / "outputs" / "verification_eval" / "v2_judgements.json"
DEFAULT_REPORT_OUT = PROJECT_ROOT / "scripts" / "outputs" / "verification_eval" / "v2_quality_eval_report.md"
GOLD_LABELS_PATH = PROJECT_ROOT / "scripts" / "data" / "gold_labels.json"


def build_judge_client(model_id: str) -> LLMClient:
    if "/" not in model_id:
        raise ValueError(f"model_id must be 'provider/model', got {model_id!r}")
    provider, model = model_id.split("/", 1)
    env_var = PROVIDER_API_KEY_ENV.get(provider)
    if not env_var:
        raise ValueError(f"Unknown provider {provider!r}")
    api_key = os.environ.get(env_var)
    if not api_key:
        raise RuntimeError(f"Missing API key for {provider!r}: set {env_var}")
    return LLMClient(provider=provider, model=model, api_key=api_key, temperature=0.0)


async def judge_post(
    judge: LLMClient, post_text: str, published_date: str, claims: list[dict]
) -> dict:
    if not claims:
        return {"per_claim": [], "missed_predictions": []}
    prompt = build_judge_prompt(
        post_text=post_text, published_date=published_date, extracted_claims=claims,
    )
    try:
        raw = await judge.complete(prompt, system=JUDGE_SYSTEM)
    except Exception as e:
        logger.exception("Judge call failed")
        return {
            "judge_error": f"{type(e).__name__}: {e}",
            "per_claim": [],
            "missed_predictions": [],
        }
    return parse_judge_response(raw)


async def run_judging(
    judge_model: str, v2_artifact: dict, min_interval: float
) -> dict[str, dict]:
    judge = build_judge_client(judge_model)
    judgements: dict[str, dict] = {}
    extractions = v2_artifact["extractions"]
    print(f"  [judge] processing {len(extractions)} posts...", flush=True)
    for idx, ext in enumerate(extractions, 1):
        post_id = ext["post_id"]
        verdict = await judge_post(
            judge,
            ext["post_text"],
            ext["post_published_at"],
            ext["claims"],
        )
        judgements[post_id] = verdict
        print(f"  [judge] {idx}/{len(extractions)} done ({post_id})", flush=True)
        if min_interval > 0:
            await asyncio.sleep(min_interval)
    return judgements


def save_judgements(
    judgements: dict[str, dict], judge_model: str, output_path: Path
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            {
                "metadata": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "judge": judge_model,
                },
                "judgements": {DEFAULT_MODEL_LABEL: judgements},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def compute_v2_metrics(judgements: dict[str, dict], gold_labels: list[dict]) -> dict:
    wrapped = {DEFAULT_MODEL_LABEL: judgements}
    return aggregate_metrics(wrapped, gold_labels)


def load_v1_baseline() -> dict | None:
    if not V1_REPORT_PATH.exists():
        return None
    rep = json.loads(V1_REPORT_PATH.read_text(encoding="utf-8"))
    return rep.get("per_model", {}).get("gemini/gemini-3.1-flash-lite-preview")


def apply_decision_rule(v2_metrics: dict, v1: dict | None) -> tuple[str, str]:
    if v1 is None:
        return "UNKNOWN", "V1 baseline not found — cannot compare"
    v2 = v2_metrics["per_model"][DEFAULT_MODEL_LABEL]
    ord_v1 = v1["avg_quality_score"]
    ord_v2 = v2["avg_quality_score"]
    hall_v1 = v1["hallucination_rate"]
    hall_v2 = v2["hallucination_rate"]

    ord_delta = ord_v2 - ord_v1
    hall_delta = hall_v2 - hall_v1

    if abs(ord_delta) <= 0.2 and hall_delta <= 0.05:
        verdict = "ACCEPT"
        reason = f"ordinal Δ={ord_delta:+.3f} within ±0.2; hallucination Δ={hall_delta:+.3f} ≤ +0.05"
    elif ord_delta < -0.5 or hall_delta > 0.20:
        verdict = "REJECT"
        reason = f"catastrophic regression: ordinal Δ={ord_delta:+.3f}, hallucination Δ={hall_delta:+.3f}"
    else:
        verdict = "TUNE"
        reason = f"moderate regression: ordinal Δ={ord_delta:+.3f}, hallucination Δ={hall_delta:+.3f}"
    return verdict, reason


def render_report(
    v2_metrics: dict, v1: dict | None, verdict: str, reason: str, output_path: Path
) -> None:
    v2 = v2_metrics["per_model"][DEFAULT_MODEL_LABEL]
    lines = [
        "# V2 Extraction Quality Re-evaluation Report",
        "",
        f"**Date:** {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
        f"**Model:** gemini/gemini-3.1-flash-lite-preview",
        f"**Prompt:** v2 (with context field)",
        "",
        "## Decision",
        "",
        f"**Verdict:** `{verdict}`",
        f"**Reason:** {reason}",
        "",
        "## Metrics Comparison",
        "",
        "| Metric | V1 baseline | V2 (this run) | Delta |",
        "|---|---|---|---|",
    ]
    if v1:
        lines.extend([
            f"| total_claims | {v1['total_claims']} | {v2['total_claims']} | {v2['total_claims'] - v1['total_claims']:+d} |",
            f"| avg_quality_score | {v1['avg_quality_score']:.3f} | {v2['avg_quality_score']:.3f} | {v2['avg_quality_score'] - v1['avg_quality_score']:+.3f} |",
            f"| hallucination_rate | {v1['hallucination_rate']:.3f} | {v2['hallucination_rate']:.3f} | {v2['hallucination_rate'] - v1['hallucination_rate']:+.3f} |",
            f"| missed_predictions_count | {v1['missed_predictions_count']} | {v2['missed_predictions_count']} | {v2['missed_predictions_count'] - v1['missed_predictions_count']:+d} |",
        ])
    else:
        lines.append("| (V1 baseline not loaded — comparison N/A) | | | |")

    lines.extend([
        "",
        "## V2 Verdict Distribution",
        "",
    ])
    for verdict_name in VERDICT_VALUES:
        count = v2["verdict_distribution"].get(verdict_name, 0)
        lines.append(f"- `{verdict_name}`: {count}")

    lines.extend([
        "",
        "## Gold Agreement (V2)",
        "",
        f"```",
        json.dumps(v2.get("gold_agreement", {}), indent=2),
        f"```",
        "",
    ])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")


async def main_async(args: argparse.Namespace) -> None:
    v2_artifact = json.loads(args.input.read_text(encoding="utf-8"))
    gold_labels = json.loads(GOLD_LABELS_PATH.read_text(encoding="utf-8"))

    print(f"Judging V2 extractions via {args.judge}")
    judgements = await run_judging(args.judge, v2_artifact, JUDGE_MIN_INTERVAL)
    save_judgements(judgements, args.judge, args.judgements_out)
    print(f"Saved judgements → {args.judgements_out}")

    metrics = compute_v2_metrics(judgements, gold_labels)
    v1 = load_v1_baseline()
    verdict, reason = apply_decision_rule(metrics, v1)
    render_report(metrics, v1, verdict, reason, args.report_out)
    print(f"Saved report → {args.report_out}")
    print(f"\nDECISION: {verdict}")
    print(f"REASON: {reason}")


def main() -> None:
    parser = argparse.ArgumentParser(description="V2 quality re-eval (Task 19.8b Stage 2)")
    parser.add_argument("--input", type=Path, default=DEFAULT_V2_EXTRACTIONS)
    parser.add_argument("--judge", default=DEFAULT_JUDGE)
    parser.add_argument("--judgements-out", type=Path, default=DEFAULT_JUDGEMENTS_OUT)
    parser.add_argument("--report-out", type=Path, default=DEFAULT_REPORT_OUT)
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Smoke test — script loads без помилок**

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker && .venv/bin/python scripts/v2_quality_eval.py --help
```

Expected: argparse help text з прапорами `--input`, `--judge`, `--judgements-out`, `--report-out`.

- [ ] **Step 3: Smoke test — decision rule pure function**

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker && .venv/bin/python -c "
import sys
sys.path.insert(0, 'scripts')
from v2_quality_eval import apply_decision_rule, DEFAULT_MODEL_LABEL

v2_metrics = {'per_model': {DEFAULT_MODEL_LABEL: {'avg_quality_score': 2.0, 'hallucination_rate': 0.0}}}
v1 = {'avg_quality_score': 2.029, 'hallucination_rate': 0.0}
verdict, reason = apply_decision_rule(v2_metrics, v1)
print('Test 1 (within tolerance):', verdict, '|', reason)
assert verdict == 'ACCEPT'

v2_metrics['per_model'][DEFAULT_MODEL_LABEL]['avg_quality_score'] = 1.5
verdict, reason = apply_decision_rule(v2_metrics, v1)
print('Test 2 (moderate regression):', verdict, '|', reason)
assert verdict == 'TUNE'

v2_metrics['per_model'][DEFAULT_MODEL_LABEL]['avg_quality_score'] = 1.0
v2_metrics['per_model'][DEFAULT_MODEL_LABEL]['hallucination_rate'] = 0.30
verdict, reason = apply_decision_rule(v2_metrics, v1)
print('Test 3 (catastrophic):', verdict, '|', reason)
assert verdict == 'REJECT'

print('All decision-rule cases pass.')
"
```

Expected output ends з `All decision-rule cases pass.`

- [ ] **Step 4: Commit**

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker && git add scripts/v2_quality_eval.py && git commit -m "feat(scripts): v2_quality_eval.py — Opus judge + decision rule"
```

---

## Task 4: Execute V2 quality re-eval (operational)

**Files:** none modified — produces `v2_judgements.json` + `v2_quality_eval_report.md`

- [ ] **Step 1: Перевірити ANTHROPIC_API_KEY**

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker && .venv/bin/python -c "
import os
from pathlib import Path
try:
    from dotenv import load_dotenv
    load_dotenv(Path('.env'), override=True)
except ImportError:
    pass
key = os.environ.get('ANTHROPIC_API_KEY', '')
print('ANTHROPIC_API_KEY set:', bool(key), f'(length={len(key)})')
"
```

Expected: True, length ~95-110 chars.

- [ ] **Step 2: Full quality eval run (~17 calls × 8s throttle = ~2.5 min)**

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker && .venv/bin/python scripts/v2_quality_eval.py
```

Expected output:
```
Judging V2 extractions via anthropic/claude-opus-4-6
  [judge] processing 17 posts...
  [judge] 1/17 done (O_Arestovich_official_1395)
  [judge] 2/17 done (O_Arestovich_official_1585)
  ...
  [judge] 17/17 done (...)
Saved judgements → scripts/outputs/verification_eval/v2_judgements.json
Saved report → scripts/outputs/verification_eval/v2_quality_eval_report.md

DECISION: ACCEPT | TUNE | REJECT
REASON: ordinal Δ=... within ±0.2; hallucination Δ=... ≤ +0.05
```

- [ ] **Step 3: Sanity check артефактів**

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker && ls -la scripts/outputs/verification_eval/v2_judgements.json scripts/outputs/verification_eval/v2_quality_eval_report.md
```

Expected: обидва файли existant, judgements ~20-50 KB, report ~2-4 KB.

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker && cat scripts/outputs/verification_eval/v2_quality_eval_report.md
```

Expected: markdown з sections "Decision", "Metrics Comparison", "V2 Verdict Distribution", "Gold Agreement".

---

## Task 5: Decision rule analysis + escalation

**Files:** none modified (analytical step)

Decision rule вже автоматично застосована у Task 4 (script printed `DECISION:` line). Цей step — human review результату.

- [ ] **Step 1: Прочитати report**

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker && cat scripts/outputs/verification_eval/v2_quality_eval_report.md
```

Knowing thresholds:
- V1 ordinal: **2.029**, V1 hallucination: **0.000**
- ✅ Accept: `avg_quality_score ∈ [1.829, 2.229]` AND `hallucination_rate ≤ 0.05`
- ⚠️ Tune: ordinal delta < -0.2 OR hallucination delta > +0.05 (але not catastrophic)
- ❌ Reject: ordinal < 1.5 OR hallucination > 0.20

- [ ] **Step 2: Apply decision**

Based on верхній output's `DECISION:` line:

- Якщо **ACCEPT** → continue to Task 6 (re-labeling). No action needed.
- Якщо **TUNE** → STOP. Report DONE_WITH_CONCERNS to user. Need prompt tuning у 19.8a iteration. Out of scope для current plan.
- Якщо **REJECT** → STOP. Report BLOCKED. Need design revision (escalate до брейнштормінга 19.8a alternative).
- Якщо **UNKNOWN** (V1 baseline missing) → перевір що `scripts/outputs/extraction_eval/extraction_eval_report.json` existant та містить `gemini/gemini-3.1-flash-lite-preview` key.

Step 5 — checkpoint. Якщо decision = ACCEPT, proceed. Else stop and escalate.

---

## Task 6: Inline re-labeling (manual phase, no code)

**Files:**
- Create: `scripts/data/_legacy/verification_gold_labels_v1.json` (move existing)
- Create: `scripts/outputs/verification_eval/_partial_v2_labels.json` (working file)
- Update: `scripts/data/verification_gold_labels.json` (новий, replaces existing)

Це INTERACTIVE chat-based step. Не subagent task — користувач (Claude assistant) і human (you) працюють разом.

- [ ] **Step 1: Archive existing gold v1**

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker && mkdir -p scripts/data/_legacy && git mv scripts/data/verification_gold_labels.json scripts/data/_legacy/verification_gold_labels_v1.json && git commit -m "data: archive verification_gold_labels v1 (no context field) → _legacy"
```

- [ ] **Step 2: Initialize empty new gold file**

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker && mkdir -p scripts/outputs/verification_eval && echo '{"predictions": []}' > scripts/outputs/verification_eval/_partial_v2_labels.json
```

- [ ] **Step 3: Re-labeling workflow (inline chat, ~1.5h)**

Workflow specification — це instruction для assistant який буде running inline labeling session:

**Setup phase (assistant виконує одноразово):**
1. Load `scripts/outputs/verification_eval/v2_extraction_outputs.json` — це source of claims.
2. Build candidate list: для кожного claim, генерувати entry з:
   - `id = f"tg:{post_id}:{claim_index}"` (1-based)
   - `claim_text`, `context`, `prediction_date`, `target_date`, `topic` з V2 output
   - `post_id`, `post_excerpt` (можна використати `post_text[:500]` для контексту, але `context` field уже focused)
3. Print loop status: "[N/M] starting labeling, today=2026-05-14".

**Per-claim loop (repeat for each candidate):**

Assistant presents claim з proposed labels:

```
[N/M] id: tg:O_Arestovich_official_1395:1
Claim:       "..."
Pred date:   2021-10-06
Target date: null
Topic:       міжнародні відносини
Context:     "<verbatim quote from V2 extraction>"

My proposal:
  status:              <one of confirmed/refuted/unresolved/premature>
  confidence:          <0.0-1.0>
  prediction_strength: <low/medium/high — assess CLAIM formulation quality>
  prediction_value:    <low/medium/high — assess EVENT importance>
  reasoning:           "<1-3 sentences>"
  evidence:            <"text" або null>
  retry_after:         <YYYY-MM-DD або null>
  max_horizon:         <YYYY-MM-DD або null>

Action: [a]ccept / [e]dit / [s]kip / [q]uit-save
```

**User responds:** `a` / `e <field>: <new value>` / `s` / `q`.

**On `a` (accept):** assistant appends entry до `_partial_v2_labels.json` і переходить до next.

**On `e <field>: <new value>`:** assistant updates the proposed field, presents updated proposal, чекає на наступний command.

**On `s`:** assistant skips (e.g., bad claim, not really a prediction) — не зберігає, переходить до next.

**On `q`:** assistant saves current progress, exits loop. Resume on next chat session by re-reading `_partial_v2_labels.json`.

**Stop conditions:** all candidates processed OR `q`.

- [ ] **Step 4: Validation після labeling**

Коли labeling complete:

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker && .venv/bin/python -c "
import json
d = json.load(open('scripts/outputs/verification_eval/_partial_v2_labels.json'))
preds = d['predictions']
print(f'Total entries: {len(preds)}')
required_fields = {'id', 'post_id', 'claim_text', 'context', 'prediction_date',
    'target_date', 'topic', 'expected_status', 'expected_confidence',
    'expected_strength', 'expected_value', 'expected_reasoning',
    'expected_evidence', 'expected_retry_after', 'expected_max_horizon'}
missing_anywhere = set()
for p in preds:
    missing = required_fields - set(p.keys())
    if missing:
        missing_anywhere.update(missing)
        print(f'  Entry {p.get(\"id\", \"?\")} missing: {missing}')
if not missing_anywhere:
    print('All entries have required fields ✓')
contexts_present = sum(1 for p in preds if p.get('context'))
print(f'Entries with non-empty context: {contexts_present}/{len(preds)}')
"
```

Expected: All entries have required fields ✓; contexts_present = all entries.

- [ ] **Step 5: Finalize gold file з metadata**

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker && .venv/bin/python -c "
import json
from datetime import datetime, UTC
from collections import Counter

src = 'scripts/outputs/verification_eval/_partial_v2_labels.json'
dst = 'scripts/data/verification_gold_labels.json'

d = json.load(open(src))
preds = d['predictions']

status_dist = dict(Counter(p['expected_status'] for p in preds))
strength_dist = dict(Counter(p['expected_strength'] for p in preds))
value_dist = dict(Counter(p['expected_value'] for p in preds))

final = {
    'metadata': {
        'completed_at': datetime.now(UTC).isoformat(),
        'today': '2026-05-14',
        'total_entries': len(preds),
        'skipped': 0,
        'person': 'Олексій Арестович',
        'source': 'Telegram @O_Arestovich_official',
        'extraction_model': 'gemini/gemini-3.1-flash-lite-preview (V2 prompt with context)',
        'labeling_method': 'inline chat review з V2 context pre-fill',
        'schema': 'V2 with prediction_value + context (EIGHT outputs + extracted context)',
        'distribution': {
            'status': status_dist,
            'prediction_strength': strength_dist,
            'prediction_value': value_dist,
        },
    },
    'predictions': preds,
}
with open(dst, 'w') as f:
    json.dump(final, f, ensure_ascii=False, indent=2)
print(f'Wrote {dst}')
print(f'Entries: {len(preds)}')
print(f'Status: {status_dist}')
print(f'Strength: {strength_dist}')
print(f'Value: {value_dist}')
"
```

Expected: gold file written, distributions printed.

---

## Task 7: Final commit + verification

**Files:**
- Modified: `scripts/data/verification_gold_labels.json` (new content)
- Already moved: `scripts/data/_legacy/verification_gold_labels_v1.json` (від Task 6 Step 1)

- [ ] **Step 1: Sanity check — нова gold має context field everywhere**

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker && .venv/bin/python -c "
import json
d = json.load(open('scripts/data/verification_gold_labels.json'))
preds = d['predictions']
print(f'Total: {len(preds)}')
ctxs_with_text = sum(1 for p in preds if p.get('context') and p['context'].strip())
print(f'With non-empty context: {ctxs_with_text}/{len(preds)}')
assert ctxs_with_text == len(preds), 'Some entries missing context'
print('Schema OK')
print(f'Distribution: {d[\"metadata\"][\"distribution\"]}')
"
```

Expected: всі entries мають non-empty context, no AssertionError.

- [ ] **Step 2: Sanity check — _legacy file існує**

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker && ls -la scripts/data/_legacy/verification_gold_labels_v1.json && .venv/bin/python -c "
import json
d = json.load(open('scripts/data/_legacy/verification_gold_labels_v1.json'))
print(f'V1 legacy entries: {len(d[\"predictions\"])}')
has_context = any('context' in p for p in d['predictions'])
print(f'V1 has context field: {has_context} (expected False)')
"
```

Expected: 35 entries, has_context=False (legacy was без context).

- [ ] **Step 3: Run pytest — verify nothing broken**

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker && .venv/bin/python -m pytest 2>&1 | tail -3
```

Expected: `154 passed` (150 baseline + 4 нових з Task 1)

- [ ] **Step 4: Commit fresh gold**

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker && git add scripts/data/verification_gold_labels.json && git commit -m "data: fresh gold (V2 extraction context) для verification eval"
```

- [ ] **Step 5: Final git log review**

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker && git log --oneline | head -10
```

Expected (most recent first):
- `<hash>` data: fresh gold (V2 extraction context) для verification eval
- `<hash>` data: archive verification_gold_labels v1 (no context field) → _legacy
- `<hash>` feat(scripts): v2_quality_eval.py — Opus judge + decision rule
- `<hash>` feat(scripts): v2_extraction_run.py — V2 extraction з context validation
- ... (попередні commits)

---

## Done criteria

- ✅ `scripts/v2_extraction_run.py` + 4 pure tests pass (154 total)
- ✅ `scripts/v2_quality_eval.py` exists, decision-rule unit smoke pass
- ✅ `scripts/outputs/verification_eval/v2_extraction_outputs.json` exists з ~30-37 claims, drop_rate < 30%
- ✅ `scripts/outputs/verification_eval/v2_judgements.json` exists
- ✅ `scripts/outputs/verification_eval/v2_quality_eval_report.md` exists з DECISION = ACCEPT (else escalate)
- ✅ `scripts/data/_legacy/verification_gold_labels_v1.json` archived
- ✅ `scripts/data/verification_gold_labels.json` updated з context field, distribution stats
- ✅ All entries у gold have non-empty `context`
- ✅ pytest 154 passing

---

## Caveats та notes для implementer

1. **V1 baseline cleanly comparable.** V1 використовував Gemini Flash Lite з V1 prompt на 17 Arestovich постах. V2 використовує той самий model на тих самих постах з V2 prompt. Direct comparison коректний.

2. **PredictionExtractor.extract() не propagate'ить `context`.** Production extractor у `src/prophet_checker/analysis/extractor.py` не оновлений у 19.8a (out of scope). Тому Task 1 script bypass'ить його і використовує `parse_extraction_response` напряму. Це OK для eval — production wiring (Task 20) potentially оновить extractor.

3. **Re-labeling — manual phase, не code.** Task 6 — interactive chat session. Implementer повинен зупинитись після Task 5 (decision verification) і escalate до human для inline labeling. Якщо implementer = subagent — він тільки готує `_partial_v2_labels.json` empty file (Step 2) і повертає DONE_WITH_CONCERNS з повідомленням "Ready for inline labeling, see Task 6 Step 3 workflow".

4. **Cost cap:** ~$0.52 total. Якщо Stage 2 (Opus judge) показує bills > $1 — investigate (можливо retry storms або throttle не працює).

5. **Скрипт reuse pattern:** `v2_extraction_run.py` impоrt'ить з `evaluate_detection.py` (PROVIDER_API_KEY_ENV, MIN_CALL_INTERVAL_SECONDS, CONCURRENCY_OVERRIDES). `v2_quality_eval.py` import'ить з `extraction_judge_prompts.py` (JUDGE_SYSTEM, build_judge_prompt, parse_judge_response) і `extraction_quality_eval.py` (aggregate_metrics). DRY дотриманий.
