from pydantic import BaseModel

from eval_common import run_eval
from eval_common.models import EvalCase, EvalMetadata, ScoreCard


class _In(BaseModel):
    n: int


class _Out(BaseModel):
    doubled: int


class _M(BaseModel):
    total: int


class _SumScorer:
    name = "sum"

    async def score(self, run):
        return ScoreCard(scorer=self.name, score=float(run.result.doubled))


async def test_run_eval_end_to_end(tmp_path):
    cases = [EvalCase(id=str(i), input=_In(n=i)) for i in range(3)]

    async def run_one(case):
        return _Out(doubled=case.input.n * 2)

    def aggregate(scored):
        return _M(total=int(sum(c.score for s in scored for c in s.cards)))

    meta = EvalMetadata(eval_name="t", created_at="2026-01-01T00:00:00Z", n_cases=3)
    report = await run_eval(cases, run_one, [_SumScorer()], aggregate, meta, tmp_path)

    assert report.metrics.total == 0 + 2 + 4
    assert len(report.runs) == 3
    assert (tmp_path / "report.json").exists()
    assert (tmp_path / "report.md").exists()
