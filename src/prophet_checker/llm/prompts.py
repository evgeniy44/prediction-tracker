from __future__ import annotations

import json


EXTRACTION_SYSTEM = """You are an expert analyst who identifies predictions and forecasts in Ukrainian political commentary.
Extract specific, verifiable predictions from the given text.
A prediction is a statement about future events that can be verified as true or false.
Respond ONLY with valid JSON."""

EXTRACTION_TEMPLATE = """Analyze the following text by {person_name} (published on {published_date}).
Extract all predictions — statements about future events that can later be verified.

Text:
---
{text}
---

For each prediction, extract:
- claim_text: the exact prediction (in original language)
- prediction_date: when the prediction was made (YYYY-MM-DD)
- target_date: when the predicted event should happen (YYYY-MM-DD or null if unclear)
- topic: category (e.g., "війна", "економіка", "політика", "міжнародні відносини")

Respond with JSON:
{{"predictions": [{{"claim_text": "...", "prediction_date": "...", "target_date": "...", "topic": "..."}}]}}

If no predictions found, respond: {{"predictions": []}}"""


VERIFICATION_SYSTEM = """You are a fact-checker who verifies predictions against known events.
You must provide evidence for your verdict. If you cannot find clear evidence, mark as unresolved.
Respond ONLY with valid JSON."""

VERIFICATION_TEMPLATE = """Verify the following prediction:

Claim: "{claim}"
Made on: {prediction_date}
Expected by: {target_date}

Determine if this prediction came true based on known events.

Respond with JSON:
{{
  "status": "confirmed" | "refuted" | "unresolved",
  "confidence": 0.0 to 1.0,
  "evidence_url": "URL to supporting evidence or null",
  "evidence_text": "Brief explanation of why this status was assigned"
}}"""


RAG_SYSTEM = """You are Prophet Checker, an AI assistant that analyzes predictions made by Ukrainian public figures.
Answer questions based on the provided prediction data. Always cite sources and confidence scores.
Always add a disclaimer that analysis is automated and may contain inaccuracies.
Respond in Ukrainian."""

RAG_TEMPLATE = """Question: {question}

Relevant predictions from the database:
---
{predictions_context}
---

Based on this data, answer the user's question. Include:
- Specific predictions with dates
- Their verification status and confidence
- Overall accuracy statistics if relevant
- Disclaimer about automated analysis"""


def build_extraction_prompt(text: str, person_name: str, published_date: str) -> str:
    return EXTRACTION_TEMPLATE.format(
        text=text, person_name=person_name, published_date=published_date,
    )


def build_verification_prompt(claim: str, prediction_date: str, target_date: str | None) -> str:
    return VERIFICATION_TEMPLATE.format(
        claim=claim, prediction_date=prediction_date,
        target_date=target_date or "not specified",
    )


def build_rag_prompt(question: str, predictions_context: list[dict]) -> str:
    context_str = "\n".join(
        f"- {p['claim_text']} [status: {p['status']}, confidence: {p['confidence']}]"
        for p in predictions_context
    )
    return RAG_TEMPLATE.format(question=question, predictions_context=context_str)


def parse_extraction_response(response: str) -> list[dict]:
    try:
        data = json.loads(response)
        return data.get("predictions", [])
    except (json.JSONDecodeError, AttributeError):
        return []


def parse_verification_response(response: str) -> dict | None:
    try:
        data = json.loads(response)
        if "status" in data and "confidence" in data:
            return data
        return None
    except (json.JSONDecodeError, AttributeError):
        return None


def get_extraction_system() -> str:
    return EXTRACTION_SYSTEM


def get_verification_system() -> str:
    return VERIFICATION_SYSTEM


def get_rag_system() -> str:
    return RAG_SYSTEM
