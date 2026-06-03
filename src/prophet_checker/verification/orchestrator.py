from __future__ import annotations

from datetime import UTC, date, datetime

from prophet_checker.models.domain import (
    Prediction,
    PredictionStatus,
    PredictionStrength,
    PredictionValue,
)
from prophet_checker.verification.report import VerificationCycleReport, VerificationEntry


def apply_verification_result(prediction: Prediction, result: dict, now: datetime) -> Prediction:
    status = PredictionStatus(result["status"])
    updates = {
        "status": status,
        "confidence": result["confidence"],
        "prediction_strength": PredictionStrength(result["prediction_strength"]),
        "prediction_value": PredictionValue(result["prediction_value"]),
        "evidence_text": result.get("evidence"),
        "verified_at": now,
        "verify_attempts": prediction.verify_attempts + 1,
        "last_verify_error": None,
        "last_verify_error_at": None,
        "next_check_at": None,
        "max_horizon": None,
    }
    if status == PredictionStatus.PREMATURE:
        retry_after = result.get("retry_after")
        if retry_after:
            updates["next_check_at"] = date.fromisoformat(retry_after)
        max_horizon = result.get("max_horizon")
        if max_horizon:
            updates["max_horizon"] = date.fromisoformat(max_horizon)
    return prediction.model_copy(update=updates)


def apply_verification_error(prediction: Prediction, exc: Exception, now: datetime) -> Prediction:
    return prediction.model_copy(update={
        "verify_attempts": prediction.verify_attempts + 1,
        "last_verify_error": f"{type(exc).__name__}: {exc}",
        "last_verify_error_at": now,
    })


class VerificationOrchestrator:
    def __init__(self, prediction_repo, verifier, attempt_cap: int = 5) -> None:
        self._prediction_repo = prediction_repo
        self._verifier = verifier
        self._attempt_cap = attempt_cap

    async def run_cycle(self, limit: int | None = None, today: date | None = None) -> VerificationCycleReport:
        started = datetime.now(UTC)
        today_str = (today or started.date()).isoformat()
        candidates = await self._prediction_repo.get_unverified()
        eligible = [p for p in candidates if p.verify_attempts < self._attempt_cap]
        skipped = len(candidates) - len(eligible)
        if limit is not None:
            eligible = eligible[:limit]
        report = VerificationCycleReport(started_at=started, skipped=skipped)
        for p in eligible:
            try:
                result = await self._verifier.verify(
                    claim=p.claim_text,
                    situation=p.situation,
                    prediction_date=p.prediction_date.isoformat(),
                    target_date=p.target_date.isoformat() if p.target_date else None,
                    today=today_str,
                )
                updated = apply_verification_result(p, result, started)
                report.verified += 1
                report.entries.append(VerificationEntry(prediction_id=p.id, status=updated.status.value))
            except Exception as exc:
                updated = apply_verification_error(p, exc, started)
                report.failed += 1
                report.entries.append(
                    VerificationEntry(prediction_id=p.id, error=f"{type(exc).__name__}: {exc}")
                )
            await self._prediction_repo.update(updated)
        report.finished_at = datetime.now(UTC)
        return report
