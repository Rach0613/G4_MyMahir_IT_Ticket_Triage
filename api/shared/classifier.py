"""Azure key-phrase ticket classification with an offline fallback.

Azure AI Language extracts key phrases synchronously.  The local ontology maps
those phrases and the original ticket text to the project's six categories.
Any Azure/configuration failure falls back to deterministic keyword rules.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Callable, Mapping
from typing import Any

import requests

from .categories import CATEGORIES, GENERAL_ENQUIRY, confidence_from_scores, score_text
from .config import AzureLanguageSettings, get_azure_language_settings

log = logging.getLogger("tickettriage.classifier")

ClassificationResult = dict[str, Any]
AzureClassifier = Callable[[str], Mapping[str, Any]]
AZURE_METHOD = "azure-ai-language-keyphrase"
KEY_PHRASE_WEIGHT = 1.5


def _result(
    category: str,
    confidence: float,
    method: str,
    evidence: list[str] | tuple[str, ...] | None = None,
) -> ClassificationResult:
    """Build the exact result shape consumed by the backend."""
    unique_evidence = list(dict.fromkeys(str(item) for item in (evidence or []) if str(item)))
    return {
        "category": category,
        "confidence": round(max(0.0, min(1.0, float(confidence))), 2),
        "method": method,
        "evidence": unique_evidence,
    }


def _normalise_provider_result(payload: Mapping[str, Any]) -> ClassificationResult:
    """Validate an injected Azure provider while preserving our public contract."""
    if not isinstance(payload, Mapping):
        raise ValueError("Classifier provider returned a non-object result.")

    category = payload.get("category")
    method = payload.get("method")
    evidence = payload.get("evidence", [])

    if category not in CATEGORIES:
        raise ValueError(f"Classifier provider returned unknown category {category!r}.")
    if not isinstance(method, str) or not method.strip():
        raise ValueError("Classifier provider did not identify its method.")
    if not isinstance(evidence, (list, tuple)):
        raise ValueError("Classifier provider evidence must be a list.")

    raw_confidence = payload.get("confidence")
    if raw_confidence is None:
        raise ValueError("Classifier provider returned invalid confidence.")

    try:
        confidence = float(raw_confidence)
    except (TypeError, ValueError) as exc:
        raise ValueError("Classifier provider returned invalid confidence.") from exc
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        raise ValueError("Classifier provider confidence must be between 0 and 1.")

    return _result(category, confidence, method.strip(), evidence)


def classify_with_keywords(text: str) -> ClassificationResult:
    """Classify text locally with deterministic weighted keyword rules."""
    scored = score_text(text)
    plain_scores = {
        category: int(details["score"])
        for category, details in scored.items()
    }
    top_score = max(plain_scores.values(), default=0)

    if top_score == 0:
        return _result(GENERAL_ENQUIRY, 0.30, "keyword-rules", [])

    winners = [
        category
        for category in CATEGORIES
        if plain_scores[category] == top_score
    ]

    # A genuine tie is evidence of uncertainty, so do not let category order
    # silently decide the result.  Human triage can resolve General Enquiry.
    if len(winners) != 1:
        tie_evidence: list[str] = []
        for category in winners:
            tie_evidence.extend(str(term) for term in scored[category]["matched"])
        return _result(GENERAL_ENQUIRY, 0.35, "keyword-rules", tie_evidence)

    winner = winners[0]
    evidence = [str(term) for term in scored[winner]["matched"]]
    confidence = confidence_from_scores(plain_scores)
    return _result(winner, confidence, "keyword-rules", evidence)


def classify_with_azure(
    text: str,
    settings: AzureLanguageSettings | None = None,
) -> ClassificationResult:
    """Extract Azure key phrases, then map them with the local ontology.

    Key Phrase Extraction does not return a category or confidence score.  The
    category and bounded heuristic confidence are therefore derived locally.
    Errors are raised to ``classify_ticket`` so ticket creation can fall back.
    """
    settings = settings or get_azure_language_settings()
    if not settings.configured:
        raise ValueError("Azure AI Language key phrase extraction is not configured.")

    response = requests.post(
        f"{settings.endpoint}/language/:analyze-text",
        params={"api-version": settings.api_version},
        headers={
            "Ocp-Apim-Subscription-Key": settings.key,
            "Content-Type": "application/json",
        },
        json={
            "kind": "KeyPhraseExtraction",
            "parameters": {"modelVersion": "latest"},
            "analysisInput": {
                "documents": [
                    {"id": "1", "language": "en", "text": (text or "")[:5000]}
                ]
            },
        },
        timeout=settings.timeout_seconds,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, Mapping):
        raise ValueError("Azure key phrase extraction returned a non-object response.")

    results = payload.get("results", {})
    if not isinstance(results, Mapping):
        raise ValueError("Azure key phrase extraction returned invalid results.")
    if results.get("errors"):
        raise ValueError("Azure key phrase extraction returned document errors.")

    documents = results.get("documents", [])
    if not documents:
        raise ValueError("Azure key phrase extraction returned no document results.")
    document = documents[0]
    if not isinstance(document, Mapping):
        raise ValueError("Azure key phrase extraction returned an invalid document.")

    raw_phrases = document.get("keyPhrases", [])
    if not isinstance(raw_phrases, list):
        raise ValueError("Azure key phrase extraction returned invalid key phrases.")
    key_phrases = list(
        dict.fromkeys(
            phrase.strip()
            for phrase in raw_phrases
            if isinstance(phrase, str) and phrase.strip()
        )
    )

    text_scores = score_text(text)
    phrase_scores = score_text(". ".join(key_phrases))
    combined_scores = {
        category: float(text_scores[category]["score"])
        + KEY_PHRASE_WEIGHT * float(phrase_scores[category]["score"])
        for category in CATEGORIES
    }
    top_score = max(combined_scores.values(), default=0.0)
    winners = [
        category for category in CATEGORIES if combined_scores[category] == top_score
    ]

    phrase_evidence = [f"key phrase: {phrase}" for phrase in key_phrases]
    if top_score == 0 or len(winners) != 1:
        return _result(GENERAL_ENQUIRY, 0.35, AZURE_METHOD, phrase_evidence)

    category = winners[0]
    matched_terms = [
        str(term)
        for term in (
            list(text_scores[category]["matched"])
            + list(phrase_scores[category]["matched"])
        )
    ]

    return _result(
        category,
        confidence_from_scores(combined_scores),
        AZURE_METHOD,
        phrase_evidence + matched_terms,
    )


def classifier_chain(
    settings: AzureLanguageSettings | None = None,
) -> list[str]:
    """Report the configured cascade without making an Azure request."""
    settings = settings or get_azure_language_settings()
    chain = []
    if settings.configured:
        chain.append(AZURE_METHOD)
    chain.append("keyword-rules")
    return chain


def classify_ticket(
    title: str,
    description: str,
    azure_classifier: AzureClassifier | None = None,
) -> ClassificationResult:
    """Classify a ticket, using Azure key phrases before keyword fallback.

    The injectable provider hook keeps tests isolated and preserves the plain
    result contract used by the backend and persistence fields.
    """
    text = f"{title or ''}. {description or ''}".strip()

    provider = azure_classifier
    if provider is None:
        settings = get_azure_language_settings()
        if settings.configured:
            provider = lambda candidate: classify_with_azure(candidate, settings)

    if provider is not None:
        try:
            return _normalise_provider_result(provider(text))
        except Exception as exc:  # noqa: BLE001 - fallback must keep submission available
            log.warning("Azure classifier unavailable; using keyword fallback: %s", exc)

    return classify_with_keywords(text)


# Short alias for callers that prefer the conventional classifier name.
classify = classify_ticket
