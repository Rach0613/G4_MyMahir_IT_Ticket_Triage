"""Tests for the category ontology and confidence calculation."""

import pytest

from api.shared.categories import (
    CATEGORIES,
    GENERAL_ENQUIRY,
    ONTOLOGY,
    confidence_from_scores,
    score_text,
)


def test_categories_are_exactly_the_backend_contract():
    assert CATEGORIES == (
        "IT Support",
        "Facilities",
        "Course Registration",
        "Student Finance",
        "Library Services",
        "General Enquiry",
    )


def test_every_category_has_one_ontology_entry():
    assert set(ONTOLOGY) == set(CATEGORIES)
    assert all(not terms for terms in ONTOLOGY[GENERAL_ENQUIRY].values())


def test_terms_are_normalised_and_unique_within_each_category():
    for category, buckets in ONTOLOGY.items():
        terms = [term for values in buckets.values() for term in values]
        assert all(term == term.strip().lower() for term in terms), category
        assert len(terms) == len(set(terms)), category


def test_matching_is_case_insensitive():
    assert score_text("CAMPUS WIFI") == score_text("campus wifi")


def test_short_keywords_respect_word_boundaries():
    assert score_text("payload") ["Student Finance"]["score"] == 0
    assert score_text("bookkeeping")["Library Services"]["score"] == 0
    assert score_text("I need to pay")["Student Finance"]["score"] > 0


def test_ambiguous_printer_scores_more_than_one_category():
    scores = score_text("The printer is broken")
    assert scores["IT Support"]["score"] > 0
    assert scores["Facilities"]["score"] > 0


@pytest.mark.parametrize(
    "scores",
    [
        {},
        {"a": 0, "b": 0},
        {"a": 1, "b": 0},
        {"a": 3, "b": 3},
        {"a": 50, "b": 1},
    ],
)
def test_confidence_is_always_bounded(scores):
    confidence = confidence_from_scores(scores)
    assert 0.0 <= confidence <= 1.0


def test_no_evidence_has_low_confidence():
    assert confidence_from_scores({category: 0 for category in CATEGORIES}) == 0.30
