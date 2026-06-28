from datetime import date

from generation.judge_prompts import (
    parse_completeness_response,
    parse_faithfulness_response,
    render_sources,
)
from prophet_checker.models.domain import (
    Prediction,
    PredictionStatus,
    RetrievedPrediction,
)


def test_parse_faithfulness_response_plain_and_fenced():
    raw = '{"claims": [{"claim": "a", "supported": true, "reason": "r"}, {"claim": "b", "supported": false}]}'
    claims = parse_faithfulness_response(raw)
    assert len(claims) == 2
    assert claims[0].claim == "a" and claims[0].supported is True
    assert claims[1].supported is False
    fenced = '```json\n{"claims": []}\n```'
    assert parse_faithfulness_response(fenced) == []


def test_parse_completeness_response():
    covered, reason = parse_completeness_response('{"covered": true, "reason": "так"}')
    assert covered is True and reason == "так"
    covered, _ = parse_completeness_response('{"covered": false}')
    assert covered is False


def test_render_sources_includes_id_claim_status():
    pred = Prediction(
        id="p1",
        document_id="d",
        person_id="x",
        claim_text="контрнаступ не дійде до моря",
        situation="південь",
        prediction_date=date(2023, 6, 1),
        status=PredictionStatus.REFUTED,
    )
    text = render_sources([RetrievedPrediction(prediction=pred, distance=0.2, rank=1)])
    assert "p1" in text
    assert "контрнаступ не дійде до моря" in text
    assert "refuted" in text
