import json
from prophet_checker.llm.prompts import (
    build_extraction_prompt,
    build_verification_prompt,
    build_rag_prompt,
    parse_extraction_response,
    parse_verification_response,
)


def test_build_extraction_prompt():
    prompt = build_extraction_prompt(
        text="Контрнаступ почнеться влітку 2023 року",
        person_name="Арестович",
        published_date="2023-01-15",
    )
    assert "Арестович" in prompt
    assert "Контрнаступ почнеться влітку 2023 року" in prompt
    assert "2023-01-15" in prompt
    assert "JSON" in prompt


def test_parse_extraction_response_valid():
    response = json.dumps({
        "predictions": [
            {
                "claim_text": "Контрнаступ почнеться влітку 2023",
                "prediction_date": "2023-01-15",
                "target_date": "2023-06-01",
                "topic": "війна",
            }
        ]
    })
    predictions = parse_extraction_response(response)
    assert len(predictions) == 1
    assert predictions[0]["claim_text"] == "Контрнаступ почнеться влітку 2023"


def test_parse_extraction_response_no_predictions():
    response = json.dumps({"predictions": []})
    predictions = parse_extraction_response(response)
    assert predictions == []


def test_parse_extraction_response_invalid_json():
    predictions = parse_extraction_response("not json at all")
    assert predictions == []


def test_build_verification_prompt():
    prompt = build_verification_prompt(
        claim="Контрнаступ почнеться влітку 2023",
        prediction_date="2023-01-15",
        target_date="2023-06-01",
    )
    assert "Контрнаступ почнеться влітку 2023" in prompt
    assert "JSON" in prompt


def test_parse_verification_response_valid():
    response = json.dumps({
        "status": "confirmed",
        "confidence": 0.85,
        "evidence_url": "https://news.com/article",
        "evidence_text": "The counteroffensive began in June 2023",
    })
    result = parse_verification_response(response)
    assert result["status"] == "confirmed"
    assert result["confidence"] == 0.85


def test_parse_verification_response_invalid_json():
    result = parse_verification_response("broken json")
    assert result is None


def test_build_rag_prompt():
    predictions_context = [
        {"claim_text": "Pred 1", "status": "confirmed", "confidence": 0.9},
        {"claim_text": "Pred 2", "status": "refuted", "confidence": 0.7},
    ]
    prompt = build_rag_prompt(
        question="Що казав Арестович про контрнаступ?",
        predictions_context=predictions_context,
    )
    assert "Що казав Арестович про контрнаступ?" in prompt
    assert "Pred 1" in prompt
    assert "Pred 2" in prompt
