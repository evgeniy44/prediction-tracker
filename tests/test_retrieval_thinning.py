from datetime import date

from prophet_checker.models.domain import (
    Prediction,
    PredictionStrength,
    PredictionValue,
)
from retrieval.build_eval_corpus import thin_chronologically


def _pred(pid: str, d: str, strength=PredictionStrength.LOW, value=PredictionValue.LOW):
    return Prediction(
        id=pid,
        document_id="doc",
        person_id="p",
        claim_text=f"claim {pid}",
        situation=f"situation {pid}",
        prediction_date=date.fromisoformat(d),
        prediction_strength=strength,
        prediction_value=value,
    )


def test_keeps_single_prediction():
    preds = [_pred("a", "2024-01-01")]
    assert [p.id for p in thin_chronologically(preds, min_gap_days=14)] == ["a"]


def test_drops_prediction_within_window_keeps_higher_score():
    # b на 3 дні пізніше a, у тому самому 14-денному вікні; b має вищий score → лишається b
    preds = [
        _pred("a", "2024-01-01", PredictionStrength.LOW, PredictionValue.LOW),
        _pred("b", "2024-01-04", PredictionStrength.HIGH, PredictionValue.HIGH),
    ]
    assert [p.id for p in thin_chronologically(preds, min_gap_days=14)] == ["b"]


def test_keeps_both_when_gap_exceeds_window():
    preds = [_pred("a", "2024-01-01"), _pred("b", "2024-02-01")]
    assert [p.id for p in thin_chronologically(preds, min_gap_days=14)] == ["a", "b"]


def test_next_window_anchored_on_kept_date():
    # a(01-01,low), b(01-10,high) → у вікні [01-01,01-15) лишається b(01-10);
    # наступне вікно стартує з b.date+14 = 01-24, тож c(01-20) відкидається, d(01-25) лишається
    preds = [
        _pred("a", "2024-01-01", PredictionStrength.LOW, PredictionValue.LOW),
        _pred("b", "2024-01-10", PredictionStrength.HIGH, PredictionValue.HIGH),
        _pred("c", "2024-01-20", PredictionStrength.LOW, PredictionValue.LOW),
        _pred("d", "2024-01-25", PredictionStrength.LOW, PredictionValue.LOW),
    ]
    assert [p.id for p in thin_chronologically(preds, min_gap_days=14)] == ["b", "d"]
