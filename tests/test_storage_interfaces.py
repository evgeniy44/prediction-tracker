from datetime import date, datetime
from prophet_checker.storage.interfaces import (
    PersonRepository,
    PredictionRepository,
    SourceRepository,
    VectorStore,
)
from prophet_checker.models.domain import (
    Person,
    PersonSource,
    Prediction,
    PredictionStatus,
    RawDocument,
    SourceType,
)


class FakePersonRepo(PersonRepository):
    def __init__(self):
        self._persons: dict[str, Person] = {}

    async def save(self, person: Person) -> Person:
        self._persons[person.id] = person
        return person

    async def get_by_id(self, person_id: str) -> Person | None:
        return self._persons.get(person_id)

    async def list_all(self) -> list[Person]:
        return list(self._persons.values())


class FakeSourceRepo(SourceRepository):
    def __init__(self):
        self._sources: list[PersonSource] = []
        self._documents: list[RawDocument] = []

    async def save_person_source(self, ps: PersonSource) -> PersonSource:
        self._sources.append(ps)
        return ps

    async def get_person_sources(self, person_id: str, source_type: SourceType | None = None) -> list[PersonSource]:
        return [s for s in self._sources if s.person_id == person_id and (source_type is None or s.source_type == source_type)]

    async def save_document(self, doc: RawDocument) -> RawDocument:
        self._documents.append(doc)
        return doc

    async def get_document_by_url(self, url: str) -> RawDocument | None:
        return next((d for d in self._documents if d.url == url), None)

    async def get_unprocessed_documents(self) -> list[RawDocument]:
        return self._documents

    async def get_last_collected_at(self, person_id: str, source_type: SourceType) -> datetime | None:
        docs = [d for d in self._documents if d.person_id == person_id and d.source_type == source_type]
        if not docs:
            return None
        return max(d.collected_at for d in docs)


class FakePredictionRepo(PredictionRepository):
    def __init__(self):
        self._predictions: list[Prediction] = []

    async def save(self, prediction: Prediction) -> Prediction:
        self._predictions.append(prediction)
        return prediction

    async def get_by_person(self, person_id: str, status: PredictionStatus | None = None) -> list[Prediction]:
        return [
            p for p in self._predictions
            if p.person_id == person_id and (status is None or p.status == status)
        ]

    async def get_unverified(self) -> list[Prediction]:
        return [p for p in self._predictions if p.status == PredictionStatus.UNRESOLVED and p.verified_at is None]

    async def update(self, prediction: Prediction) -> Prediction:
        self._predictions = [p if p.id != prediction.id else prediction for p in self._predictions]
        return prediction


class FakeVectorStore(VectorStore):
    def __init__(self):
        self._entries: list[tuple[str, list[float]]] = []

    async def store_embedding(self, prediction_id: str, embedding: list[float]) -> None:
        self._entries.append((prediction_id, embedding))

    async def search_similar(self, query_embedding: list[float], limit: int = 10) -> list[str]:
        return [pid for pid, _ in self._entries[:limit]]


async def test_person_repo_round_trip():
    repo = FakePersonRepo()
    person = Person(id="1", name="Арестович", description="Оглядач")
    await repo.save(person)
    result = await repo.get_by_id("1")
    assert result is not None
    assert result.name == "Арестович"


async def test_source_repo_save_and_query():
    repo = FakeSourceRepo()
    ps = PersonSource(id="1", person_id="1", source_type=SourceType.TELEGRAM, source_identifier="@arest")
    await repo.save_person_source(ps)
    sources = await repo.get_person_sources("1", SourceType.TELEGRAM)
    assert len(sources) == 1
    assert sources[0].source_identifier == "@arest"


async def test_source_repo_last_collected_at():
    repo = FakeSourceRepo()
    doc1 = RawDocument(id="1", person_id="1", source_type=SourceType.TELEGRAM, url="u1",
                       published_at=datetime(2023, 1, 1), raw_text="text",
                       collected_at=datetime(2024, 1, 1))
    doc2 = RawDocument(id="2", person_id="1", source_type=SourceType.TELEGRAM, url="u2",
                       published_at=datetime(2023, 2, 1), raw_text="text",
                       collected_at=datetime(2024, 2, 1))
    await repo.save_document(doc1)
    await repo.save_document(doc2)
    last = await repo.get_last_collected_at("1", SourceType.TELEGRAM)
    assert last == datetime(2024, 2, 1)


async def test_source_repo_last_collected_at_empty():
    repo = FakeSourceRepo()
    last = await repo.get_last_collected_at("1", SourceType.TELEGRAM)
    assert last is None


async def test_prediction_repo_save_and_query():
    repo = FakePredictionRepo()
    pred = Prediction(id="1", document_id="d1", person_id="1",
                      claim_text="Test prediction", prediction_date=date(2023, 1, 1))
    await repo.save(pred)
    results = await repo.get_by_person("1")
    assert len(results) == 1
    assert results[0].claim_text == "Test prediction"


async def test_prediction_repo_filter_by_status():
    repo = FakePredictionRepo()
    p1 = Prediction(id="1", document_id="d1", person_id="1",
                    claim_text="Pred 1", prediction_date=date(2023, 1, 1),
                    status=PredictionStatus.CONFIRMED)
    p2 = Prediction(id="2", document_id="d2", person_id="1",
                    claim_text="Pred 2", prediction_date=date(2023, 2, 1),
                    status=PredictionStatus.REFUTED)
    await repo.save(p1)
    await repo.save(p2)
    confirmed = await repo.get_by_person("1", status=PredictionStatus.CONFIRMED)
    assert len(confirmed) == 1
    assert confirmed[0].id == "1"


async def test_vector_store_search():
    store = FakeVectorStore()
    await store.store_embedding("p1", [0.1, 0.2, 0.3])
    await store.store_embedding("p2", [0.4, 0.5, 0.6])
    results = await store.search_similar([0.1, 0.2, 0.3], limit=1)
    assert len(results) == 1
