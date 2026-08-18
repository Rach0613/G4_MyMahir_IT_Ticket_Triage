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
    "AZURE_LANGUAGE_PROJECT_NAME",
    "AZURE_LANGUAGE_DEPLOYMENT_NAME",
    "AZURE_LANGUAGE_API_VERSION",
    "AZURE_LANGUAGE_MIN_CONFIDENCE",
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
        "project_name": "TicketTriage",
        "deployment_name": "production",
        "api_version": "2024-11-01",
        "min_confidence": 0.55,
        "timeout_seconds": 1.0,
    }
    values.update(overrides)
    return AzureLanguageSettings(**values)


def azure_submit_response():
    response = Mock()
    response.headers = {
        "operation-location": "https://example.cognitiveservices.azure.com/jobs/123"
    }
    response.raise_for_status.return_value = None
    return response


def azure_result_response(category="Facilities", confidence=0.91, status="succeeded"):
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "status": status,
        "tasks": {
            "items": [
                {
                    "results": {
                        "documents": [
                            {
                                "id": "1",
                                "class": [
                                    {
                                        "category": category,
                                        "confidenceScore": confidence,
                                    }
                                ],
                            }
                        ]
                    }
                }
            ]
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
        "method": "azure-ai-language-custom",
        "evidence": ["model class: Facilities"],
        "ignored": "provider-specific data",
    })

    result = classify_ticket("Lift problem", "The lift is stuck.", provider)

    provider.assert_called_once()
    assert result == {
        "category": "Facilities",
        "confidence": 0.93,
        "method": "azure-ai-language-custom",
        "evidence": ["model class: Facilities"],
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


def test_azure_custom_classifier_returns_model_category_and_confidence():
    settings = azure_settings()

    with patch(
        "api.shared.classifier.requests.post",
        return_value=azure_submit_response(),
    ) as post, patch(
        "api.shared.classifier.requests.get",
        return_value=azure_result_response("Facilities", 0.91),
    ) as get:
        result = classify_with_azure("The lift is stuck.", settings)

    assert result == {
        "category": "Facilities",
        "confidence": 0.91,
        "method": "azure-ai-language-custom",
        "evidence": ["model class: Facilities (0.91)"],
    }
    assert post.call_args.kwargs["params"] == {"api-version": "2024-11-01"}
    assert post.call_args.kwargs["json"]["tasks"][0]["parameters"] == {
        "projectName": "TicketTriage",
        "deploymentName": "production",
    }
    assert get.call_args.args[0].endswith("/jobs/123")


def test_low_confidence_azure_prediction_is_rejected_for_fallback():
    with patch(
        "api.shared.classifier.requests.post",
        return_value=azure_submit_response(),
    ), patch(
        "api.shared.classifier.requests.get",
        return_value=azure_result_response("Facilities", 0.31),
    ):
        with pytest.raises(ValueError, match="below"):
            classify_with_azure("A vague problem", azure_settings(min_confidence=0.7))


def test_unknown_azure_category_is_rejected_for_fallback():
    with patch(
        "api.shared.classifier.requests.post",
        return_value=azure_submit_response(),
    ), patch(
        "api.shared.classifier.requests.get",
        return_value=azure_result_response("Parking Enforcement", 0.99),
    ):
        with pytest.raises(ValueError, match="unknown category"):
            classify_with_azure("A parking question", azure_settings())


def test_automatic_azure_failure_falls_back_without_blocking_ticket():
    settings = azure_settings()
    with patch(
        "api.shared.classifier.get_azure_language_settings",
        return_value=settings,
    ), patch(
        "api.shared.classifier.classify_with_azure",
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
        "azure-ai-language-custom",
        "keyword-rules",
    ]
    assert classifier_chain(azure_settings(key="")) == ["keyword-rules"]


def test_language_settings_are_safe_when_numeric_values_are_invalid(monkeypatch):
    monkeypatch.setenv("AZURE_LANGUAGE_MIN_CONFIDENCE", "not-a-number")
    monkeypatch.setenv("AZURE_LANGUAGE_TIMEOUT_SECONDS", "not-a-number")

    settings = get_azure_language_settings()

    assert settings.min_confidence == 0.55
    assert settings.timeout_seconds == 6.0
