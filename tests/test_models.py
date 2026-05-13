from datetime import UTC, date, datetime
from prophet_checker.models.domain import (
    Person,
    PersonSource,
    RawDocument,
    Prediction,
    PredictionStatus,
    SourceType,
)


def test_person_creation():
    person = Person(id="1", name="Арестович", description="Політичний оглядач")
    assert person.name == "Арестович"
    assert person.description == "Політичний оглядач"


def test_person_source_creation():
    ps = PersonSource(
        id="1",
        person_id="1",
        source_type=SourceType.TELEGRAM,
        source_identifier="@arestovych",
        enabled=True,
    )
    assert ps.source_type == SourceType.TELEGRAM
    assert ps.source_identifier == "@arestovych"
    assert ps.enabled is True


def test_raw_document_creation():
    doc = RawDocument(
        id="1",
        person_id="1",
        source_type=SourceType.TELEGRAM,
        url="https://t.me/arestovych/1234",
        published_at=datetime(2023, 6, 15, 10, 30),
        raw_text="Контрнаступ почнеться влітку",
        language="uk",
        collected_at=datetime(2024, 1, 1, 12, 0),
    )
    assert doc.source_type == SourceType.TELEGRAM
    assert doc.language == "uk"


def test_prediction_creation():
    pred = Prediction(
        id="1",
        document_id="1",
        person_id="1",
        claim_text="Контрнаступ почнеться влітку 2023",
        prediction_date=date(2023, 1, 12),
        target_date=date(2023, 6, 1),
        topic="війна",
        status=PredictionStatus.UNRESOLVED,
        confidence=0.0,
    )
    assert pred.status == PredictionStatus.UNRESOLVED
    assert pred.confidence == 0.0
    assert pred.evidence_url is None


def test_prediction_status_enum():
    assert PredictionStatus.CONFIRMED.value == "confirmed"
    assert PredictionStatus.REFUTED.value == "refuted"
    assert PredictionStatus.UNRESOLVED.value == "unresolved"


def test_source_type_enum():
    assert SourceType.TELEGRAM.value == "telegram"
    assert SourceType.NEWS.value == "news"


def test_person_source_default_last_collected_at_is_creation_time():
    before = datetime.now(UTC)
    ps = PersonSource(
        id="ps1",
        person_id="p1",
        source_type=SourceType.TELEGRAM,
        source_identifier="@arestovich",
    )
    after = datetime.now(UTC)
    assert ps.last_collected_at is not None
    assert before <= ps.last_collected_at <= after


def test_person_source_explicit_last_collected_at_preserved():
    explicit = datetime(2024, 1, 15, tzinfo=UTC)
    ps = PersonSource(
        id="ps1",
        person_id="p1",
        source_type=SourceType.TELEGRAM,
        source_identifier="@arestovich",
        last_collected_at=explicit,
    )
    assert ps.last_collected_at == explicit


def test_prediction_strength_enum_values():
    from prophet_checker.models.domain import PredictionStrength
    assert PredictionStrength.LOW.value == "low"
    assert PredictionStrength.MEDIUM.value == "medium"
    assert PredictionStrength.HIGH.value == "high"


def test_prediction_has_v2_verification_field_defaults():
    from datetime import date
    from prophet_checker.models.domain import Prediction
    pred = Prediction(
        id="p1",
        document_id="d1",
        person_id="per1",
        claim_text="Test claim",
        prediction_date=date(2024, 1, 1),
    )
    assert pred.prediction_strength is None
    assert pred.max_horizon is None
    assert pred.next_check_at is None
    assert pred.verify_attempts == 0
    assert pred.last_verify_error is None
    assert pred.last_verify_error_at is None


def test_prediction_value_enum_values():
    from prophet_checker.models.domain import PredictionValue
    assert PredictionValue.LOW.value == "low"
    assert PredictionValue.MEDIUM.value == "medium"
    assert PredictionValue.HIGH.value == "high"


def test_prediction_has_value_field_default():
    from datetime import date
    from prophet_checker.models.domain import Prediction
    pred = Prediction(
        id="p1",
        document_id="d1",
        person_id="per1",
        claim_text="Test",
        prediction_date=date(2024, 1, 1),
    )
    assert pred.prediction_value is None
