import json
from datetime import date

from prophet_checker.models.domain import (
    Prediction,
    PredictionStrength,
    PredictionValue,
)
from retrieval.build_eval_corpus import eligible, prediction_to_row, write_corpus


def _pred(pid, strength=PredictionStrength.HIGH, value=PredictionValue.HIGH, situation="s"):
    return Prediction(
        id=pid,
        document_id="doc",
        person_id="p",
        claim_text=f"claim {pid}",
        situation=situation,
        prediction_date=date(2024, 1, 1),
        topic="війна",
        prediction_strength=strength,
        prediction_value=value,
    )


def test_eligible_requires_strength_and_value():
    assert eligible(_pred("a")) is True
    p = _pred("b")
    p.prediction_strength = None
    assert eligible(p) is False


def test_prediction_to_row_shape():
    row = prediction_to_row(_pred("a"))
    assert row == {
        "id": "a",
        "claim_text": "claim a",
        "situation": "s",
        "topic": "війна",
        "prediction_date": "2024-01-01",
        "strength": "high",
        "value": "high",
    }


def test_write_corpus_roundtrip(tmp_path):
    out = tmp_path / "corpus.json"
    write_corpus([_pred("a"), _pred("b")], out)
    data = json.loads(out.read_text())
    assert [r["id"] for r in data] == ["a", "b"]
