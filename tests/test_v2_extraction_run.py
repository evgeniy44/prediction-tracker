import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


def test_select_posts_for_v2_keeps_only_posts_with_v1_claims():
    from extraction.extraction_run import select_posts_for_v2
    posts = [
        {"id": "A", "person_name": "Арестович"},
        {"id": "B", "person_name": "Арестович"},
        {"id": "C", "person_name": "Арестович"},
        {"id": "D", "person_name": "Інший Автор"},
    ]
    v1_extractions = {
        "extractions": {
            "model-x": {
                "A": [{"claim_text": "Some claim"}],
                "B": [],
                "C": [{"claim_text": "Another"}],
                "D": [{"claim_text": "Other author"}],
            }
        }
    }
    result = select_posts_for_v2(posts, v1_extractions, "model-x", "Арестович")
    assert [p["id"] for p in result] == ["A", "C"]


def test_select_posts_for_v2_filters_by_author():
    from extraction.extraction_run import select_posts_for_v2
    posts = [
        {"id": "A", "person_name": "Арестович"},
        {"id": "B", "person_name": "Подоляк"},
    ]
    v1_extractions = {
        "extractions": {
            "m": {"A": [{"claim_text": "X"}], "B": [{"claim_text": "Y"}]}
        }
    }
    result = select_posts_for_v2(posts, v1_extractions, "m", "Арестович")
    assert [p["id"] for p in result] == ["A"]
