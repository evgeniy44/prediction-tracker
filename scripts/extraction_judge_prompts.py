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

A valid prediction must satisfy ALL three criteria:
1. Refers to a FUTURE event or state (not present assessment, not past event)
2. Has a VERIFIABLE OUTCOME — a concrete condition that can be objectively checked as true or false later
3. Concerns EXTERNAL events (politics, war, economy, people, institutions) — NOT the author's own scheduled activities

Do NOT accept these as predictions (they superficially look like predictions but fail criteria above):

A. Slogans / rhetorical declarations without measurable outcomes (e.g. "Перемога буде за нами", "Військові злочинці понесуть відповідальність").
B. Author's own event announcements about broadcasts, courses, books, trips (e.g. "Завтра о 22:00 проведемо ефір").
C. Normative statements describing what SHOULD happen (e.g. "Потрібно посилити санкції", "Україна має змінити стратегію").
D. Vague forward statements without concrete criteria (e.g. "Найближчі тижні будуть переломними", "Ситуація скоро зміниться").
E. Analysis of present state or past events phrased with future-tense verbs for rhetorical effect (e.g. "Ця війна вже змінила світ").
F. Questions, calls to action, metaphors, sarcasm — these are not claims.

Verification test: ask "Could an impartial fact-checker in 1 year objectively confirm or refute this specific statement?" If the answer requires interpretation of vague terms — it's NOT a prediction.

For each extracted claim, assign exactly ONE of these six verdicts:

- exact_match: The claim is a verbatim or near-verbatim quote from the post AND is itself a valid prediction (passes all three criteria above) AND its prediction_date / target_date / topic metadata is correct.
- faithful_paraphrase: The claim is a semantically faithful rephrase of a valid prediction in the post AND metadata is correct. Minor rewording allowed.
- valid_but_metadata_error: The claim correctly identifies a valid prediction in the post, but the prediction_date, target_date, or topic metadata is wrong or inconsistent with the text.
- not_a_prediction: The claim text appears in the post but does NOT pass the three-criteria test (it's a slogan, announcement, normative, vague, present-tense rhetoric, etc. — categories A-F above).
- truncated: The claim is cut mid-sentence; the meaning is incomplete or distorted.
- hallucination: The claim text is NOT present in the post and cannot be reasonably derived from it. The extractor fabricated content.

Additionally, identify any predictions that ARE present in the post text but were NOT included in the extracted claims list. Report these as `missed_predictions`.

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
