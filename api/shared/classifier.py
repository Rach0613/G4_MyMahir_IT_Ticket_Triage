"""Stable ticket-classification contract with an offline fallback.

Azure AI Language can later be supplied as a callable provider.  This module
validates the provider's result and falls back to deterministic keyword rules
if the provider is absent, unavailable, or returns an unusable response.
"""

from __future__ import annotations

import logging
import math
import time
from collections.abc import Callable, Mapping
from typing import Any

import requests

from .categories import CATEGORIES, GENERAL_ENQUIRY, confidence_from_scores, score_text
from .config import AzureLanguageSettings, get_azure_language_settings

log = logging.getLogger("tickettriage.classifier")

ClassificationResult = dict[str, Any]
AzureClassifier = Callable[[str], Mapping[str, Any]]


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

    try:
        confidence = float(payload.get("confidence"))
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
    """Classify text with an Azure custom single-label deployment.

    Azure returns this operation asynchronously.  Any HTTP, timeout, response,
    label, or confidence error is deliberately raised to ``classify_ticket``,
    which keeps ticket submission available by invoking the keyword fallback.
    """
    settings = settings or get_azure_language_settings()
    if not settings.configured:
        raise ValueError("Azure AI Language custom classification is not configured.")

    submit = requests.post(
        f"{settings.endpoint}/language/analyze-text/jobs",
        params={"api-version": settings.api_version},
        headers={
            "Ocp-Apim-Subscription-Key": settings.key,
            "Content-Type": "application/json",
        },
        json={
            "displayName": "Ticket classification",
            "analysisInput": {
                "documents": [
                    {"id": "1", "language": "en", "text": (text or "")[:5000]}
                ]
            },
            "tasks": [
                {
                    "kind": "CustomSingleLabelClassification",
                    "taskName": "TicketCategory",
                    "parameters": {
                        "projectName": settings.project_name,
                        "deploymentName": settings.deployment_name,
                    },
                }
            ],
        },
        timeout=settings.timeout_seconds,
    )
    submit.raise_for_status()

    operation_url = (
        submit.headers.get("operation-location")
        or submit.headers.get("Operation-Location")
    )
    if not operation_url:
        raise ValueError("Azure classification did not return an operation location.")

    deadline = time.monotonic() + settings.timeout_seconds
    payload: Mapping[str, Any] = {}
    while time.monotonic() < deadline:
        poll = requests.get(
            operation_url,
            headers={"Ocp-Apim-Subscription-Key": settings.key},
            timeout=settings.timeout_seconds,
        )
        poll.raise_for_status()
        payload = poll.json()
        state = str(payload.get("status", "")).lower()

        if state == "succeeded":
            break
        if state in {"failed", "cancelled"}:
            raise ValueError(f"Azure classification job ended with status {state}.")

        remaining = deadline - time.monotonic()
        if remaining > 0:
            time.sleep(min(0.25, remaining))
    else:
        raise TimeoutError("Azure classification job did not finish before the timeout.")

    task_items = payload.get("tasks", {}).get("items", [])
    if not task_items:
        raise ValueError("Azure classification returned no task results.")
    documents = task_items[0].get("results", {}).get("documents", [])
    if not documents:
        raise ValueError("Azure classification returned no document results.")
    classes = documents[0].get("class", [])
    if not classes:
        raise ValueError("Azure classification returned no category prediction.")

    prediction = max(
        classes,
        key=lambda item: float(item.get("confidenceScore", 0.0)),
    )
    category = prediction.get("category")
    confidence = float(prediction.get("confidenceScore", 0.0))

    if category not in CATEGORIES:
        raise ValueError(f"Azure classification returned unknown category {category!r}.")
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        raise ValueError("Azure classification returned invalid confidence.")
    if confidence < settings.min_confidence:
        raise ValueError(
            "Azure classification confidence "
            f"{confidence:.2f} is below {settings.min_confidence:.2f}."
        )

    return _result(
        category,
        confidence,
        "azure-ai-language-custom",
        [f"model class: {category} ({confidence:.2f})"],
    )


def classifier_chain(
    settings: AzureLanguageSettings | None = None,
) -> list[str]:
    """Report the configured cascade without making an Azure request."""
    settings = settings or get_azure_language_settings()
    chain = []
    if settings.configured:
        chain.append("azure-ai-language-custom")
    chain.append("keyword-rules")
    return chain


def classify_ticket(
    title: str,
    description: str,
    azure_classifier: AzureClassifier | None = None,
) -> ClassificationResult:
    """Classify a ticket, using an optional Azure provider before fallback.

    The provider hook deliberately accepts and returns plain Python values.
    Adding the Azure REST implementation later therefore will not require any
    change to this function's result contract or to backend persistence fields.
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
