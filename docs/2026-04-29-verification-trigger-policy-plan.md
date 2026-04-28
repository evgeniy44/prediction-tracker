# Verification Trigger Policy — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Smart-Verifier-with-Dumb-Trigger architecture from spec — adds 4-status verifier (confirmed/refuted/unresolved/premature), prediction_strength, max_horizon, retry-loop semantics. No orchestration (deferred to Task 15).

**Architecture:** Verifier returns 7-field verdict in single LLM call. Trigger logic = trivial SQL filter (`verified_at IS NULL AND eligibility window`). Premature predictions loop with `next_check_at` until terminal verdict OR `max_horizon` expires (forced unresolved by housekeeping pass).

**Tech Stack:** Pydantic, SQLAlchemy 2.0 async, Alembic, pgvector, pytest-asyncio, LiteLLM, Claude Opus 4.6.

**Spec:** [`2026-04-26-verification-trigger-policy-design.md`](2026-04-26-verification-trigger-policy-design.md)

---

## File Structure

| File | Change | Responsibility |
|------|--------|----------------|
| `src/prophet_checker/models/domain.py` | Modify | Add `PredictionStrength` enum + 4 new `Prediction` fields |
| `src/prophet_checker/models/db.py` | Modify | Add 4 columns + index to `PredictionDB` |
| `src/prophet_checker/storage/interfaces.py` | Modify | Add 2 methods to `PredictionRepository` Protocol |
| `src/prophet_checker/storage/postgres.py` | Modify | Update mappers; implement 2 new methods on `PostgresPredictionRepository` |
| `src/prophet_checker/llm/prompts.py` | Modify | Add `VERIFICATION_SYSTEM_V2`, `VERIFICATION_TEMPLATE_V2`, `build_verification_prompt_v2`, `parse_verification_response_v2`, `VerificationResult` dataclass |
| `src/prophet_checker/analysis/verifier.py` | Modify | Add `verify_v2(prediction, today)` method with set-once semantics |
| `alembic/versions/2026_04_29_add_verification_metadata.py` | Create | Schema migration |
| `tests/test_models.py` | Modify | Add 3 domain tests |
| `tests/test_llm_prompts.py` | Modify | Add 16 prompt + parser tests |
| `tests/test_storage_postgres.py` | Modify | Extend round-trip test for new fields |
| `tests/test_storage_interfaces.py` | Modify | Add ~9 FakeRepo tests for trigger logic |
| `tests/test_analysis_verifier.py` | Modify | Add ~9 verifier_v2 tests |
| `scripts/empirical/verifier_v2_test.py` | Create | 10-claim manual validation re-run with v2 prompt |
| `scripts/outputs/extraction_eval/verifier_v2_test.json` | Create (output) | Empirical results, gitignored |

---

## Task 1: PredictionStrength enum + Prediction domain fields

**Files:**
- Modify: `src/prophet_checker/models/domain.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write failing test for `PredictionStrength` enum**

Add to `tests/test_models.py`:

```python
from prophet_checker.models.domain import PredictionStrength


def test_prediction_strength_enum_values():
    assert PredictionStrength.LOW.value == "low"
    assert PredictionStrength.MEDIUM.value == "medium"
    assert PredictionStrength.HIGH.value == "high"
```

- [ ] **Step 2: Run test, verify ImportError**

```bash
.venv/bin/python -m pytest tests/test_models.py::test_prediction_strength_enum_values -v
```

Expected: ImportError on `PredictionStrength`.

- [ ] **Step 3: Add `PredictionStrength` enum to `domain.py`**

In `src/prophet_checker/models/domain.py`, after `PredictionStatus` enum (line 17):

```python
class PredictionStrength(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
```

- [ ] **Step 4: Run test, verify pass**

```bash
.venv/bin/python -m pytest tests/test_models.py::test_prediction_strength_enum_values -v
```

Expected: 1 passed.

- [ ] **Step 5: Write failing tests for new `Prediction` fields**

Add to `tests/test_models.py`:

```python
from datetime import date


def test_prediction_new_fields_defaults():
    """4 new fields default to None / 0."""
    pred = Prediction(
        id="p1", document_id="d1", person_id="per1",
        claim_text="Test claim",
        prediction_date=date(2024, 1, 1),
    )
    assert pred.prediction_strength is None
    assert pred.max_horizon is None
    assert pred.next_check_at is None
    assert pred.verify_attempts == 0


def test_prediction_new_fields_serialize():
    """New fields round-trip through Pydantic."""
    pred = Prediction(
        id="p1", document_id="d1", person_id="per1",
        claim_text="Test claim",
        prediction_date=date(2024, 1, 1),
        prediction_strength=PredictionStrength.HIGH,
        max_horizon=date(2026, 1, 1),
        next_check_at=date(2025, 6, 1),
        verify_attempts=3,
    )
    dumped = pred.model_dump()
    assert dumped["prediction_strength"] == "high"
    assert dumped["max_horizon"] == date(2026, 1, 1)
    assert dumped["next_check_at"] == date(2025, 6, 1)
    assert dumped["verify_attempts"] == 3
```

- [ ] **Step 6: Run, verify both fail**

```bash
.venv/bin/python -m pytest tests/test_models.py::test_prediction_new_fields_defaults tests/test_models.py::test_prediction_new_fields_serialize -v
```

Expected: 2 failed (extra fields not allowed / unknown attribute).

- [ ] **Step 7: Add 4 fields to `Prediction` Pydantic model**

In `src/prophet_checker/models/domain.py`, modify `Prediction` class (line 54):

```python
class Prediction(BaseModel):
    id: str
    document_id: str
    person_id: str
    claim_text: str
    prediction_date: date
    target_date: date | None = None
    topic: str = ""
    status: PredictionStatus = PredictionStatus.UNRESOLVED
    confidence: float = 0.0
    evidence_url: str | None = None
    evidence_text: str | None = None
    verified_at: datetime | None = None
    embedding: list[float] | None = None
    # NEW for verification trigger policy (2026-04-29)
    prediction_strength: PredictionStrength | None = None
    max_horizon: date | None = None
    next_check_at: date | None = None
    verify_attempts: int = 0
```

- [ ] **Step 8: Run all tests in test_models.py, verify pass**

```bash
.venv/bin/python -m pytest tests/test_models.py -v
```

Expected: All passing (existing + 3 new).

- [ ] **Step 9: Commit**

```bash
git add src/prophet_checker/models/domain.py tests/test_models.py
git commit -m "feat(domain): add PredictionStrength enum + 4 fields on Prediction (Verifier v2)"
```

---

## Task 2: PredictionDB schema + mapper updates

**Files:**
- Modify: `src/prophet_checker/models/db.py`
- Modify: `src/prophet_checker/storage/postgres.py`
- Test: `tests/test_storage_postgres.py`

- [ ] **Step 1: Write failing test for round-trip with new fields**

Modify `tests/test_storage_postgres.py:test_prediction_round_trip` (around line 50):

```python
def test_prediction_round_trip():
    pred = Prediction(
        id="1", document_id="d1", person_id="p1",
        claim_text="Війна закінчиться у 2024",
        prediction_date=date(2023, 1, 1),
        target_date=date(2024, 12, 31),
        topic="війна",
        status=PredictionStatus.CONFIRMED,
        confidence=0.85,
        evidence_url="https://example.com",
        evidence_text="proof",
        # NEW
        prediction_strength=PredictionStrength.HIGH,
        max_horizon=date(2025, 6, 1),
        next_check_at=date(2024, 9, 1),
        verify_attempts=2,
    )
    db_obj = domain_to_prediction_db(pred)
    assert db_obj.prediction_strength == "high"
    assert db_obj.max_horizon == date(2025, 6, 1)
    assert db_obj.next_check_at == date(2024, 9, 1)
    assert db_obj.verify_attempts == 2
    
    back = prediction_db_to_domain(db_obj)
    assert back.prediction_strength == PredictionStrength.HIGH
    assert back.max_horizon == date(2025, 6, 1)
    assert back.next_check_at == date(2024, 9, 1)
    assert back.verify_attempts == 2
```

Also add import at top:
```python
from prophet_checker.models.domain import (
    Person, PersonSource, Prediction, PredictionStatus, PredictionStrength,
    RawDocument, SourceType,
)
```

- [ ] **Step 2: Run test, verify fail (TypeError on PredictionDB.__init__)**

```bash
.venv/bin/python -m pytest tests/test_storage_postgres.py::test_prediction_round_trip -v
```

Expected: TypeError or AttributeError on `prediction_strength` field on PredictionDB.

- [ ] **Step 3: Add columns + index to `PredictionDB`**

In `src/prophet_checker/models/db.py`, modify `PredictionDB` (line 66):

Add imports at top if missing:
```python
from sqlalchemy import (
    Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, func,
)
```

Add fields after `embedding` (line 81):
```python
    embedding = mapped_column(Vector(1536), nullable=True)
    # NEW for verification trigger policy (2026-04-29)
    prediction_strength: Mapped[str | None] = mapped_column(String(10), nullable=True)
    max_horizon: Mapped[date | None] = mapped_column(Date, nullable=True)
    next_check_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    verify_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    document: Mapped[RawDocumentDB] = relationship(back_populates="predictions")
    person: Mapped[PersonDB] = relationship(back_populates="predictions")

    __table_args__ = (
        Index(
            "idx_predictions_eligible",
            "verified_at", "next_check_at", "max_horizon",
        ),
    )
```

- [ ] **Step 4: Update `domain_to_prediction_db` and `prediction_db_to_domain` mappers**

In `src/prophet_checker/storage/postgres.py`, modify both functions (lines 59-78):

```python
def domain_to_prediction_db(pred: Prediction) -> PredictionDB:
    return PredictionDB(
        id=pred.id, document_id=pred.document_id, person_id=pred.person_id,
        claim_text=pred.claim_text, prediction_date=pred.prediction_date,
        target_date=pred.target_date, topic=pred.topic,
        status=pred.status.value, confidence=pred.confidence,
        evidence_url=pred.evidence_url, evidence_text=pred.evidence_text,
        verified_at=pred.verified_at, embedding=pred.embedding,
        prediction_strength=pred.prediction_strength.value if pred.prediction_strength else None,
        max_horizon=pred.max_horizon,
        next_check_at=pred.next_check_at,
        verify_attempts=pred.verify_attempts,
    )


def prediction_db_to_domain(db: PredictionDB) -> Prediction:
    return Prediction(
        id=db.id, document_id=db.document_id, person_id=db.person_id,
        claim_text=db.claim_text, prediction_date=db.prediction_date,
        target_date=db.target_date, topic=db.topic,
        status=PredictionStatus(db.status), confidence=db.confidence,
        evidence_url=db.evidence_url, evidence_text=db.evidence_text,
        verified_at=db.verified_at,
        prediction_strength=PredictionStrength(db.prediction_strength) if db.prediction_strength else None,
        max_horizon=db.max_horizon,
        next_check_at=db.next_check_at,
        verify_attempts=db.verify_attempts,
    )
```

Add import at top:
```python
from prophet_checker.models.domain import (
    Person, PersonSource, Prediction, PredictionStatus, PredictionStrength,
    RawDocument, SourceType,
)
```

- [ ] **Step 5: Run test, verify pass**

```bash
.venv/bin/python -m pytest tests/test_storage_postgres.py -v
```

Expected: All tests passing.

- [ ] **Step 6: Commit**

```bash
git add src/prophet_checker/models/db.py src/prophet_checker/storage/postgres.py tests/test_storage_postgres.py
git commit -m "feat(db): add 4 verification metadata columns + idx_predictions_eligible (Verifier v2)"
```

---

## Task 3: Alembic migration

**Files:**
- Create: `alembic/versions/2026_04_29_add_verification_metadata.py`

- [ ] **Step 1: Write the migration file**

Create `alembic/versions/2026_04_29_add_verification_metadata.py`:

```python
"""add verification metadata fields

Revision ID: 2026_04_29_verif
Revises:
Create Date: 2026-04-29

Adds 4 columns to predictions for verification trigger policy:
- prediction_strength VARCHAR(10) NULL — set once on first verification
- max_horizon DATE NULL — for premature predictions without target_date
- next_check_at DATE NULL — when to retry (premature only)
- verify_attempts INTEGER NOT NULL DEFAULT 0 — telemetry counter

Plus index for trigger query: WHERE verified_at IS NULL AND
  (next_check_at IS NULL OR next_check_at <= today) AND
  (max_horizon IS NULL OR max_horizon >= today)
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "2026_04_29_verif"
down_revision = None  # If a prior revision exists, set its ID here
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "predictions",
        sa.Column("prediction_strength", sa.String(length=10), nullable=True),
    )
    op.add_column(
        "predictions",
        sa.Column("max_horizon", sa.Date(), nullable=True),
    )
    op.add_column(
        "predictions",
        sa.Column("next_check_at", sa.Date(), nullable=True),
    )
    op.add_column(
        "predictions",
        sa.Column(
            "verify_attempts", sa.Integer(), nullable=False, server_default="0"
        ),
    )
    op.create_index(
        "idx_predictions_eligible",
        "predictions",
        ["verified_at", "next_check_at", "max_horizon"],
    )


def downgrade() -> None:
    op.drop_index("idx_predictions_eligible", table_name="predictions")
    op.drop_column("predictions", "verify_attempts")
    op.drop_column("predictions", "next_check_at")
    op.drop_column("predictions", "max_horizon")
    op.drop_column("predictions", "prediction_strength")
```

- [ ] **Step 2: Determine current head revision**

```bash
ls alembic/versions/*.py 2>/dev/null
```

Expected: empty (no prior migrations) — keep `down_revision = None`.

If files exist, open the latest one and use its `revision` value as `down_revision`.

- [ ] **Step 3: Verify migration parses (no syntax errors)**

```bash
.venv/bin/python -c "import importlib.util; s = importlib.util.spec_from_file_location('m', 'alembic/versions/2026_04_29_add_verification_metadata.py'); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); print(m.revision, '→ down:', m.down_revision)"
```

Expected: `2026_04_29_verif → down: None`.

- [ ] **Step 4: Commit**

```bash
git add alembic/versions/2026_04_29_add_verification_metadata.py
git commit -m "feat(db): alembic migration — add verification metadata columns"
```

---

## Task 4: VerificationResult dataclass + parse_verification_response_v2

**Files:**
- Modify: `src/prophet_checker/llm/prompts.py`
- Test: `tests/test_llm_prompts.py`

- [ ] **Step 1: Write 12 failing tests for parser v2**

Add to `tests/test_llm_prompts.py`:

```python
from datetime import date
from prophet_checker.llm.prompts import (
    VerificationResult,
    parse_verification_response_v2,
)


def test_parse_v2_full_premature():
    raw = '''{"status": "premature", "confidence": 0.95,
    "prediction_strength": "high",
    "reasoning": "Target date in 2035",
    "evidence": null,
    "retry_after": "2035-06-24",
    "max_horizon": null}'''
    result = parse_verification_response_v2(raw)
    assert result is not None
    assert result.status == "premature"
    assert result.confidence == 0.95
    assert result.prediction_strength == "high"
    assert result.retry_after == date(2035, 6, 24)
    assert result.max_horizon is None
    assert result.evidence is None


def test_parse_v2_full_terminal_confirmed():
    raw = '''{"status": "confirmed", "confidence": 0.85,
    "prediction_strength": "medium",
    "reasoning": "Event happened in late 2024",
    "evidence": "BBC report Nov 2024",
    "retry_after": null,
    "max_horizon": null}'''
    result = parse_verification_response_v2(raw)
    assert result.status == "confirmed"
    assert result.evidence == "BBC report Nov 2024"
    assert result.retry_after is None


def test_parse_v2_strips_markdown_fence():
    raw = '''```json
{"status": "refuted", "confidence": 0.9, "prediction_strength": "high",
"reasoning": "Did not happen", "evidence": "official statement",
"retry_after": null, "max_horizon": null}
```'''
    result = parse_verification_response_v2(raw)
    assert result.status == "refuted"


def test_parse_v2_handles_trailing_text():
    raw = '''{"status": "unresolved", "confidence": 0.5, "prediction_strength": "low",
"reasoning": "Vague claim", "evidence": null,
"retry_after": null, "max_horizon": null}

Note: this was difficult to assess.'''
    result = parse_verification_response_v2(raw)
    assert result.status == "unresolved"


def test_parse_v2_handles_leading_preamble():
    raw = '''Here is my verdict:
{"status": "confirmed", "confidence": 0.8, "prediction_strength": "high",
"reasoning": "Yes", "evidence": "fact",
"retry_after": null, "max_horizon": null}'''
    result = parse_verification_response_v2(raw)
    assert result.status == "confirmed"


def test_parse_v2_invalid_status_flags():
    raw = '''{"status": "MAYBE", "confidence": 0.5, "prediction_strength": "high",
"reasoning": "x", "evidence": null, "retry_after": null, "max_horizon": null}'''
    result = parse_verification_response_v2(raw)
    assert result.verdict_invalid is True


def test_parse_v2_invalid_strength_flags():
    raw = '''{"status": "confirmed", "confidence": 0.5, "prediction_strength": "huge",
"reasoning": "x", "evidence": "fact", "retry_after": null, "max_horizon": null}'''
    result = parse_verification_response_v2(raw)
    assert result.verdict_invalid is True


def test_parse_v2_mutual_exclusion_unresolved_drops_retry():
    """unresolved + retry_after → drops retry_after, sets verdict_invalid=False
    (a mild correction, not a full rejection)."""
    raw = '''{"status": "unresolved", "confidence": 0.5, "prediction_strength": "low",
"reasoning": "vague", "evidence": null,
"retry_after": "2026-10-01", "max_horizon": null}'''
    result = parse_verification_response_v2(raw)
    assert result.status == "unresolved"
    assert result.retry_after is None  # dropped


def test_parse_v2_mutual_exclusion_terminal_drops_horizon():
    """confirmed + max_horizon → drops max_horizon."""
    raw = '''{"status": "confirmed", "confidence": 0.9, "prediction_strength": "high",
"reasoning": "happened", "evidence": "fact",
"retry_after": null, "max_horizon": "2030-01-01"}'''
    result = parse_verification_response_v2(raw)
    assert result.max_horizon is None


def test_parse_v2_premature_without_retry_after_invalid():
    """premature MUST have retry_after."""
    raw = '''{"status": "premature", "confidence": 0.7, "prediction_strength": "medium",
"reasoning": "future", "evidence": null,
"retry_after": null, "max_horizon": "2030-01-01"}'''
    result = parse_verification_response_v2(raw)
    assert result.verdict_invalid is True


def test_parse_v2_malformed_json_returns_none():
    raw = "not json {}"
    result = parse_verification_response_v2(raw)
    assert result is None


def test_parse_v2_invalid_date_format():
    """Bad ISO date should not crash; flag as invalid."""
    raw = '''{"status": "premature", "confidence": 0.7, "prediction_strength": "high",
"reasoning": "later", "evidence": null,
"retry_after": "not-a-date", "max_horizon": null}'''
    result = parse_verification_response_v2(raw)
    assert result.verdict_invalid is True
```

- [ ] **Step 2: Run, verify all 12 fail**

```bash
.venv/bin/python -m pytest tests/test_llm_prompts.py -k "parse_v2" -v
```

Expected: 12 errors (ImportError or NameError on `VerificationResult` / `parse_verification_response_v2`).

- [ ] **Step 3: Implement `VerificationResult` dataclass + parser**

In `src/prophet_checker/llm/prompts.py`, add at the bottom:

```python
import re as _re
from dataclasses import dataclass, field
from datetime import date as _date

VALID_V2_STATUSES = ("confirmed", "refuted", "unresolved", "premature")
VALID_V2_STRENGTHS = ("low", "medium", "high")


@dataclass
class VerificationResult:
    """Parsed verifier-v2 output. Use `verdict_invalid=True` to detect
    enum violations or constraint failures."""
    status: str
    confidence: float
    prediction_strength: str | None
    reasoning: str
    evidence: str | None
    retry_after: _date | None
    max_horizon: _date | None
    verdict_invalid: bool = False


_V2_FENCE_RE = _re.compile(
    r"^\s*```(?:json|JSON)?\s*\n?(.*?)\n?\s*```\s*$",
    _re.DOTALL,
)


def _strip_v2_fence(text: str) -> str:
    m = _V2_FENCE_RE.match(text.strip())
    if m:
        return m.group(1).strip()
    return text.strip()


def _parse_iso_date(raw) -> _date | None:
    if raw is None:
        return None
    if not isinstance(raw, str):
        return None
    try:
        return _date.fromisoformat(raw)
    except (ValueError, TypeError):
        return None


def parse_verification_response_v2(response: str) -> VerificationResult | None:
    """Parse + validate v2 verifier output.

    Tolerates markdown fences, leading preamble, trailing text after JSON.
    Returns None on malformed JSON.
    Returns VerificationResult with verdict_invalid=True on enum/constraint
    violations (caller can decide how to handle).
    Mutual-exclusion drops invalid combinations (e.g. retry_after with
    status!=premature is set to None instead of failing the whole parse).
    """
    text = _strip_v2_fence(response)
    first_brace = text.find("{")
    if first_brace > 0:
        text = text[first_brace:]
    try:
        data, _ = _json.JSONDecoder().raw_decode(text)
    except (_json.JSONDecodeError, AttributeError, TypeError):
        return None

    status = data.get("status", "")
    strength = data.get("prediction_strength")
    raw_retry = data.get("retry_after")
    raw_horizon = data.get("max_horizon")

    retry_after = _parse_iso_date(raw_retry)
    max_horizon = _parse_iso_date(raw_horizon)

    invalid = False
    # Status enum check
    if status not in VALID_V2_STATUSES:
        invalid = True
    # Strength enum check (allowing None for backward compat)
    if strength is not None and strength not in VALID_V2_STRENGTHS:
        invalid = True
    # Date format check (raw fields existed but couldn't be parsed)
    if raw_retry is not None and retry_after is None:
        invalid = True
    if raw_horizon is not None and max_horizon is None:
        invalid = True
    # Mutual exclusion: premature MUST have retry_after
    if status == "premature" and retry_after is None:
        invalid = True
    # Mutual exclusion: non-premature should not have retry_after — drop silently
    if status in ("confirmed", "refuted", "unresolved") and retry_after is not None:
        retry_after = None
    # Mutual exclusion: non-premature should not have max_horizon — drop silently
    if status in ("confirmed", "refuted", "unresolved") and max_horizon is not None:
        max_horizon = None

    return VerificationResult(
        status=status,
        confidence=float(data.get("confidence", 0.0)),
        prediction_strength=strength,
        reasoning=data.get("reasoning", ""),
        evidence=data.get("evidence"),
        retry_after=retry_after,
        max_horizon=max_horizon,
        verdict_invalid=invalid,
    )
```

Add `import json as _json` at top of file (or reuse existing `import json`).

- [ ] **Step 4: Run, verify all 12 pass**

```bash
.venv/bin/python -m pytest tests/test_llm_prompts.py -k "parse_v2" -v
```

Expected: 12 passed.

- [ ] **Step 5: Commit**

```bash
git add src/prophet_checker/llm/prompts.py tests/test_llm_prompts.py
git commit -m "feat(llm): VerificationResult + parse_verification_response_v2 with mutual-exclusion validation"
```

---

## Task 5: VERIFICATION_SYSTEM_V2 + build_verification_prompt_v2

**Files:**
- Modify: `src/prophet_checker/llm/prompts.py`
- Test: `tests/test_llm_prompts.py`

- [ ] **Step 1: Write failing tests for prompt builder**

Add to `tests/test_llm_prompts.py`:

```python
from prophet_checker.llm.prompts import (
    VERIFICATION_SYSTEM_V2,
    VERIFICATION_TEMPLATE_V2,
    build_verification_prompt_v2,
    get_verification_system_v2,
)


def test_v2_system_prompt_contains_4_statuses():
    sys = get_verification_system_v2(today="2026-04-29")
    assert "confirmed" in sys
    assert "refuted" in sys
    assert "unresolved" in sys
    assert "premature" in sys


def test_v2_system_prompt_contains_strength_levels():
    sys = get_verification_system_v2(today="2026-04-29")
    assert "low" in sys
    assert "medium" in sys
    assert "high" in sys


def test_v2_system_prompt_injects_today():
    sys = get_verification_system_v2(today="2026-04-29")
    assert "2026-04-29" in sys


def test_v2_template_includes_post_excerpt():
    prompt = build_verification_prompt_v2(
        claim="Test claim",
        prediction_date="2024-01-01",
        target_date="2024-12-31",
        post_excerpt="full post text here",
        today="2026-04-29",
    )
    assert "Test claim" in prompt
    assert "2024-01-01" in prompt
    assert "2024-12-31" in prompt
    assert "full post text here" in prompt
    assert "2026-04-29" in prompt


def test_v2_template_target_date_null():
    prompt = build_verification_prompt_v2(
        claim="Test",
        prediction_date="2024-01-01",
        target_date=None,
        post_excerpt="text",
        today="2026-04-29",
    )
    assert "not specified" in prompt or "null" in prompt
```

- [ ] **Step 2: Run, verify all 5 fail**

```bash
.venv/bin/python -m pytest tests/test_llm_prompts.py -k "v2_system or v2_template" -v
```

Expected: 5 errors (NameError on `VERIFICATION_SYSTEM_V2` etc.).

- [ ] **Step 3: Add v2 system + template + builder**

In `src/prophet_checker/llm/prompts.py`, add (after the v1 verification prompt, before RAG):

```python
VERIFICATION_SYSTEM_V2 = """You are a fact-checker who verifies political/economic predictions about Ukraine and global events. Today's date is {today}. The prediction was made on a past date — your job is to assess whether it can be evaluated NOW, and if so, what the verdict is.

Determine FOUR outputs:

═══════════════════════════════════════════════════════════════════
1) STATUS — exactly one of:

   "confirmed" — the predicted event happened as foretold. You have concrete
                evidence. The prediction's timeframe (target_date, or
                reasonable interpretation) has passed.

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

═══════════════════════════════════════════════════════════════════
2) PREDICTION_STRENGTH — assess the CLAIM ITSELF (independent of outcome):

   "high"   — concrete falsifiable claim with measurable outcome.
              Example: "Trump will end the war by April 30, 2025"

   "medium" — probabilistic but substantive claim with clear outcome.
              Example: "There's a high probability Russia will mobilize
              500k more troops by 2026"

   "low"    — vague hedge, possibility statement, or non-substantive
              forecast. Example: "Armed clashes are possible in the Baltics"
              ("possible" is not a forecast — it's a risk description)

═══════════════════════════════════════════════════════════════════
3) MAX_HORIZON — latest reasonable date to keep checking this prediction.
   Set ONLY if status="premature" AND target_date is null. Otherwise null.

   Heuristics:
   • Conditional ("if X happens, then Y"): max_horizon = today + lifespan
     of condition X. E.g. political-power conditionals ~3 years.
   • Open-ended political ("Zelensky will lose power"): today + 5 years.
   • "Soon" / "in the coming weeks/months": prediction_date + 1-2 years.
   • Far-future explicit ("in 10 years"): use the implied date.

   If max_horizon < today already → don't set premature; pick terminal verdict.

═══════════════════════════════════════════════════════════════════
4) RETRY_AFTER — only when status="premature". When does it make sense to
   re-evaluate?

   • For conditional: today + 3-6 months (recheck if trigger fired).
   • For target_date in future: target_date itself.
   • For vague open-ended: today + 6 months.

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
  "reasoning": "1-3 sentences explaining the verdict and strength",
  "evidence": "concrete fact or URL, or null",
  "retry_after": "YYYY-MM-DD or null",
  "max_horizon": "YYYY-MM-DD or null"
}}"""


VERIFICATION_TEMPLATE_V2 = """Claim: "{claim}"
Made on: {prediction_date}
Expected by: {target_date}

Original post excerpt (for context):
---
{post_excerpt}
---

Today: {today}.

Provide your verdict per the rubric."""


def get_verification_system_v2(today: str) -> str:
    """Return v2 system prompt with today injected."""
    return VERIFICATION_SYSTEM_V2.format(today=today)


def build_verification_prompt_v2(
    claim: str,
    prediction_date: str,
    target_date: str | None,
    post_excerpt: str,
    today: str,
) -> str:
    """Build user-message prompt for verifier-v2."""
    return VERIFICATION_TEMPLATE_V2.format(
        claim=claim,
        prediction_date=prediction_date,
        target_date=target_date if target_date else "not specified",
        post_excerpt=post_excerpt,
        today=today,
    )
```

Note: the `{{` / `}}` are deliberately escaped braces so `.format()` on a parameterized template works. The `today` placeholder uses `{today}` (single braces) since it IS a format param.

Wait — there's a subtle issue. The system prompt has `{today}` which is the single placeholder we want to format, but ALSO `{{ ... }}` for the JSON example which we want to keep as literal `{ ... }` after formatting.

Standard Python `.format()` handles this correctly: `{{` → `{`, `}}` → `}`, `{today}` → value of today.

- [ ] **Step 4: Run, verify all 5 pass**

```bash
.venv/bin/python -m pytest tests/test_llm_prompts.py -k "v2_system or v2_template" -v
```

Expected: 5 passed.

- [ ] **Step 5: Run all prompt tests, verify 17 pass total (12 + 5)**

```bash
.venv/bin/python -m pytest tests/test_llm_prompts.py -v
```

Expected: All passing.

- [ ] **Step 6: Commit**

```bash
git add src/prophet_checker/llm/prompts.py tests/test_llm_prompts.py
git commit -m "feat(llm): VERIFICATION_SYSTEM_V2 + build_verification_prompt_v2 (4-status + strength + horizon)"
```

---

## Task 6: PredictionRepository protocol changes

**Files:**
- Modify: `src/prophet_checker/storage/interfaces.py`
- Test: `tests/test_storage_interfaces.py`

- [ ] **Step 1: Write failing tests for new repo methods (FakeRepo style)**

Add to `tests/test_storage_interfaces.py`. First, find the `FakePredictionRepo` class (or wherever Prediction repo fakes live). Extend it:

```python
from datetime import date as _date


class FakePredictionRepoV2:
    """Fake repo for testing v2 trigger logic via in-memory filtering."""
    def __init__(self):
        self._preds: dict[str, Prediction] = {}

    async def save(self, prediction: Prediction) -> Prediction:
        self._preds[prediction.id] = prediction
        return prediction

    async def get_by_person(self, person_id, status=None):
        return [p for p in self._preds.values() if p.person_id == person_id]

    async def get_unverified(self):
        return [p for p in self._preds.values() if p.verified_at is None]

    async def update(self, prediction):
        self._preds[prediction.id] = prediction
        return prediction

    async def get_eligible_for_verification(
        self, today: _date, limit: int = 100
    ) -> list[Prediction]:
        eligible = []
        for p in self._preds.values():
            if p.verified_at is not None:
                continue
            if p.next_check_at is not None and p.next_check_at > today:
                continue
            if p.max_horizon is not None and p.max_horizon < today:
                continue
            eligible.append(p)
        return eligible[:limit]

    async def force_unresolved_past_horizon(self, today: _date) -> int:
        count = 0
        for p in self._preds.values():
            if p.verified_at is not None:
                continue
            if p.max_horizon is None or p.max_horizon >= today:
                continue
            p.status = PredictionStatus.UNRESOLVED
            p.verified_at = datetime.combine(today, datetime.min.time())
            p.evidence_text = "exceeded max_horizon"
            count += 1
        return count


def _make_pred(pid, **kwargs) -> Prediction:
    defaults = dict(
        id=pid, document_id="d", person_id="per",
        claim_text="x", prediction_date=date(2024, 1, 1),
    )
    defaults.update(kwargs)
    return Prediction(**defaults)


async def test_get_eligible_excludes_verified():
    repo = FakePredictionRepoV2()
    pending = _make_pred("p1")
    verified = _make_pred("p2", verified_at=datetime(2025, 1, 1))
    await repo.save(pending)
    await repo.save(verified)
    result = await repo.get_eligible_for_verification(today=date(2026, 4, 29))
    assert {p.id for p in result} == {"p1"}


async def test_get_eligible_excludes_future_next_check():
    repo = FakePredictionRepoV2()
    later = _make_pred("p1", next_check_at=date(2027, 1, 1))
    now = _make_pred("p2", next_check_at=date(2026, 4, 1))
    await repo.save(later)
    await repo.save(now)
    result = await repo.get_eligible_for_verification(today=date(2026, 4, 29))
    assert {p.id for p in result} == {"p2"}


async def test_get_eligible_excludes_past_max_horizon():
    repo = FakePredictionRepoV2()
    expired = _make_pred("p1", max_horizon=date(2025, 1, 1))
    fresh = _make_pred("p2", max_horizon=date(2027, 1, 1))
    await repo.save(expired)
    await repo.save(fresh)
    result = await repo.get_eligible_for_verification(today=date(2026, 4, 29))
    assert {p.id for p in result} == {"p2"}


async def test_get_eligible_includes_when_horizon_equals_today():
    repo = FakePredictionRepoV2()
    on_horizon = _make_pred("p1", max_horizon=date(2026, 4, 29))
    await repo.save(on_horizon)
    result = await repo.get_eligible_for_verification(today=date(2026, 4, 29))
    assert {p.id for p in result} == {"p1"}


async def test_get_eligible_includes_when_check_equals_today():
    repo = FakePredictionRepoV2()
    on_check = _make_pred("p1", next_check_at=date(2026, 4, 29))
    await repo.save(on_check)
    result = await repo.get_eligible_for_verification(today=date(2026, 4, 29))
    assert {p.id for p in result} == {"p1"}


async def test_get_eligible_respects_limit():
    repo = FakePredictionRepoV2()
    for i in range(10):
        await repo.save(_make_pred(f"p{i}"))
    result = await repo.get_eligible_for_verification(today=date(2026, 4, 29), limit=3)
    assert len(result) == 3


async def test_force_unresolved_updates_correctly():
    repo = FakePredictionRepoV2()
    expired = _make_pred(
        "p1", max_horizon=date(2025, 1, 1),
        status=PredictionStatus.UNRESOLVED,
    )
    fresh = _make_pred("p2", max_horizon=date(2027, 1, 1))
    await repo.save(expired)
    await repo.save(fresh)
    n = await repo.force_unresolved_past_horizon(today=date(2026, 4, 29))
    assert n == 1
    updated = await repo.get_by_person("per")
    expired_after = next(p for p in updated if p.id == "p1")
    assert expired_after.status == PredictionStatus.UNRESOLVED
    assert expired_after.verified_at is not None
    assert expired_after.evidence_text == "exceeded max_horizon"


async def test_force_unresolved_returns_count():
    repo = FakePredictionRepoV2()
    for i in range(5):
        await repo.save(_make_pred(f"p{i}", max_horizon=date(2025, 1, 1)))
    n = await repo.force_unresolved_past_horizon(today=date(2026, 4, 29))
    assert n == 5


async def test_force_unresolved_skips_already_verified():
    repo = FakePredictionRepoV2()
    already = _make_pred(
        "p1", max_horizon=date(2025, 1, 1),
        verified_at=datetime(2025, 6, 1),
    )
    await repo.save(already)
    n = await repo.force_unresolved_past_horizon(today=date(2026, 4, 29))
    assert n == 0
```

Add imports if missing: `from datetime import datetime`, plus `pytest` mark for asyncio:

```python
import pytest
pytestmark = pytest.mark.asyncio
```

If async tests aren't auto-detected by pytest-asyncio, configure `pytest.ini` or use explicit marker on each test.

- [ ] **Step 2: Run, verify all 9 fail**

```bash
.venv/bin/python -m pytest tests/test_storage_interfaces.py -k "eligible or force_unresolved" -v
```

Expected: 9 failed (`get_eligible_for_verification`/`force_unresolved_past_horizon` not in Protocol — but FakeRepo defines them so tests run; tests pass at this stage actually, since FakeRepo has the methods).

Wait — FakeRepo implements the methods directly, so tests will pass. The Protocol change is to formalize the contract. Let's add a Protocol-conformance check:

Add at top of test file:

```python
def test_fake_repo_v2_satisfies_protocol():
    repo: PredictionRepository = FakePredictionRepoV2()
    assert hasattr(repo, "get_eligible_for_verification")
    assert hasattr(repo, "force_unresolved_past_horizon")
```

This will fail because Protocol does not yet declare these methods.

- [ ] **Step 3: Add methods to `PredictionRepository` Protocol**

In `src/prophet_checker/storage/interfaces.py`, modify `PredictionRepository` (line 35):

```python
from datetime import date  # at top, if not already


class PredictionRepository(Protocol):
    async def save(self, prediction: Prediction) -> Prediction: ...
    async def get_by_person(
        self, person_id: str, status: PredictionStatus | None = None
    ) -> list[Prediction]: ...
    async def get_unverified(self) -> list[Prediction]: ...  # DEPRECATED — kept for backward compat
    async def update(self, prediction: Prediction) -> Prediction: ...
    
    # NEW for verification trigger policy (2026-04-29)
    async def get_eligible_for_verification(
        self, today: date, limit: int = 100
    ) -> list[Prediction]: ...
    async def force_unresolved_past_horizon(self, today: date) -> int: ...
```

- [ ] **Step 4: Run all storage interface tests, verify pass**

```bash
.venv/bin/python -m pytest tests/test_storage_interfaces.py -v
```

Expected: All 9+ new tests passing, plus existing tests still passing.

- [ ] **Step 5: Commit**

```bash
git add src/prophet_checker/storage/interfaces.py tests/test_storage_interfaces.py
git commit -m "feat(storage): PredictionRepository protocol + 9 trigger-logic tests via FakeRepo"
```

---

## Task 7: PostgresPredictionRepository — implement new SQL methods

**Files:**
- Modify: `src/prophet_checker/storage/postgres.py`

- [ ] **Step 1: Implement methods**

In `src/prophet_checker/storage/postgres.py`, modify `PostgresPredictionRepository` (line 159):

```python
from datetime import date, datetime  # at top
from sqlalchemy import or_, update  # add update to existing import


class PostgresPredictionRepository:
    # ... existing __init__, save, get_by_person, get_unverified, update ...

    async def get_eligible_for_verification(
        self, today: date, limit: int = 100
    ) -> list[Prediction]:
        """Predictions ready for verification:
        verified_at IS NULL
        AND (next_check_at IS NULL OR next_check_at <= today)
        AND (max_horizon IS NULL OR max_horizon >= today)
        """
        async with self._session_factory() as session:
            stmt = (
                select(PredictionDB)
                .where(
                    PredictionDB.verified_at.is_(None),
                    or_(
                        PredictionDB.next_check_at.is_(None),
                        PredictionDB.next_check_at <= today,
                    ),
                    or_(
                        PredictionDB.max_horizon.is_(None),
                        PredictionDB.max_horizon >= today,
                    ),
                )
                .limit(limit)
            )
            result = await session.execute(stmt)
            return [prediction_db_to_domain(row) for row in result.scalars().all()]

    async def force_unresolved_past_horizon(self, today: date) -> int:
        """Bulk-finalize predictions that exceeded max_horizon.
        Returns count of updated rows."""
        async with self._session_factory() as session:
            stmt = (
                update(PredictionDB)
                .where(
                    PredictionDB.verified_at.is_(None),
                    PredictionDB.max_horizon.isnot(None),
                    PredictionDB.max_horizon < today,
                )
                .values(
                    status=PredictionStatus.UNRESOLVED.value,
                    verified_at=datetime.combine(today, datetime.min.time()),
                    evidence_text="exceeded max_horizon",
                )
            )
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount or 0
```

Also update the `update()` method to include new fields:

```python
    async def update(self, prediction: Prediction) -> Prediction:
        async with self._session_factory() as session:
            db_obj = await session.get(PredictionDB, prediction.id)
            if db_obj:
                db_obj.status = prediction.status.value
                db_obj.confidence = prediction.confidence
                db_obj.evidence_url = prediction.evidence_url
                db_obj.evidence_text = prediction.evidence_text
                db_obj.verified_at = prediction.verified_at
                # NEW for verification trigger policy
                db_obj.prediction_strength = (
                    prediction.prediction_strength.value
                    if prediction.prediction_strength else None
                )
                db_obj.max_horizon = prediction.max_horizon
                db_obj.next_check_at = prediction.next_check_at
                db_obj.verify_attempts = prediction.verify_attempts
                await session.commit()
            return prediction
```

- [ ] **Step 2: Verify imports compile (smoke test via Python import)**

```bash
.venv/bin/python -c "from prophet_checker.storage.postgres import PostgresPredictionRepository; print('OK')"
```

Expected: `OK`.

- [ ] **Step 3: Run all storage tests**

```bash
.venv/bin/python -m pytest tests/test_storage_postgres.py tests/test_storage_interfaces.py -v
```

Expected: All passing.

- [ ] **Step 4: Commit**

```bash
git add src/prophet_checker/storage/postgres.py
git commit -m "feat(storage): PostgresPredictionRepository implements get_eligible_for_verification + force_unresolved_past_horizon"
```

---

## Task 8: PredictionVerifier.verify_v2

**Files:**
- Modify: `src/prophet_checker/analysis/verifier.py`
- Test: `tests/test_analysis_verifier.py`

- [ ] **Step 1: Write 9 failing tests for verifier_v2**

Add to `tests/test_analysis_verifier.py`:

```python
import json
import pytest
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock

from prophet_checker.analysis.verifier import PredictionVerifier
from prophet_checker.models.domain import (
    Prediction, PredictionStatus, PredictionStrength,
)


def _make_pred(**kwargs):
    defaults = dict(
        id="p1", document_id="d1", person_id="per1",
        claim_text="Test claim",
        prediction_date=date(2024, 1, 1),
    )
    defaults.update(kwargs)
    return Prediction(**defaults)


def _make_llm_v2(response: str) -> MagicMock:
    llm = MagicMock()
    llm.complete = AsyncMock(return_value=response)
    return llm


def _v2_resp(**kwargs) -> str:
    """Build a v2 verifier response JSON."""
    defaults = {
        "status": "confirmed",
        "confidence": 0.9,
        "prediction_strength": "high",
        "reasoning": "Event happened",
        "evidence": "BBC report",
        "retry_after": None,
        "max_horizon": None,
    }
    defaults.update(kwargs)
    return json.dumps(defaults)


pytestmark = pytest.mark.asyncio


async def test_verifier_v2_returns_terminal_confirmed():
    llm = _make_llm_v2(_v2_resp(status="confirmed", confidence=0.9))
    verifier = PredictionVerifier(llm_client=llm)
    pred = _make_pred()
    result = await verifier.verify_v2(pred, today=date(2026, 4, 29))
    assert result.status == PredictionStatus.CONFIRMED
    assert result.confidence == 0.9
    assert result.verified_at is not None
    assert result.next_check_at is None


async def test_verifier_v2_returns_premature_with_retry_after():
    llm = _make_llm_v2(_v2_resp(
        status="premature", confidence=0.85,
        retry_after="2026-12-01", max_horizon="2030-01-01",
    ))
    verifier = PredictionVerifier(llm_client=llm)
    pred = _make_pred()
    result = await verifier.verify_v2(pred, today=date(2026, 4, 29))
    assert result.status == PredictionStatus.UNRESOLVED  # premature persisted as UNRESOLVED+next_check_at
    assert result.verified_at is None  # still in queue
    assert result.next_check_at == date(2026, 12, 1)
    assert result.max_horizon == date(2030, 1, 1)


async def test_verifier_v2_calls_llm_with_today_in_prompt():
    llm = _make_llm_v2(_v2_resp())
    verifier = PredictionVerifier(llm_client=llm)
    pred = _make_pred()
    await verifier.verify_v2(pred, today=date(2026, 4, 29))
    # Inspect the call args
    sys_arg = llm.complete.call_args.kwargs.get("system") or llm.complete.call_args.args[1]
    assert "2026-04-29" in sys_arg


async def test_verifier_v2_set_once_strength_preserved():
    """If prediction already has prediction_strength, verify_v2 doesn't overwrite."""
    llm = _make_llm_v2(_v2_resp(prediction_strength="low"))
    verifier = PredictionVerifier(llm_client=llm)
    pred = _make_pred(prediction_strength=PredictionStrength.HIGH)
    result = await verifier.verify_v2(pred, today=date(2026, 4, 29))
    assert result.prediction_strength == PredictionStrength.HIGH  # unchanged


async def test_verifier_v2_set_once_max_horizon_preserved():
    """If prediction already has max_horizon, verify_v2 doesn't overwrite."""
    llm = _make_llm_v2(_v2_resp(
        status="premature", retry_after="2026-12-01",
        max_horizon="2030-01-01",
    ))
    verifier = PredictionVerifier(llm_client=llm)
    pred = _make_pred(max_horizon=date(2028, 1, 1))
    result = await verifier.verify_v2(pred, today=date(2026, 4, 29))
    assert result.max_horizon == date(2028, 1, 1)  # unchanged


async def test_verifier_v2_increments_attempts():
    llm = _make_llm_v2(_v2_resp())
    verifier = PredictionVerifier(llm_client=llm)
    pred = _make_pred(verify_attempts=2)
    result = await verifier.verify_v2(pred, today=date(2026, 4, 29))
    assert result.verify_attempts == 3


async def test_verifier_v2_llm_failure_no_status_change():
    """LLM exception → status untouched, attempts++, verified_at stays NULL."""
    llm = MagicMock()
    llm.complete = AsyncMock(side_effect=RuntimeError("LLM down"))
    verifier = PredictionVerifier(llm_client=llm)
    pred = _make_pred(status=PredictionStatus.UNRESOLVED, verify_attempts=0)
    result = await verifier.verify_v2(pred, today=date(2026, 4, 29))
    assert result.status == PredictionStatus.UNRESOLVED
    assert result.verified_at is None
    assert result.verify_attempts == 1


async def test_verifier_v2_parse_error_no_status_change():
    """Malformed response → status untouched, attempts++."""
    llm = _make_llm_v2("not valid json {{}")
    verifier = PredictionVerifier(llm_client=llm)
    pred = _make_pred(verify_attempts=0)
    result = await verifier.verify_v2(pred, today=date(2026, 4, 29))
    assert result.verified_at is None
    assert result.verify_attempts == 1


async def test_verifier_v2_premature_keeps_status_unresolved_no_verified_at():
    """Premature: status stays UNRESOLVED, next_check_at set, verified_at NULL."""
    llm = _make_llm_v2(_v2_resp(
        status="premature", retry_after="2026-12-01",
    ))
    verifier = PredictionVerifier(llm_client=llm)
    pred = _make_pred()
    result = await verifier.verify_v2(pred, today=date(2026, 4, 29))
    assert result.status == PredictionStatus.UNRESOLVED
    assert result.verified_at is None
    assert result.next_check_at == date(2026, 12, 1)
```

- [ ] **Step 2: Run, verify all 9 fail**

```bash
.venv/bin/python -m pytest tests/test_analysis_verifier.py -k "verifier_v2" -v
```

Expected: 9 errors (verify_v2 method does not exist).

- [ ] **Step 3: Implement `verify_v2` method**

In `src/prophet_checker/analysis/verifier.py`, add:

```python
from datetime import UTC, date, datetime

from prophet_checker.llm.prompts import (
    build_verification_prompt,
    build_verification_prompt_v2,
    get_verification_system,
    get_verification_system_v2,
    parse_verification_response,
    parse_verification_response_v2,
)
from prophet_checker.models.domain import (
    Prediction, PredictionStatus, PredictionStrength,
)


class PredictionVerifier:
    """Verifies a Prediction against known events using an LLM.

    Two API versions:
    - verify(prediction): legacy 3-status verdict (DEPRECATED)
    - verify_v2(prediction, today): 4-status + strength + horizon (preferred)
    """

    def __init__(self, llm_client, confidence_threshold: float = 0.6) -> None:
        self._llm = llm_client
        self._confidence_threshold = confidence_threshold

    # ... existing verify() method ...

    async def verify_v2(
        self,
        prediction: Prediction,
        today: date,
        post_excerpt: str = "",
    ) -> Prediction:
        """v2 verifier — 4-status with set-once metadata.

        Args:
            prediction: claim to verify (mutated and returned)
            today: reference date for trigger logic
            post_excerpt: original post text (optional, helps with conditional/context)

        Returns:
            Same prediction object with updated fields:
            - verify_attempts: ALWAYS incremented (+1)
            - prediction_strength: set ONLY if previously None
            - max_horizon: set ONLY if previously None and verifier returned one
            - For terminal status (confirmed/refuted/unresolved):
                status, confidence, evidence_url, evidence_text, verified_at
            - For premature status:
                next_check_at = retry_after; verified_at stays None
            - On LLM/parse error: only verify_attempts incremented
        """
        prediction.verify_attempts += 1

        prompt = build_verification_prompt_v2(
            claim=prediction.claim_text,
            prediction_date=prediction.prediction_date.isoformat(),
            target_date=(
                prediction.target_date.isoformat() if prediction.target_date else None
            ),
            post_excerpt=post_excerpt,
            today=today.isoformat(),
        )
        sys_prompt = get_verification_system_v2(today=today.isoformat())

        try:
            response = await self._llm.complete(prompt, system=sys_prompt)
        except Exception:
            logger.exception(
                "LLM call failed for verify_v2 prediction %s", prediction.id
            )
            return prediction

        result = parse_verification_response_v2(response)
        if result is None or result.verdict_invalid:
            logger.warning(
                "Verifier v2 invalid response for %s: %s",
                prediction.id, response[:200],
            )
            return prediction

        # Set-once metadata
        if prediction.prediction_strength is None and result.prediction_strength:
            try:
                prediction.prediction_strength = PredictionStrength(
                    result.prediction_strength
                )
            except ValueError:
                pass  # invalid strength was caught by parse, defensive
        if prediction.max_horizon is None and result.max_horizon:
            prediction.max_horizon = result.max_horizon

        if result.status == "premature":
            # In-flight: keep status, set next_check_at; verified_at stays NULL
            prediction.next_check_at = result.retry_after
            return prediction

        # Terminal: confirmed / refuted / unresolved
        try:
            prediction.status = PredictionStatus(result.status)
        except ValueError:
            prediction.status = PredictionStatus.UNRESOLVED
        prediction.confidence = result.confidence
        prediction.evidence_text = result.evidence
        prediction.evidence_url = None  # v2 doesn't separate URL field
        prediction.verified_at = datetime.combine(today, datetime.min.time(), UTC)
        prediction.next_check_at = None
        return prediction
```

- [ ] **Step 4: Run verifier_v2 tests, verify pass**

```bash
.venv/bin/python -m pytest tests/test_analysis_verifier.py -k "verifier_v2" -v
```

Expected: 9 passed.

- [ ] **Step 5: Run full test suite, verify no regressions**

```bash
.venv/bin/python -m pytest tests/ -v
```

Expected: All previously-passing tests still pass + 30+ new tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/prophet_checker/analysis/verifier.py tests/test_analysis_verifier.py
git commit -m "feat(verifier): add verify_v2 with 4-status + set-once strength/horizon (Verifier v2)"
```

---

## Task 9: Empirical re-run on 10 claims with v2 prompt

**Files:**
- Create: `scripts/empirical/verifier_v2_test.py`
- Output: `scripts/outputs/extraction_eval/verifier_v2_test.json` (gitignored)

- [ ] **Step 1: Create empirical script**

Create directory and file:

```bash
mkdir -p scripts/empirical
```

Create `scripts/empirical/verifier_v2_test.py`:

```python
"""Empirical validation of v2 verifier prompt on same 10 random claims
used in v1 baseline (scripts/outputs/extraction_eval/verifier_4status_test.json).

Compares: status distribution, prediction_strength assignment, max_horizon
plausibility, mutual-exclusion compliance.
"""
import asyncio
import json
import random
from datetime import date
from pathlib import Path

import litellm
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent.parent  # prediction-tracker root
load_dotenv(ROOT / ".env", override=True)
litellm.drop_params = True

import sys
sys.path.insert(0, str(ROOT / "src"))

from prophet_checker.llm.prompts import (
    build_verification_prompt_v2,
    get_verification_system_v2,
    parse_verification_response_v2,
)


random.seed(42)
ext = json.load(open(ROOT / "scripts/outputs/extraction_eval/extraction_outputs.json"))
posts = json.load(open(ROOT / "scripts/data/sample_posts.json"))
posts_by_id = {p["id"]: p for p in posts}

flash = ext["extractions"]["gemini/gemini-3.1-flash-lite-preview"]
all_claims = []
for pid, claims in flash.items():
    for c in claims:
        all_claims.append({"post_id": pid, **c})

sample = random.sample(all_claims, 10)
TODAY = "2026-04-29"


async def verify_one(idx: int, claim: dict) -> dict:
    post = posts_by_id[claim["post_id"]]
    excerpt = post["text"][:500].replace("\n", " ").strip()

    prompt = build_verification_prompt_v2(
        claim=claim["claim_text"],
        prediction_date=claim.get("prediction_date") or "unknown",
        target_date=claim.get("target_date"),
        post_excerpt=excerpt,
        today=TODAY,
    )
    sys_prompt = get_verification_system_v2(today=TODAY)

    try:
        resp = await litellm.acompletion(
            model="anthropic/claude-opus-4-6",
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            max_tokens=2000,
            num_retries=0,
        )
        raw = resp.choices[0].message.content
        parsed = parse_verification_response_v2(raw)
        if parsed is None:
            return {"idx": idx, "claim": claim, "raw": raw, "error": "parse_failure"}
        result = {
            "idx": idx,
            "claim": claim,
            "verdict": {
                "status": parsed.status,
                "confidence": parsed.confidence,
                "prediction_strength": parsed.prediction_strength,
                "reasoning": parsed.reasoning,
                "evidence": parsed.evidence,
                "retry_after": parsed.retry_after.isoformat() if parsed.retry_after else None,
                "max_horizon": parsed.max_horizon.isoformat() if parsed.max_horizon else None,
                "verdict_invalid": parsed.verdict_invalid,
            },
        }
    except Exception as e:
        result = {"idx": idx, "claim": claim, "error": f"{type(e).__name__}: {e}"}

    icons = {"confirmed": "✅", "refuted": "❌", "unresolved": "❓", "premature": "⏳"}
    if "verdict" in result:
        v = result["verdict"]
        icon = icons.get(v["status"], "?")
        flag = " 🚨INVALID" if v["verdict_invalid"] else ""
        print(
            f"\n#{idx} [{claim['post_id']}] {icon} {v['status']} "
            f"strength={v['prediction_strength']} conf={v['confidence']}{flag}"
        )
        print(f"   claim: {claim['claim_text'][:140]}")
        print(f"   reasoning: {v['reasoning'][:200]}")
        if v["retry_after"]:
            print(f"   retry_after: {v['retry_after']}")
        if v["max_horizon"]:
            print(f"   max_horizon: {v['max_horizon']}")
    else:
        print(f"\n#{idx} [{claim['post_id']}] ❌ {result.get('error', 'unknown')}")
    return result


async def main():
    results = []
    for i, claim in enumerate(sample, 1):
        results.append(await verify_one(i, claim))
        await asyncio.sleep(8)  # Opus 30k ITPM throttle

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    status_counts = {}
    strength_counts = {}
    invalid_count = 0
    for r in results:
        if "verdict" in r:
            v = r["verdict"]
            st = v.get("status", "error")
            status_counts[st] = status_counts.get(st, 0) + 1
            stren = v.get("prediction_strength", "none")
            strength_counts[stren] = strength_counts.get(stren, 0) + 1
            if v.get("verdict_invalid"):
                invalid_count += 1
    print(f"Status distribution: {status_counts}")
    print(f"Strength distribution: {strength_counts}")
    print(f"Invalid verdicts (mutual-exclusion violations): {invalid_count}")

    out = ROOT / "scripts/outputs/extraction_eval/verifier_v2_test.json"
    out.write_text(json.dumps(
        {"today": TODAY, "model": "anthropic/claude-opus-4-6",
         "prompt_version": "v2", "results": results},
        ensure_ascii=False, indent=2
    ))
    print(f"\nSaved → {out}")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Run empirical test (background, ~2 min)**

```bash
.venv/bin/python -u scripts/empirical/verifier_v2_test.py | tee /tmp/verifier_v2_run.log
```

Expected: 10 verdicts printed + summary at end. Each verdict shows status + strength.

- [ ] **Step 3: Analyze findings vs v1 baseline**

Compare with `scripts/outputs/extraction_eval/verifier_4status_test.json`:

- v1 had Opus inconsistency on #5 (unresolved + retry_after — both set).
- v1 had no `prediction_strength` field at all.
- v1 had no `max_horizon` field.

Validate v2 results:
- [ ] No `verdict_invalid=True` events (mutual-exclusion working).
- [ ] All `premature` cases have `retry_after` set.
- [ ] All `premature` without `target_date` have `max_horizon` set.
- [ ] `prediction_strength` distributed plausibly (not all "high").
- [ ] At least 1 case classified as `low` strength (matches our extraction analysis).

If any issue found, document in commit message and consider iterating prompt v2.

- [ ] **Step 4: Commit empirical script + results**

```bash
git add scripts/empirical/verifier_v2_test.py scripts/outputs/extraction_eval/verifier_v2_test.json
git commit -m "test(empirical): v2 verifier prompt validated on 10 random Flash Lite claims via Opus"
```

Note: `scripts/outputs/extraction_eval/` is currently in `.gitignore`. Force-add the verifier_v2 result manually if you want it committed (alternatively store findings inline in this plan or in a doc).

---

## Final verification

- [ ] **Run full test suite — confirm everything passes:**

```bash
.venv/bin/python -m pytest tests/ -v
```

Expected: All tests passing. Should be roughly:
- Existing: 88 tests
- New: 30+ tests (3 domain + 17 prompt + 9 storage interface + 9 verifier)
- **Total: ~118+ tests**

- [ ] **Verify migration parses (sanity check):**

```bash
.venv/bin/python -c "
from importlib.util import spec_from_file_location, module_from_spec
spec = spec_from_file_location('m', 'alembic/versions/2026_04_29_add_verification_metadata.py')
m = module_from_spec(spec); spec.loader.exec_module(m)
print('rev:', m.revision); print('upgrade:', m.upgrade); print('downgrade:', m.downgrade)
"
```

Expected: `rev: 2026_04_29_verif`, both upgrade/downgrade are functions.

- [ ] **Empirical results sanity check:**

Open `scripts/outputs/extraction_eval/verifier_v2_test.json` and verify:
- 10 results, no errors
- 0 `verdict_invalid` flags (or document any violations as known limitations)
- Each `premature` has `retry_after`
- Mix of `low`/`medium`/`high` strengths

- [ ] **Push branch (optional, for review):**

```bash
git log --oneline | head -10  # confirm 9 task commits
```

---

## Open items deferred

These are NOT blockers for this plan — they go into Task 15 plan or later:

- `verification_cycle()` orchestration function (combines `force_unresolved_past_horizon` + `get_eligible_for_verification` + verifier loop).
- Scheduler trigger (cron-like cadence) for verification_cycle.
- E2E integration test (requires real Postgres via Docker — Task 17-19).
- Removing deprecated `get_unverified()` and old `verify()` API (after Task 15 has migrated to v2).
- Manual review queue UI for low-strength + high-attempts predictions.
- News collector for evidence URL (Task 22).

---

## Cross-references

- Spec: [`2026-04-26-verification-trigger-policy-design.md`](2026-04-26-verification-trigger-policy-design.md)
- Architecture refresh: [`2026-04-26-architecture-current.md`](2026-04-26-architecture-current.md)
- v1 empirical test results: `scripts/outputs/extraction_eval/verifier_4status_test.json`
- Master plan: [`2026-04-08-prophet-checker-plan.md`](2026-04-08-prophet-checker-plan.md)
