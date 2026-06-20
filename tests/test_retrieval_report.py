import json

from retrieval.retrieval_eval import render_report, run_eval


def test_render_report_has_row_per_config():
    per_config = {
        "m1__claim_text": {"overall": {"recall@1": 0.5, "recall@10": 0.8, "mrr": 0.6, "n": 10}},
        "m1__situation": {"overall": {"recall@1": 0.3, "recall@10": 0.7, "mrr": 0.4, "n": 10}},
    }
    md = render_report(per_config, ks=[1, 10])
    assert "m1__claim_text" in md and "m1__situation" in md
    assert "recall@10" in md and "0.8" in md


class FakeEmbedder:
    def __init__(self, model):
        pass

    async def embed(self, text: str) -> list[float]:
        return [1.0, 0.0]


class FakeStore:
    async def ensure_table(self):
        pass

    async def search(self, config, query, limit):
        return ["a", "b"]  # завжди повертає "a" першим


async def test_run_eval_produces_metrics_per_config(tmp_path):
    gold = tmp_path / "gold.json"
    gold.write_text(json.dumps([{"query": "q", "target_id": "a", "source_field": "claim_text"}]))
    per_config = await run_eval(
        gold_path=gold,
        configs=[("m1", "claim_text")],
        embedder_factory=FakeEmbedder,
        store=FakeStore(),
        ks=[1],
    )
    assert per_config["m1__claim_text"]["overall"]["recall@1"] == 1.0
