"""Unit tests for Azure classification and the stable local fallback."""

from unittest.mock import Mock, patch

import pytest

from api.shared.categories import GENERAL_ENQUIRY
from api.shared.classifier import (
    classifier_chain,
    classify_ticket,
    classify_with_azure,
    classify_with_keywords,
)
from api.shared.config import AzureLanguageSettings, get_azure_language_settings


AZURE_ENVIRONMENT_VARIABLES = (
    "AZURE_LANGUAGE_ENDPOINT",
    "AZURE_LANGUAGE_KEY",
    "AZURE_LANGUAGE_API_VERSION",
    "AZURE_LANGUAGE_TIMEOUT_SECONDS",
)


@pytest.fixture(autouse=True)
def clean_azure_environment(monkeypatch):
    """Local developer credentials must never make unit tests call Azure."""
    for variable in AZURE_ENVIRONMENT_VARIABLES:
        monkeypatch.delenv(variable, raising=False)


def azure_settings(**overrides):
    values = {
        "endpoint": "https://example.cognitiveservices.azure.com",
        "key": "test-key",
        "api_version": "2024-11-01",
        "timeout_seconds": 1.0,
    }
    values.update(overrides)
    return AzureLanguageSettings(**values)


def azure_key_phrase_response(*phrases, errors=None):
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "kind": "KeyPhraseExtractionResults",
        "results": {
            "documents": [
                {"id": "1", "keyPhrases": list(phrases), "warnings": []}
            ],
            "errors": errors or [],
            "modelVersion": "2024-11-01",
        },
    }
    return response


@pytest.mark.parametrize(
    "title,description,expected",
    [
        ("Campus Wi-Fi unavailable", "My laptop cannot connect to the network.", "IT Support"),
        ("Password reset", "I cannot log in to my student account.", "IT Support"),
        ("Air conditioning broken", "The lecture hall is extremely hot.", "Facilities"),
        ("Lift not working", "The elevator in the main building is stuck.", "Facilities"),
        ("Module registration", "I need to register for a course this semester.", "Course Registration"),
        ("Timetable clash", "Two classes are scheduled at the same time.", "Course Registration"),
        ("Tuition fee problem", "My payment is missing from the fee statement.", "Student Finance"),
        ("Request a refund", "I was double charged for tuition.", "Student Finance"),
        ("Overdue library book", "I need to renew my book loan.", "Library Services"),
        ("Journal access", "The library research database will not show an article.", "Library Services"),
    ],
)
def test_keyword_fallback_handles_multiple_ticket_types(title, description, expected):
    result = classify_ticket(title, description)
    assert result["category"] == expected
    assert result["method"] == "keyword-rules"


@pytest.mark.parametrize(
    "text,expected",
    [
        ("I need to apply for a student loan", "Student Finance"),
        ("Please renew my book loan", "Library Services"),
        ("There is a tuition fee on my invoice", "Student Finance"),
        ("I have an overdue library fine", "Library Services"),
    ],
)
def test_contextual_phrases_resolve_ambiguous_terms(text, expected):
    assert classify_with_keywords(text)["category"] == expected


def test_genuine_tie_returns_general_enquiry_instead_of_category_order():
    result = classify_with_keywords("The printer is broken")
    assert result["category"] == GENERAL_ENQUIRY
    assert result["confidence"] == 0.35


def test_no_matching_keywords_returns_general_enquiry():
    result = classify_ticket("Question", "Where can I find information about graduation?")
    assert result == {
        "category": "General Enquiry",
        "confidence": 0.30,
        "method": "keyword-rules",
        "evidence": [],
    }


def test_empty_ticket_still_returns_the_stable_contract():
    result = classify_ticket("", "")
    assert set(result) == {"category", "confidence", "method", "evidence"}
    assert isinstance(result["category"], str)
    assert isinstance(result["confidence"], float)
    assert isinstance(result["method"], str)
    assert isinstance(result["evidence"], list)


def test_case_does_not_change_classification():
    lower = classify_with_keywords("campus wifi password reset")
    upper = classify_with_keywords("CAMPUS WIFI PASSWORD RESET")
    assert lower == upper


@pytest.mark.parametrize(
    "text",
    [
        "wifi",
        "water leak in a classroom",
        "register for a module",
        "tuition invoice",
        "overdue library book",
        "unrecognised words only",
        "the printer is broken",
    ],
)
def test_keyword_confidence_stays_between_zero_and_one(text):
    confidence = classify_with_keywords(text)["confidence"]
    assert 0.0 <= confidence <= 1.0


def test_injected_azure_provider_uses_the_same_contract():
    provider = Mock(return_value={
        "category": "Facilities",
        "confidence": 0.934,
        "method": "azure-ai-language-keyphrase",
        "evidence": ["key phrase: lift problem"],
        "ignored": "provider-specific data",
    })

    result = classify_ticket("Lift problem", "The lift is stuck.", provider)

    provider.assert_called_once()
    assert result == {
        "category": "Facilities",
        "confidence": 0.93,
        "method": "azure-ai-language-keyphrase",
        "evidence": ["key phrase: lift problem"],
    }


@pytest.mark.parametrize(
    "provider_result",
    [
        None,
        {"category": "Unknown", "confidence": 0.9, "method": "azure"},
        {"category": "IT Support", "confidence": 2.0, "method": "azure"},
        {"category": "IT Support", "confidence": 0.9, "method": ""},
        {"category": "IT Support", "confidence": 0.9, "method": "azure", "evidence": "wifi"},
    ],
)
def test_invalid_azure_result_falls_back_to_keywords(provider_result):
    provider = Mock(return_value=provider_result)
    result = classify_ticket("Wi-Fi problem", "Campus wifi is unavailable.", provider)
    assert result["category"] == "IT Support"
    assert result["method"] == "keyword-rules"


def test_azure_exception_falls_back_to_keywords():
    provider = Mock(side_effect=TimeoutError("Azure request timed out"))
    result = classify_ticket("Fee question", "My tuition invoice is incorrect.", provider)
    assert result["category"] == "Student Finance"
    assert result["method"] == "keyword-rules"


def test_azure_key_phrases_are_mapped_through_the_local_ontology():
    settings = azure_settings()

    with patch(
        "api.shared.classifier.requests.post",
        return_value=azure_key_phrase_response("broken lift", "lecture hall"),
    ) as post:
        result = classify_with_azure("The room is hot.", settings)

    assert result["category"] == "Facilities"
    assert result["method"] == "azure-ai-language-keyphrase"
    assert 0.0 <= result["confidence"] <= 1.0
    assert "key phrase: broken lift" in result["evidence"]
    assert post.call_args.args[0].endswith("/language/:analyze-text")
    assert post.call_args.kwargs["params"] == {"api-version": "2024-11-01"}
    assert post.call_args.kwargs["json"] == {
        "kind": "KeyPhraseExtraction",
        "parameters": {"modelVersion": "latest"},
        "analysisInput": {
            "documents": [
                {"id": "1", "language": "en", "text": "The room is hot."}
            ]
        },
    }


def test_azure_mapping_uses_key_phrases_that_contain_ontology_terms():
    with patch(
        "api.shared.classifier.requests.post",
        return_value=azure_key_phrase_response("outstanding balance"),
    ):
        result = classify_with_azure("Please help with this issue.", azure_settings())

    assert result["category"] == "Student Finance"
    assert result["method"] == "azure-ai-language-keyphrase"
    assert "outstanding balance" in result["evidence"]


def test_azure_mapping_also_uses_the_original_ticket_text():
    with patch(
        "api.shared.classifier.requests.post",
        return_value=azure_key_phrase_response("urgent issue"),
    ):
        result = classify_with_azure(
            "My tuition invoice is incorrect.", azure_settings()
        )

    assert result["category"] == "Student Finance"
    assert result["method"] == "azure-ai-language-keyphrase"


def test_successful_unmatched_key_phrases_return_general_enquiry():
    with patch(
        "api.shared.classifier.requests.post",
        return_value=azure_key_phrase_response("graduation information"),
    ):
        result = classify_with_azure("Where can I find details?", azure_settings())

    assert result == {
        "category": "General Enquiry",
        "confidence": 0.35,
        "method": "azure-ai-language-keyphrase",
        "evidence": ["key phrase: graduation information"],
    }


def test_empty_key_phrase_list_still_maps_the_original_ticket_text():
    with patch(
        "api.shared.classifier.requests.post",
        return_value=azure_key_phrase_response(),
    ):
        result = classify_with_azure("Campus wifi is unavailable.", azure_settings())

    assert result["category"] == "IT Support"
    assert result["method"] == "azure-ai-language-keyphrase"


def test_azure_document_errors_are_rejected_for_fallback():
    error = {"id": "1", "error": {"code": "InvalidDocument", "message": "bad"}}
    with patch(
        "api.shared.classifier.requests.post",
        return_value=azure_key_phrase_response(errors=[error]),
    ):
        with pytest.raises(ValueError, match="document errors"):
            classify_with_azure("A vague problem", azure_settings())


def test_automatic_azure_failure_falls_back_without_blocking_ticket():
    settings = azure_settings()
    with patch(
        "api.shared.classifier.get_azure_language_settings",
        return_value=settings,
    ), patch(
        "api.shared.classifier.requests.post",
        side_effect=TimeoutError("service timeout"),
    ):
        result = classify_ticket(
            "Cannot access Wi-Fi",
            "My laptop cannot connect to campus wifi.",
        )

    assert result["category"] == "IT Support"
    assert result["method"] == "keyword-rules"


def test_classifier_chain_reflects_configuration_without_network_call():
    assert classifier_chain(azure_settings()) == [
        "azure-ai-language-keyphrase",
        "keyword-rules",
    ]
    assert classifier_chain(azure_settings(key="")) == ["keyword-rules"]


def test_language_settings_are_safe_when_numeric_values_are_invalid(monkeypatch):
    monkeypatch.setenv("AZURE_LANGUAGE_TIMEOUT_SECONDS", "not-a-number")

    settings = get_azure_language_settings()

    assert settings.timeout_seconds == 6.0


def test_language_configuration_only_requires_endpoint_and_key(monkeypatch):
    monkeypatch.setenv(
        "AZURE_LANGUAGE_ENDPOINT",
        "https://example.cognitiveservices.azure.com/",
    )
    monkeypatch.setenv("AZURE_LANGUAGE_KEY", "local-test-key")

    settings = get_azure_language_settings()

    assert settings.configured is True
    assert settings.endpoint == "https://example.cognitiveservices.azure.com"
    assert settings.api_version == "2024-11-01"
