"""Judge prompt templates and verdict definitions for Task 13.5 extraction eval.

The judge (Opus 4.6) rates each extracted claim using a 6-value categorical
verdict. Ordinal mapping (0-3) provides a scalar `quality_score` for ranking.
"""
from __future__ import annotations

import json
import re

VERDICT_VALUES: tuple[str, ...] = (
    "exact_match",
    "faithful_paraphrase",
    "valid_but_metadata_error",
    "not_a_prediction",
    "truncated",
    "hallucination",
)

VERDICT_ORDINAL: dict[str, int] = {
    "exact_match": 3,
    "faithful_paraphrase": 3,
    "valid_but_metadata_error": 2,
    "not_a_prediction": 1,
    "truncated": 1,
    "hallucination": 0,
}


JUDGE_SYSTEM = """You are evaluating the quality of prediction extraction from Ukrainian/Russian political commentary posts.

A valid prediction must satisfy ALL FOUR criteria:
1. Refers to a FUTURE event or state (not present assessment, not past event)
2. Has a VERIFIABLE OUTCOME — a concrete condition that can be objectively checked as true or false later
3. Concerns EXTERNAL events (politics, war, economy, people, institutions) — NOT the author's own scheduled activities
4. Is SUBSTANTIVE — outcome must be genuinely uncertain or strategically/politically meaningful (NOT a known fact restated, NOT a mechanical logistical certainty, NOT a procedural inevitability)

Do NOT accept these as predictions (they superficially look like predictions but fail criteria above):

A. Slogans / rhetorical declarations without measurable outcomes (e.g. "Перемога буде за нами", "Військові злочинці понесуть відповідальність").
B. Author's own event announcements about broadcasts, courses, books, trips (e.g. "Завтра о 22:00 проведемо ефір").
C. Normative statements describing what SHOULD happen (e.g. "Потрібно посилити санкції", "Україна має змінити стратегію").
D. Vague forward statements without concrete criteria (e.g. "Найближчі тижні будуть переломними", "Ситуація скоро зміниться").
E. Analysis of present state or past events phrased with future-tense verbs for rhetorical effect (e.g. "Ця війна вже змінила світ").
F. Questions, calls to action, metaphors, sarcasm — these are not claims.
G. Non-substantive claims (fail criterion 4): mechanical logistics or restated known facts. Examples:
   - "К 14 января самолеты вернут дипломатов" — routine logistical schedule
   - "Трамп зможе вести переговори тільки після інавгурації 20 січня" — known constitutional fact, not a forecast
   - "Суд має винести рішення до кінця місяця" — procedural deadline
   These claims may be technically "future + verifiable + external" but their OUTCOME is mechanically determined and not strategically meaningful. Verdict: not_a_prediction.

Verification tests:
- Criterion 2: "Could an impartial fact-checker in 1 year objectively confirm or refute this?"
- Criterion 4: "Would a reader 1 year later actually CARE whether this came true?" If no — it's not substantive, verdict not_a_prediction.

For each extracted claim, assign exactly ONE of these six verdicts:

- exact_match: The claim is a verbatim or near-verbatim quote from the post AND is itself a valid prediction (passes all four criteria above) AND its prediction_date / target_date / topic metadata is correct.
- faithful_paraphrase: The claim is a semantically faithful rephrase of a valid prediction in the post AND metadata is correct. Minor rewording allowed.
- valid_but_metadata_error: The claim correctly identifies a valid prediction in the post, but the prediction_date, target_date, or topic metadata is wrong or inconsistent with the text.
- not_a_prediction: The claim text appears in the post but does NOT pass the four-criteria test (it's a slogan, announcement, normative, vague, present-tense rhetoric, non-substantive, etc. — categories A-G above).
- truncated: The claim is cut mid-sentence; the meaning is incomplete or distorted.
- hallucination: The claim text is NOT present in the post and cannot be reasonably derived from it. The extractor fabricated content.

Additionally, identify any predictions that ARE present in the post text but were NOT included in the extracted claims list. Report these as `missed_predictions`.

CONSISTENCY ANCHOR (critical): apply the EXACT SAME four-criteria standard to both extracted claims and missed predictions. If a passage in the post would receive verdict `not_a_prediction` when extracted (because it's a slogan, normative, vague, non-substantive, etc.), then it MUST NOT appear in `missed_predictions`. The `missed_predictions` list contains ONLY passages that would receive `exact_match` or `faithful_paraphrase` if extracted — i.e. genuine valid predictions. Before adding any item to `missed_predictions`, ask: "If an extractor had produced this exact text, would I rate it `exact_match`/`faithful_paraphrase`?" If no — exclude it.

Respond ONLY with raw JSON in this exact shape — do NOT wrap in markdown code fences:

{
  "per_claim": [
    {
      "claim_text": "<verbatim claim from input>",
      "verdict": "<one of the six verdict values>",
      "reasoning": "<one or two sentences explaining the verdict>"
    }
  ],
  "missed_predictions": [
    {
      "text_excerpt": "<short quote from the post that was missed>",
      "why_valid": "<one sentence explaining why this is a valid prediction>"
    }
  ]
}

If the extracted claims list is empty, return per_claim as an empty list and only populate missed_predictions if applicable.
"""


JUDGE_TEMPLATE = """Post published on {published_date}:
---
{post_text}
---

The following claims were extracted by an LLM from the post:

{claims_block}

For each claim above, output a verdict per the rubric. Also identify any predictions in the post that the extractor missed.
"""


def build_judge_prompt(
    post_text: str, published_date: str, extracted_claims: list[dict]
) -> str:
    """Render the user-message judge prompt for a given post + claims."""
    if not extracted_claims:
        claims_block = "(no claims extracted — list is empty)"
    else:
        lines = []
        for idx, claim in enumerate(extracted_claims, start=1):
            lines.append(
                f"{idx}. \"{claim.get('claim_text', '')}\" "
                f"(prediction_date: {claim.get('prediction_date')}, "
                f"target_date: {claim.get('target_date')}, "
                f"topic: {claim.get('topic')})"
            )
        claims_block = "\n".join(lines)

    return JUDGE_TEMPLATE.format(
        post_text=post_text,
        published_date=published_date,
        claims_block=claims_block,
    )


_CODE_FENCE_RE = re.compile(
    r"^\s*```(?:json|JSON)?\s*\n?(.*?)\n?\s*```\s*$",
    re.DOTALL,
)


def _strip_code_fence(text: str) -> str:
    """Strip markdown code fences if present. Preserves content otherwise."""
    match = _CODE_FENCE_RE.match(text.strip())
    if match:
        return match.group(1).strip()
    return text.strip()


def parse_judge_response(response: str) -> dict:
    """Parse Opus judge output into normalized dict.

    Returns dict with keys:
        per_claim: list of {claim_text, verdict, reasoning, [verdict_invalid]}
        missed_predictions: list of {text_excerpt, why_valid}
        parse_error: str or None — populated when JSON is malformed

    Unknown verdict values are preserved with `verdict_invalid: True` flag,
    so the aggregator can count them separately. Malformed JSON returns
    empty lists with parse_error populated.

    Tolerates two real-world Opus 4.6 output deviations from raw JSON:
        1. Markdown code fences (```json ... ```)
        2. Leading preamble text before the JSON object
        3. Trailing explanation text after the JSON object
    Strategy: strip fences → find first `{` → use raw_decode from there.
    """
    text = _strip_code_fence(response)
    # Skip any leading non-JSON text — find the first `{`
    first_brace = text.find("{")
    if first_brace > 0:
        text = text[first_brace:]
    try:
        data, _consumed = json.JSONDecoder().raw_decode(text)
    except (json.JSONDecodeError, AttributeError, TypeError) as e:
        return {
            "per_claim": [],
            "missed_predictions": [],
            "parse_error": f"{type(e).__name__}: {e}",
        }

    per_claim = data.get("per_claim", []) or []
    missed = data.get("missed_predictions", []) or []

    # Flag unknown verdicts but preserve them for diagnosis
    for item in per_claim:
        if item.get("verdict") not in VERDICT_VALUES:
            item["verdict_invalid"] = True

    return {
        "per_claim": per_claim,
        "missed_predictions": missed,
        "parse_error": None,
    }
