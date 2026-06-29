from datetime import date

import pytest

from generation.build_generation_gold import build_gold
from prophet_checker.models.domain import Prediction


def _retrieval():
    return [
        {"query": "claim-фраза A", "target_id": "t1", "source_field": "claim_text"},
        {"query": "situation-фраза A", "target_id": "t1", "source_field": "situation"},
        {"query": "claim-фраза B", "target_id": "t2", "source_field": "claim_text"},
        {"query": "situation-фраза B", "target_id": "t2", "source_field": "situation"},
    ]


def _preds():
    def p(pid, claim):
        return Prediction(
            id=pid, document_id="d", person_id="x", claim_text=claim, prediction_date=date(2024, 1, 1)
        )

    return {"t1": p("t1", "клейм-1"), "t2": p("t2", "клейм-2"), "s1": p("s1", "синтез-клейм")}


def test_build_gold_single_source_5050_and_enrichment():
    manual = [
        {"question": "синтез?", "category": "synthesis", "prediction_ids": ["t1", "s1"]},
        {"question": "рецепт борщу", "category": "off_domain", "prediction_ids": []},
    ]
    out = build_gold(_retrieval(), manual, _preds())

    single = [r for r in out if r["category"] == "single_source"]
    assert len(single) == 2
    # 50/50: t1 (idx0) → claim-фраза, t2 (idx1) → situation-фраза
    by_tid = {r["expected_sources"][0]["prediction"]["id"]: r for r in single}
    assert by_tid["t1"]["question"] == "claim-фраза A"
    assert by_tid["t2"]["question"] == "situation-фраза B"
    assert by_tid["t1"]["expected_sources"][0]["prediction"]["claim_text"] == "клейм-1"  # вморожено

    syn = next(r for r in out if r["category"] == "synthesis")
    assert syn["answerable"] is True
    assert {e["prediction"]["id"] for e in syn["expected_sources"]} == {"t1", "s1"}
    assert {e["prediction"]["claim_text"] for e in syn["expected_sources"]} == {"клейм-1", "синтез-клейм"}

    off = next(r for r in out if r["category"] == "off_domain")
    assert off["answerable"] is False
    assert off["expected_sources"] == []


def test_build_gold_failloud_on_unknown_prediction():
    manual = [{"question": "x", "category": "synthesis", "prediction_ids": ["NOPE"]}]
    with pytest.raises(KeyError):
        build_gold(_retrieval(), manual, _preds())
