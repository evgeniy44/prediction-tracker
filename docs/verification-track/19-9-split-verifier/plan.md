# Split Verifier (2-call) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Production verifier that scores each prediction with two LLM calls (verdict + assessment) and merges them into one result dict, hitting the validated firm-status 0.833 / strength 0.719 / value ~0.81 on Flash Lite.

**Architecture:** `Verifier.verify` builds one user prompt, fires two system prompts in parallel via `asyncio.gather` — a verdict prompt (clean V3: status/confidence/value + plain strength, discarded) and an assessment prompt (orthogonality + high=RARE strength). It takes status/confidence/value/evidence/dates from the verdict call and overrides `prediction_strength` with the assessment call. All-or-nothing: any parse/infra error propagates.

**Tech Stack:** Python 3.12, async/await, LiteLLM-backed `LLMClient`, pytest (`asyncio_mode=auto`).

**Spec:** `docs/verification-track/19-9-split-verifier/design.md` (commit `32aa4f0`).

**Working dir:** all commands assume `cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker` first (cwd drifts in this environment — always prefix it).

**Test baseline:** 181 passed. Final expected: 190 passed (+1 T1, +1 T2, +4 T3, +3 T4).

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `src/prophet_checker/llm/prompts.py` | Prompts + parsers | Revert `VERIFICATION_SYSTEM_V2` → V3; add `ASSESSMENT_SYSTEM_V2`, `get_assessment_system_v2`, `parse_assessment_response_v2` |
| `src/prophet_checker/analysis/verifier.py` | 2-call verification component | **Create** — `Verifier` class |
| `src/prophet_checker/analysis/__init__.py` | Package exports | Add `Verifier` |
| `tests/test_llm_prompts.py` | Prompt/parser tests | Add verdict-marker, assessment, parser tests |
| `tests/test_analysis_verifier.py` | Verifier tests | **Create** |

**Out of scope (do NOT touch):** Task 20 orchestrator, `scripts/verification_eval.py`, DB/domain (`Prediction` already has every field).

**Model guidance for subagents:** Task 1 HAIKU, Task 2 HAIKU, Task 3 HAIKU, Task 4 SONNET (async + merge + stub routing), Task 5 SONNET (run + interpret metrics).

---

### Task 1: Revert `VERIFICATION_SYSTEM_V2` to the clean V3 verdict prompt

The working tree currently holds the rejected V7 experiment (reasoning-first, "high = RARE", vagueness rule). Replace it with the clean V3 verdict prompt: plain strength ("concrete falsifiable"), elaborate value rubric, reasoning as output #5, no orthogonality block.

**Files:**
- Modify: `src/prophet_checker/llm/prompts.py` (the `VERIFICATION_SYSTEM_V2 = """..."""` block, currently around lines 118–221)
- Test: `tests/test_llm_prompts.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_llm_prompts.py`:

```python
def test_verdict_system_is_plain_v3():
    from prophet_checker.llm.prompts import get_verification_system_v2

    system = get_verification_system_v2(today="2026-05-23")
    assert "2026-05-23" in system
    assert "fact-checker" in system
    assert "concrete falsifiable claim with measurable outcome" in system
    assert "outcome reshapes a country, region, or balance of power" in system
    assert "high = RARE" not in system
    assert "VAGUENESS RULE" not in system
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker && .venv/bin/python -m pytest tests/test_llm_prompts.py::test_verdict_system_is_plain_v3 -v`
Expected: FAIL — current V7 lacks "concrete falsifiable claim with measurable outcome" and contains "high = RARE".

- [ ] **Step 3: Replace the `VERIFICATION_SYSTEM_V2` block**

Replace the entire `VERIFICATION_SYSTEM_V2 = """..."""` assignment in `src/prophet_checker/llm/prompts.py` with exactly:

```python
VERIFICATION_SYSTEM_V2 = """You are a fact-checker who verifies political/economic predictions about Ukraine
and global events. Today's date is {today}. The prediction was made on a past
date — your job is to assess whether it can be evaluated NOW, and if so, what
the verdict is.

Determine EIGHT outputs (all required in JSON response):

═══════════════════════════════════════════════════════════════════
1) status — exactly one of:

   "confirmed" — the predicted event happened as foretold. You have
                concrete evidence. The prediction's timeframe (target_date,
                or reasonable interpretation) has passed.

   "refuted"  — the predicted event did NOT happen, OR the opposite occurred.
                Concrete evidence required. Timeframe has passed.

   "unresolved" — the predicted event's timeframe has passed, but evidence is
                  ambiguous, the claim is too vague to falsify, or no public
                  record exists. Re-checking later WON'T help — this is a
                  permanent verdict.

   "premature" — the predicted event has not yet occurred but is still
                 POSSIBLE. The timeframe hasn't elapsed, OR the trigger
                 condition (for conditional predictions like "if X happens")
                 hasn't fired. We should retry verification later.

2) confidence — 0.0 to 1.0
   Your certainty in the verdict.

3) prediction_strength — assess the CLAIM ITSELF (independent of outcome):

   "high"   — concrete falsifiable claim with measurable outcome.
   "medium" — probabilistic but substantive claim with clear outcome.
   "low"    — vague hedge, possibility statement, or non-substantive forecast.

4) prediction_value — assess the IMPORTANCE/RESONANCE of the predicted outcome.
   Even in consequential topics (war, geopolitics), distinguish:

   "high"   — outcome reshapes a country, region, or balance of power.
              Examples: "війна закінчиться у 2026", "Україна стане
              федеральним округом", "Захід вступить у війну з РФ".
              NOT high: process announcements, logistical events,
              announcements of intent within an ongoing conflict.
   "medium" — affects a sector, region, institution, or specific subgroup;
              significant policy/military escalation but not regime-changing.
              Examples: "новий уряд буде сформований", "будуть нові санкції",
              "поставки зброї будуть розширені".
   "low"    — process/logistical/descriptive within a larger context;
              tautology; calendar-bound certainty; announcement of intent
              (not outcome); description of ongoing activity; vague slogan.
              Examples: "дипломати зустрінуться", "позиції політиків
              змінюватимуться залежно від подій", "сторони нарабатывают
              соглашения", "45 евакуаційних автобусів поїдуть з міста".

5) reasoning — 1-3 sentences
   Explain the verdict, strength, and value assessment.

6) evidence — concrete fact text or null
   REQUIRED when status=confirmed/refuted (verdict needs justification).
   May be null when status=premature/unresolved.
   Do NOT include URLs (you have no web access).

7) retry_after — YYYY-MM-DD or null
   REQUIRED when status=premature. Null for all other statuses.
   Heuristics: for conditional predictions today + 3-6 months;
   for target_date in future, use target_date itself;
   for vague open-ended, today + 6 months.

8) max_horizon — YYYY-MM-DD or null
   Latest reasonable date to keep checking this prediction.
   Set ONLY if status="premature" AND target_date is null. Otherwise null.
   Heuristics: conditional ~3 years; open-ended political ~5 years;
   "soon"/"coming months" → prediction_date + 1-2 years.

═══════════════════════════════════════════════════════════════════
MUTUAL EXCLUSION RULES (strictly enforce):
- status=confirmed/refuted → evidence MUST be a concrete fact, retry_after=null
- status=unresolved → retry_after=null (recheck won't help)
- status=premature → retry_after MUST be a date, evidence may be null
- max_horizon set ONLY when status=premature AND target_date=null

Respond ONLY with raw JSON, no markdown fences:

{{
  "status": "confirmed" | "refuted" | "unresolved" | "premature",
  "confidence": 0.0 to 1.0,
  "prediction_strength": "low" | "medium" | "high",
  "prediction_value": "low" | "medium" | "high",
  "reasoning": "1-3 sentences explaining the verdict, strength, and value",
  "evidence": "concrete fact text or null. Do NOT include URLs (you have no web access).",
  "retry_after": "YYYY-MM-DD or null",
  "max_horizon": "YYYY-MM-DD or null"
}}"""
```

- [ ] **Step 4: Run the new test + full suite**

Run: `cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker && .venv/bin/python -m pytest tests/test_llm_prompts.py::test_verdict_system_is_plain_v3 -v && .venv/bin/python -m pytest -q`
Expected: new test PASS; full suite **182 passed** (181 + 1).

- [ ] **Step 5: Commit**

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker
git add src/prophet_checker/llm/prompts.py tests/test_llm_prompts.py
git commit -m "$(cat <<'EOF'
refactor(llm): VERIFICATION_SYSTEM_V2 → чистий V3 verdict-промт

Відкат некомітнутого V7-експерименту до плаского V3 (concrete falsifiable
strength, value rubric, reasoning #5) — verdict-виклик split verifier'а.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Add `ASSESSMENT_SYSTEM_V2` + `get_assessment_system_v2`

The assessment prompt is the validated strength+value prompt (orthogonality block + high=RARE + reasoning-first). It outputs strength+value, but the verifier keeps only strength.

**Files:**
- Modify: `src/prophet_checker/llm/prompts.py` (add constant after `VERIFICATION_TEMPLATE_V2`; add builder near `get_verification_system_v2`)
- Test: `tests/test_llm_prompts.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_llm_prompts.py`:

```python
def test_get_assessment_system_v2_injects_today_and_markers():
    from prophet_checker.llm.prompts import get_assessment_system_v2

    system = get_assessment_system_v2(today="2026-05-23")
    assert "2026-05-23" in system
    assert "INDEPENDENT axes" in system
    assert "high\"   — RARE" in system or "RARE" in system
    assert "fact-checker" not in system
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker && .venv/bin/python -m pytest tests/test_llm_prompts.py::test_get_assessment_system_v2_injects_today_and_markers -v`
Expected: FAIL — `ImportError: cannot import name 'get_assessment_system_v2'`.

- [ ] **Step 3: Add the constant and builder**

In `src/prophet_checker/llm/prompts.py`, add this constant immediately after the `VERIFICATION_TEMPLATE_V2 = """..."""` block:

```python
ASSESSMENT_SYSTEM_V2 = """You assess two INDEPENDENT properties of a political/economic prediction about
Ukraine and global events. Today's date is {today}. You do NOT judge whether the
prediction came true — only how it is phrased and how much its outcome matters.

═══════════════════════════════════════════════════════════════════
prediction_strength and prediction_value are INDEPENDENT axes:
   - strength = HOW the claim is phrased (vague ↔ precise)
   - value    = HOW MUCH the outcome matters (trivial ↔ world-changing)
   A vague claim about war ending = strength:low + value:high.
   A precise claim about a diplomat's schedule = strength:high + value:low.

Determine THREE outputs (all required in JSON response):

1) reasoning — 1-3 sentences.
   State how the claim is phrased and how consequential its outcome is.

2) prediction_strength — HOW the claim is phrased (NOT how important):

   "high"   — RARE. Explicit numeric/dated threshold with a single measurable
              criterion (e.g., "X will reach Y by date Z").
   "medium" — probabilistic but substantive, with a clear checkable outcome.
   "low"    — vague hedge ("может", "возможно", "скорее всего", "практически"),
              possibility statement, open-ended trend, or non-substantive
              forecast. MOST political commentary is low.

3) prediction_value — HOW MUCH the predicted outcome matters. Even in
   consequential topics (war, geopolitics), distinguish:

   "high"   — outcome reshapes a country, region, or balance of power.
              Examples: "війна закінчиться у 2026", "Україна стане
              федеральним округом", "Захід вступить у війну з РФ".
              NOT high: process announcements, logistical events,
              announcements of intent within an ongoing conflict.
   "medium" — affects a sector, region, institution, or specific subgroup;
              significant policy/military escalation but not regime-changing.
              Examples: "новий уряд буде сформований", "будуть нові санкції",
              "поставки зброї будуть розширені".
   "low"    — process/logistical/descriptive within a larger context;
              tautology; calendar-bound certainty; announcement of intent
              (not outcome); description of ongoing activity; vague slogan.
              Examples: "дипломати зустрінуться", "позиції політиків
              змінюватимуться залежно від подій", "сторони нарабатывают
              соглашения", "45 евакуаційних автобусів поїдуть з міста".

Respond ONLY with raw JSON, no markdown fences:

{{
  "reasoning": "1-3 sentences",
  "prediction_strength": "low" | "medium" | "high",
  "prediction_value": "low" | "medium" | "high"
}}"""
```

Add this builder immediately after the existing `get_verification_system_v2` function:

```python
def get_assessment_system_v2(today: str) -> str:
    return ASSESSMENT_SYSTEM_V2.format(today=today)
```

- [ ] **Step 4: Run the new test + full suite**

Run: `cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker && .venv/bin/python -m pytest tests/test_llm_prompts.py::test_get_assessment_system_v2_injects_today_and_markers -v && .venv/bin/python -m pytest -q`
Expected: new test PASS; full suite **183 passed**.

- [ ] **Step 5: Commit**

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker
git add src/prophet_checker/llm/prompts.py tests/test_llm_prompts.py
git commit -m "$(cat <<'EOF'
feat(llm): ASSESSMENT_SYSTEM_V2 + get_assessment_system_v2

Валідований strength+value промт (orthogonality + high=RARE + reasoning-first)
для assessment-виклику split verifier'а.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Add `parse_assessment_response_v2`

Parses the assessment response and returns only `prediction_strength` (value/reasoning ignored). Mirrors `parse_verification_response_v2` style: `_strip_code_fence` + `json.loads`, required-field + enum checks, `ValueError` on violation.

**Files:**
- Modify: `src/prophet_checker/llm/prompts.py` (add function after `parse_verification_response_v2`)
- Test: `tests/test_llm_prompts.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_llm_prompts.py`:

```python
def test_parse_assessment_happy_path():
    from prophet_checker.llm.prompts import parse_assessment_response_v2

    raw = json.dumps({
        "reasoning": "Vague hedge.",
        "prediction_strength": "low",
        "prediction_value": "high",
    })
    result = parse_assessment_response_v2(raw)
    assert result == {"prediction_strength": "low"}


def test_parse_assessment_strips_code_fence():
    from prophet_checker.llm.prompts import parse_assessment_response_v2

    raw = '```json\n{"prediction_strength": "medium", "prediction_value": "low"}\n```'
    assert parse_assessment_response_v2(raw) == {"prediction_strength": "medium"}


def test_parse_assessment_raises_on_missing_strength():
    from prophet_checker.llm.prompts import parse_assessment_response_v2

    raw = json.dumps({"prediction_value": "high"})
    with pytest.raises(ValueError, match="missing required field: prediction_strength"):
        parse_assessment_response_v2(raw)


def test_parse_assessment_raises_on_invalid_strength():
    from prophet_checker.llm.prompts import parse_assessment_response_v2

    raw = json.dumps({"prediction_strength": "strong", "prediction_value": "high"})
    with pytest.raises(ValueError, match="invalid prediction_strength"):
        parse_assessment_response_v2(raw)
```

Note: `json` and `pytest` are already imported at the top of `tests/test_llm_prompts.py`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker && .venv/bin/python -m pytest tests/test_llm_prompts.py -k parse_assessment -v`
Expected: FAIL — `ImportError: cannot import name 'parse_assessment_response_v2'`.

- [ ] **Step 3: Implement the parser**

In `src/prophet_checker/llm/prompts.py`, add immediately after `parse_verification_response_v2`:

```python
def parse_assessment_response_v2(response: str) -> dict:
    data = json.loads(_strip_code_fence(response))

    if "prediction_strength" not in data:
        raise ValueError("missing required field: prediction_strength")

    if data["prediction_strength"] not in {"low", "medium", "high"}:
        raise ValueError(
            f"invalid prediction_strength: {data['prediction_strength']!r} "
            f"(expected low/medium/high)"
        )

    return {"prediction_strength": data["prediction_strength"]}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker && .venv/bin/python -m pytest tests/test_llm_prompts.py -k parse_assessment -v && .venv/bin/python -m pytest -q`
Expected: 4 new tests PASS; full suite **187 passed**.

- [ ] **Step 5: Commit**

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker
git add src/prophet_checker/llm/prompts.py tests/test_llm_prompts.py
git commit -m "$(cat <<'EOF'
feat(llm): parse_assessment_response_v2 — парсер strength з assessment-виклику

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: `Verifier` class + export

The verifier runs both calls in parallel, parses each, and overrides the verdict's strength with the assessment's strength. All-or-nothing — exceptions propagate to the caller.

**Files:**
- Create: `src/prophet_checker/analysis/verifier.py`
- Modify: `src/prophet_checker/analysis/__init__.py`
- Create: `tests/test_analysis_verifier.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_analysis_verifier.py`:

```python
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from prophet_checker.analysis.verifier import Verifier


def make_split_llm(verdict_raw: str, assessment_raw: str):
    llm = MagicMock()

    def route(prompt, system=None):
        return verdict_raw if "fact-checker" in (system or "") else assessment_raw

    llm.complete = AsyncMock(side_effect=route)
    return llm


VERDICT_JSON = json.dumps({
    "status": "confirmed",
    "confidence": 0.9,
    "prediction_strength": "low",
    "prediction_value": "high",
    "reasoning": "Event occurred as predicted.",
    "evidence": "It happened in June 2023.",
    "retry_after": None,
    "max_horizon": None,
})

ASSESSMENT_JSON = json.dumps({
    "reasoning": "Numeric dated threshold.",
    "prediction_strength": "medium",
    "prediction_value": "low",
})


async def test_verify_merges_verdict_with_assessment_strength():
    llm = make_split_llm(VERDICT_JSON, ASSESSMENT_JSON)
    verifier = Verifier(llm)

    result = await verifier.verify(
        claim="Контрнаступ почнеться влітку 2023",
        situation="Обговорення літньої кампанії",
        prediction_date="2023-01-15",
        target_date="2023-06-01",
        today="2026-05-23",
    )

    assert result["status"] == "confirmed"
    assert result["confidence"] == 0.9
    assert result["prediction_value"] == "high"
    assert result["evidence"] == "It happened in June 2023."
    assert result["prediction_strength"] == "medium"


async def test_verify_fires_both_system_prompts():
    llm = make_split_llm(VERDICT_JSON, ASSESSMENT_JSON)
    verifier = Verifier(llm)

    await verifier.verify(
        claim="c", situation="s", prediction_date="2023-01-15",
        target_date=None, today="2026-05-23",
    )

    systems = [call.kwargs["system"] for call in llm.complete.call_args_list]
    assert any("fact-checker" in s for s in systems)
    assert any("INDEPENDENT axes" in s for s in systems)


async def test_verify_raises_when_assessment_invalid():
    bad_assessment = json.dumps({"prediction_strength": "strong"})
    llm = make_split_llm(VERDICT_JSON, bad_assessment)
    verifier = Verifier(llm)

    with pytest.raises(ValueError, match="invalid prediction_strength"):
        await verifier.verify(
            claim="c", situation="s", prediction_date="2023-01-15",
            target_date=None, today="2026-05-23",
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker && .venv/bin/python -m pytest tests/test_analysis_verifier.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'prophet_checker.analysis.verifier'`.

- [ ] **Step 3: Create the `Verifier` class**

Create `src/prophet_checker/analysis/verifier.py`:

```python
from __future__ import annotations

import asyncio

from prophet_checker.llm.client import LLMClient
from prophet_checker.llm.prompts import (
    build_verification_prompt_v2,
    get_assessment_system_v2,
    get_verification_system_v2,
    parse_assessment_response_v2,
    parse_verification_response_v2,
)


class Verifier:
    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    async def verify(
        self,
        claim: str,
        situation: str,
        prediction_date: str,
        target_date: str | None,
        today: str,
    ) -> dict:
        user = build_verification_prompt_v2(
            claim=claim,
            prediction_date=prediction_date,
            target_date=target_date,
            today=today,
            situation=situation,
        )
        verdict_raw, assessment_raw = await asyncio.gather(
            self._llm.complete(user, system=get_verification_system_v2(today)),
            self._llm.complete(user, system=get_assessment_system_v2(today)),
        )
        verdict = parse_verification_response_v2(verdict_raw)
        assessment = parse_assessment_response_v2(assessment_raw)
        verdict["prediction_strength"] = assessment["prediction_strength"]
        return verdict
```

- [ ] **Step 4: Export `Verifier`**

Replace the contents of `src/prophet_checker/analysis/__init__.py` with:

```python
from prophet_checker.analysis.extractor import PredictionExtractor
from prophet_checker.analysis.verifier import Verifier

__all__ = ["PredictionExtractor", "Verifier"]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker && .venv/bin/python -m pytest tests/test_analysis_verifier.py -v && .venv/bin/python -m pytest -q`
Expected: 3 new tests PASS; full suite **190 passed**.

- [ ] **Step 6: Commit**

```bash
cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker
git add src/prophet_checker/analysis/verifier.py src/prophet_checker/analysis/__init__.py tests/test_analysis_verifier.py
git commit -m "$(cat <<'EOF'
feat(analysis): Verifier — 2-call split верифікація (verdict + assessment merge)

Паралельні виклики через asyncio.gather; status/confidence/value/evidence з
verdict-виклику, prediction_strength перевизначається з assessment-виклику.
All-or-nothing: parse/infra помилки пропагуються.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Confirming spot-test (manual smoke — no commit)

End-to-end check that the real `Verifier` against 32 gold claims lands in the validated range. Requires `GEMINI_API_KEY` in the environment. Costs ~$0.006, ~40s. If `GEMINI_API_KEY` is unavailable, report `DONE_WITH_CONCERNS` and defer this run to the user.

**Files:**
- Create: `/tmp/spot_check_split.py` (throwaway — NOT committed)

- [ ] **Step 1: Create the spot-test script**

Create `/tmp/spot_check_split.py`:

```python
import asyncio
import json
import os
import sys

sys.path.insert(0, "src")
from prophet_checker.analysis.verifier import Verifier
from prophet_checker.llm.client import LLMClient

GOLD = "scripts/data/verification_gold_labels.json"


async def main():
    gold = json.load(open(GOLD))
    today = gold["metadata"]["today"]
    entries = gold["predictions"]
    llm = LLMClient(provider="gemini", model="gemini-3.1-flash-lite-preview",
                    api_key=os.environ.get("GEMINI_API_KEY"), temperature=0.0)
    verifier = Verifier(llm)
    res = {}
    rejects = 0
    for i, e in enumerate(entries, 1):
        try:
            res[e["id"]] = await verifier.verify(
                claim=e["claim_text"], situation=e["situation"],
                prediction_date=e["prediction_date"], target_date=e["target_date"],
                today=today)
        except Exception as ex:
            rejects += 1
            res[e["id"]] = None
            print(f"  reject {e['id']}: {ex}")
        print(f"  {i}/{len(entries)}", flush=True)
    g = {p["id"]: p for p in entries}
    firm = [k for k in g if g[k]["expected_confidence"] > 0.55]
    fc = sum(1 for k in firm if res[k] and res[k]["status"] == g[k]["expected_status"])
    st = sum(1 for k in g if res[k] and res[k]["prediction_strength"] == g[k]["expected_strength"])
    va = sum(1 for k in g if res[k] and res[k]["prediction_value"] == g[k]["expected_value"])
    n = len(entries)
    print(f"\nrejects: {rejects}")
    print(f"firm-status {fc}/{len(firm)}={fc/len(firm):.3f}  "
          f"strength {st}/{n}={st/n:.3f}  value {va}/{n}={va/n:.3f}")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Run the spot-test**

Run: `cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker && .venv/bin/python /tmp/spot_check_split.py`
Expected (acceptance gate): `rejects ≤ 2`, `firm-status ≥ 0.80` (target 0.833), `strength ≥ 0.69` (target 0.719), `value ≥ 0.78` (target ~0.81).

- [ ] **Step 3: Interpret**

- If all gates pass → report DONE. The 2-call architecture is confirmed on production code.
- If `value` lands below 0.78 → the reconstructed verdict value rubric drifted from the lost original. Report DONE_WITH_CONCERNS with the actual numbers; do NOT block — a value-rubric tuning pass is a follow-up, not part of this task.
- If `firm-status < 0.80` or `strength < 0.69` → flag for review (prompt regression); report the per-field numbers.

No commit for this task (throwaway script).

---

## Final Verification

- [ ] **Run the full suite**

Run: `cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker && .venv/bin/python -m pytest -q`
Expected: **190 passed**.

- [ ] **Confirm git state**

Run: `cd /Users/evgenijberlog/Claude/Brain/Brain/prediction-tracker && git log --oneline -4 && git status --short`
Expected: 4 task commits (T1–T4); working tree clean except untracked `.DS_Store`/`.coverage`/`/tmp` artifacts.

- [ ] **Confirm scope discipline**

Verify these were NOT modified: `scripts/verification_eval.py`, any `alembic/`, `models/domain.py`, `models/db.py`. This task touches only `llm/prompts.py`, `analysis/verifier.py`, `analysis/__init__.py`, and the two test files.
