from datetime import date

from eval_common.models import EvalCase, EvalRun, ScoreCard, ScoredRun
from generation.gen_models import GenerationInput, GenerationLabels
from generation.metrics import aggregate
from prophet_checker.models.domain import AnswerResult, Prediction, RetrievedPrediction


def _pred():
    return Prediction(
        id="p", document_id="d", person_id="x", claim_text="c", prediction_date=date(2024, 1, 1)
    )


def _scored(category, answerable, *, faith=None, recall=None, error=False):
    labels = GenerationLabels(answerable=answerable, category=category)
    case = EvalCase(id="c", input=GenerationInput(question="q"), labels=labels)

    if error:
        run = EvalRun(case=case, result=None, latency_s=0.1, error="RuntimeError")
        cards = [ScoreCard(scorer=name, score=None) for name in ("faithfulness", "completeness")]
        return ScoredRun(run=run, cards=cards)

    result = AnswerResult(
        query="q",
        answer="a",
        sources=[RetrievedPrediction(prediction=_pred(), distance=0.1, rank=1)],
    )
    run = EvalRun(case=case, result=result, latency_s=0.1)
    cards = [
        ScoreCard(scorer="faithfulness", score=faith),
        ScoreCard(scorer="completeness", score=recall),
    ]
    return ScoredRun(run=run, cards=cards)


def test_aggregate_means_and_categories():
    # значення підібрані так, щоб середні були точні у float (без == на 0.7999…)
    scored = [
        _scored("single_source", True, faith=1.0, recall=1.0),
        _scored("single_source", True, faith=0.0, recall=0.0),
        _scored("synthesis", True, faith=0.5, recall=0.5),
        _scored("single_source", True, error=True),  # SUT error → обидва None
    ]
    m = aggregate(scored)
    assert m.n_total == 4
    assert m.n_errors == 1
    assert m.faithfulness_mean == 0.5  # (1.0 + 0.0 + 0.5) / 3
    assert m.hallucination_rate == 0.5
    assert m.recall_mean == 0.5  # (1.0 + 0.0 + 0.5) / 3
    assert m.by_category["single_source"].faithfulness_mean == 0.5  # (1.0 + 0.0) / 2
    assert m.by_category["synthesis"].recall_mean == 0.5
    assert not hasattr(m, "refusal_accuracy")  # поле прибране в v2 — це і дає RED проти старого коду


def test_aggregate_empty():
    m = aggregate([])
    assert m.n_total == 0
    assert m.faithfulness_mean is None
    assert m.by_category == {}
