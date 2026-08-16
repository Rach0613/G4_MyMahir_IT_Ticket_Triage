"""Unit tests for the stable classifier and local fallback."""

from unittest.mock import Mock

import pytest

from api.shared.categories import GENERAL_ENQUIRY
from api.shared.classifier import classify_ticket, classify_with_keywords


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
