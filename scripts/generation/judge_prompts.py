# scripts/generation/judge_prompts.py
from __future__ import annotations

import json
import re

from generation.gen_models import ClaimVerdict

_FENCE_RE = re.compile(r"^\s*```(?:json|JSON)?\s*\n?(.*?)\n?\s*```\s*$", re.DOTALL)

FAITHFULNESS_SYSTEM = (
    "Ти — суворий фактчекер. Розкладаєш ВІДПОВІДЬ на атомарні фактичні твердження "
    "й перевіряєш кожне проти наданих ДЖЕРЕЛ. Відповідаєш ЛИШЕ валідним JSON."
)
REFUSAL_SYSTEM = "Визначаєш, чи текст є відмовою відповісти за браком даних. Відповідаєш ЛИШЕ JSON."
COMPLETENESS_SYSTEM = (
    "Визначаєш, чи конкретне ТВЕРДЖЕННЯ відображене у ВІДПОВІДІ. Відповідаєш ЛИШЕ JSON."
)


def _extract_json(text: str) -> dict:
    m = _FENCE_RE.match(text.strip())
    payload = m.group(1) if m else text
    return json.loads(payload)


def render_sources(sources: list) -> str:
    lines = []
    for s in sources:
        p = s.prediction
        situation = f" | {p.situation}" if p.situation else ""
        lines.append(f"[{p.id}] {p.claim_text}{situation} (status: {p.status.value})")
    return "\n".join(lines)


def build_faithfulness_prompt(answer: str, sources: list) -> str:
    return (
        "Розклади ВІДПОВІДЬ на атомарні фактичні твердження. Для кожного визнач, чи воно "
        "підкріплене ДЖЕРЕЛАМИ (supported true/false). Якщо ВІДПОВІДЬ — відмова або не містить "
        'фактів, поверни порожній список. Формат: {"claims": [{"claim": "...", '
        '"supported": true, "reason": "..."}]}\n\n'
        f"ВІДПОВІДЬ:\n{answer}\n\nДЖЕРЕЛА:\n{render_sources(sources)}"
    )


def build_refusal_prompt(answer: str) -> str:
    return (
        "Чи ВІДПОВІДЬ є відмовою відповісти (каже, що не може / немає даних)? "
        'Формат: {"refused": true|false}\n\n'
        f"ВІДПОВІДЬ:\n{answer}"
    )


def build_completeness_prompt(answer: str, claim: str) -> str:
    return (
        "Чи ВІДПОВІДЬ відображає (згадує або передає суть) ТВЕРДЖЕННЯ? "
        'Формат: {"covered": true|false, "reason": "..."}\n\n'
        f"ТВЕРДЖЕННЯ:\n{claim}\n\nВІДПОВІДЬ:\n{answer}"
    )


def parse_faithfulness_response(text: str) -> list[ClaimVerdict]:
    data = _extract_json(text)
    return [
        ClaimVerdict(claim=c["claim"], supported=bool(c["supported"]), reason=c.get("reason", ""))
        for c in data.get("claims", [])
    ]


def parse_refusal_response(text: str) -> bool:
    return bool(_extract_json(text)["refused"])


def parse_completeness_response(text: str) -> tuple[bool, str]:
    data = _extract_json(text)
    return bool(data["covered"]), data.get("reason", "")
