from __future__ import annotations

import argparse
import asyncio
import json
import sys
from contextlib import AsyncExitStack
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

try:
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env", override=True)
except ImportError:
    pass

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from prophet_checker.config import Settings  # noqa: E402
from prophet_checker.llm import EmbeddingClient  # noqa: E402
from retrieval.embed_corpus import REPRESENTATIONS, config_name  # noqa: E402
from retrieval.eval_store import PostgresEvalEmbStore  # noqa: E402

GOLD_PATH = Path("scripts/data/retrieval_query_gold.json")
REPORT_PATH = Path("scripts/outputs/retrieval_eval/retrieval_eval_report.md")


def recall_at_k(ranked: list[str], target_id: str, k: int) -> float:
    return 1.0 if target_id in ranked[:k] else 0.0


def reciprocal_rank(ranked: list[str], target_id: str) -> float:
    if target_id in ranked:
        return 1.0 / (ranked.index(target_id) + 1)
    return 0.0


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def aggregate_metrics(results: list[dict], ks: list[int]) -> dict:
    """results: [{source_field, ranked, target_id}]. Повертає метрики overall + по source_field."""
    groups: dict[str, list[dict]] = {"overall": list(results)}
    for r in results:
        groups.setdefault(r["source_field"], []).append(r)
    out: dict[str, dict] = {}
    for name, rows in groups.items():
        metrics = {
            f"recall@{k}": _mean([recall_at_k(r["ranked"], r["target_id"], k) for r in rows])
            for k in ks
        }
        metrics["mrr"] = _mean([reciprocal_rank(r["ranked"], r["target_id"]) for r in rows])
        metrics["n"] = len(rows)
        out[name] = metrics
    return out


def render_report(per_config: dict, ks: list[int]) -> str:
    cols = [f"recall@{k}" for k in ks] + ["mrr", "n"]
    header = "| config | scope | " + " | ".join(cols) + " |"
    sep = "|" + "---|" * (len(cols) + 2)
    lines = ["# Retrieval eval report", "", header, sep]
    for name in sorted(per_config):
        for scope in sorted(per_config[name]):
            m = per_config[name][scope]
            cells = [f"{m.get(c, 0):.3f}" if c != "n" else str(m.get("n", 0)) for c in cols]
            lines.append(f"| {name} | {scope} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


async def run_eval(gold_path: Path, configs, embedder_factory, store, ks: list[int]) -> dict:
    gold = json.loads(gold_path.read_text())
    await store.ensure_table()
    limit = max(ks)
    per_config: dict[str, dict] = {}
    for model, kind in configs:
        name = config_name(model, kind)
        embedder = embedder_factory(model)
        results = []
        for item in gold:
            qvec = await embedder.embed(item["query"])
            ranked = await store.search(name, qvec, limit)
            results.append(
                {
                    "source_field": item["source_field"],
                    "ranked": ranked,
                    "target_id": item["target_id"],
                }
            )
        per_config[name] = aggregate_metrics(results, ks)
    return per_config


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", type=Path, default=GOLD_PATH)
    parser.add_argument("--models", nargs="+", default=["text-embedding-3-small"])
    parser.add_argument("--ks", nargs="+", type=int, default=[1, 5, 10, 20])
    parser.add_argument("--report", type=Path, default=REPORT_PATH)
    args = parser.parse_args()
    settings = Settings()
    configs = [(m, k) for m in args.models for k in REPRESENTATIONS]

    def factory(model: str):
        return EmbeddingClient(model=model, api_key=settings.openai_api_key)

    async def _run():
        async with AsyncExitStack() as stack:
            engine = create_async_engine(settings.database_url, echo=False)
            stack.push_async_callback(engine.dispose)
            store = PostgresEvalEmbStore(async_sessionmaker(engine, expire_on_commit=False))
            return await run_eval(args.gold, configs, factory, store, args.ks)

    per_config = asyncio.run(_run())
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(render_report(per_config, args.ks))
    print(f"report → {args.report}")


if __name__ == "__main__":
    main()
