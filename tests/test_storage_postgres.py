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
