from __future__ import annotations

from datetime import timedelta

from prophet_checker.models.domain import (
    Prediction,
    PredictionStrength,
    PredictionValue,
)

_RANK = {
    PredictionStrength.LOW: 0,
    PredictionStrength.MEDIUM: 1,
    PredictionStrength.HIGH: 2,
}
_VRANK = {
    PredictionValue.LOW: 0,
    PredictionValue.MEDIUM: 1,
    PredictionValue.HIGH: 2,
}


def _score(pred: Prediction) -> int:
    """Сумарний ранг strength+value (0..4). Вищий = вагоміший прогноз."""
    return _RANK[pred.prediction_strength] + _VRANK[pred.prediction_value]


def thin_chronologically(predictions: list[Prediction], min_gap_days: int = 14) -> list[Prediction]:
    """Жадібне проріджування: у кожному вікні [anchor, anchor+gap) лишаємо прогноз із
    найвищим _score (тайбрейк: рання дата, далі id), наступне вікно стартує з kept.date+gap.
    Гарантує: дати лишених прогнозів ≥ min_gap_days одна від одної."""
    ordered = sorted(predictions, key=lambda p: (p.prediction_date, p.id))
    gap = timedelta(days=min_gap_days)
    kept: list[Prediction] = []
    i = 0
    n = len(ordered)
    while i < n:
        anchor = ordered[i].prediction_date
        window_end = anchor + gap
        group = []
        j = i
        while j < n and ordered[j].prediction_date < window_end:
            group.append(ordered[j])
            j += 1
        best = max(group, key=lambda p: (_score(p), -p.prediction_date.toordinal(), p.id))
        kept.append(best)
        next_start = best.prediction_date + gap
        while i < n and ordered[i].prediction_date < next_start:
            i += 1
    return kept
