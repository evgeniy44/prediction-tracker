from datetime import date, datetime
from prophet_checker.models.domain import (
    Person, PersonSource, Prediction, PredictionStatus, RawDocument, SourceType,
)
from prophet_checker.storage.postgres import (
    domain_to_person_db, person_db_to_domain,
    domain_to_person_source_db, person_source_db_to_domain,
    domain_to_raw_document_db, raw_document_db_to_domain,
    domain_to_prediction_db, prediction_db_to_domain,
)
from prophet_checker.models.db import PersonDB, PersonSourceDB, RawDocumentDB, PredictionDB


def test_person_domain_to_db():
    person = Person(id="1", name="Арестович", description="Оглядач")
    db_obj = domain_to_person_db(person)
    assert isinstance(db_obj, PersonDB)
    assert db_obj.id == "1"
    assert db_obj.name == "Арестович"


def test_person_db_to_domain():
    db_obj = PersonDB(id="1", name="Арестович", description="Оглядач", created_at=datetime(2024, 1, 1))
    domain_obj = person_db_to_domain(db_obj)
    assert isinstance(domain_obj, Person)
    assert domain_obj.name == "Арестович"


def test_person_source_round_trip():
    ps = PersonSource(id="1", person_id="p1", source_type=SourceType.TELEGRAM,
                      source_identifier="@chan", enabled=True)
    db_obj = domain_to_person_source_db(ps)
    assert db_obj.source_type == "telegram"
    result = person_source_db_to_domain(db_obj)
    assert result.source_type == SourceType.TELEGRAM
    assert result.source_identifier == "@chan"


def test_raw_document_round_trip():
    doc = RawDocument(id="1", person_id="p1", source_type=SourceType.NEWS,
                      url="https://example.com/article", published_at=datetime(2023, 5, 1),
                      raw_text="Some text", language="uk", collected_at=datetime(2024, 1, 1))
    db_obj = domain_to_raw_document_db(doc)
    assert db_obj.source_type == "news"
    assert db_obj.url == "https://example.com/article"
    result = raw_document_db_to_domain(db_obj)
    assert result.source_type == SourceType.NEWS


def test_prediction_round_trip():
    pred = Prediction(id="1", document_id="d1", person_id="p1",
                      claim_text="Test claim", prediction_date=date(2023, 1, 1),
                      target_date=date(2023, 6, 1), topic="війна",
                      status=PredictionStatus.CONFIRMED, confidence=0.85,
                      evidence_url="https://news.com/proof", evidence_text="Proof text")
    db_obj = domain_to_prediction_db(pred)
    assert db_obj.status == "confirmed"
    assert db_obj.confidence == 0.85
    result = prediction_db_to_domain(db_obj)
    assert result.status == PredictionStatus.CONFIRMED
    assert result.evidence_url == "https://news.com/proof"


def test_domain_to_prediction_db_includes_v2_fields():
    from datetime import UTC, date, datetime
    from prophet_checker.models.domain import Prediction, PredictionStatus, PredictionStrength
    from prophet_checker.storage.postgres import domain_to_prediction_db

    pred = Prediction(
        id="p1",
        document_id="d1",
        person_id="per1",
        claim_text="Test claim",
        prediction_date=date(2024, 1, 1),
        prediction_strength=PredictionStrength.HIGH,
        max_horizon=date(2025, 1, 1),
        next_check_at=date(2024, 6, 1),
        verify_attempts=3,
        last_verify_error="ValueError: invalid status",
        last_verify_error_at=datetime(2024, 5, 1, tzinfo=UTC),
    )
    db_obj = domain_to_prediction_db(pred)
    assert db_obj.prediction_strength == "high"
    assert db_obj.max_horizon == date(2025, 1, 1)
    assert db_obj.next_check_at == date(2024, 6, 1)
    assert db_obj.verify_attempts == 3
    assert db_obj.last_verify_error == "ValueError: invalid status"
    assert db_obj.last_verify_error_at == datetime(2024, 5, 1, tzinfo=UTC)


def test_prediction_db_to_domain_includes_v2_fields():
    from datetime import UTC, date, datetime
    from prophet_checker.models.db import PredictionDB
    from prophet_checker.models.domain import PredictionStrength
    from prophet_checker.storage.postgres import prediction_db_to_domain

    db = PredictionDB(
        id="p1",
        document_id="d1",
        person_id="per1",
        claim_text="Test claim",
        prediction_date=date(2024, 1, 1),
        topic="test topic",
        status="unresolved",
        confidence=0.0,
        prediction_strength="medium",
        max_horizon=date(2025, 1, 1),
        next_check_at=date(2024, 6, 1),
        verify_attempts=2,
        last_verify_error="JSONDecodeError",
        last_verify_error_at=datetime(2024, 5, 1, tzinfo=UTC),
    )
    pred = prediction_db_to_domain(db)
    assert pred.prediction_strength == PredictionStrength.MEDIUM
    assert pred.max_horizon == date(2025, 1, 1)
    assert pred.next_check_at == date(2024, 6, 1)
    assert pred.verify_attempts == 2
    assert pred.last_verify_error == "JSONDecodeError"
    assert pred.last_verify_error_at == datetime(2024, 5, 1, tzinfo=UTC)


def test_domain_to_prediction_db_includes_prediction_value():
    from datetime import date
    from prophet_checker.models.domain import Prediction, PredictionValue
    from prophet_checker.storage.postgres import domain_to_prediction_db

    pred = Prediction(
        id="p1", document_id="d1", person_id="per1",
        claim_text="Test", prediction_date=date(2024, 1, 1),
        prediction_value=PredictionValue.HIGH,
    )
    db_obj = domain_to_prediction_db(pred)
    assert db_obj.prediction_value == "high"


def test_prediction_db_to_domain_includes_prediction_value():
    from datetime import date
    from prophet_checker.models.db import PredictionDB
    from prophet_checker.models.domain import PredictionValue
    from prophet_checker.storage.postgres import prediction_db_to_domain

    db = PredictionDB(
        id="p1", document_id="d1", person_id="per1",
        claim_text="Test", prediction_date=date(2024, 1, 1),
        topic="", status="unresolved", confidence=0.0,
        verify_attempts=0,
        prediction_value="medium",
    )
    pred = prediction_db_to_domain(db)
    assert pred.prediction_value == PredictionValue.MEDIUM


def test_domain_to_prediction_db_includes_context():
    from datetime import date
    from prophet_checker.models.domain import Prediction
    from prophet_checker.storage.postgres import domain_to_prediction_db

    pred = Prediction(
        id="p1", document_id="d1", person_id="per1",
        claim_text="Test", prediction_date=date(2024, 1, 1),
        context="Verbatim quote from post",
    )
    db_obj = domain_to_prediction_db(pred)
    assert db_obj.context == "Verbatim quote from post"


def test_prediction_db_to_domain_includes_context():
    from datetime import date
    from prophet_checker.models.db import PredictionDB
    from prophet_checker.storage.postgres import prediction_db_to_domain

    db = PredictionDB(
        id="p1", document_id="d1", person_id="per1",
        claim_text="Test", prediction_date=date(2024, 1, 1),
        topic="", status="unresolved", confidence=0.0,
        verify_attempts=0,
        context="Verbatim quote from post",
    )
    pred = prediction_db_to_domain(db)
    assert pred.context == "Verbatim quote from post"
