"""Ticket categories and deterministic keyword scoring.

This module has no Azure or backend dependencies.  It provides the local
fallback used when Azure AI Language is not configured or cannot return a
usable classification.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import TypedDict


class CategoryScore(TypedDict):
    score: int
    matched: list[str]

IT_SUPPORT = "IT Support"
FACILITIES = "Facilities"
COURSE_REGISTRATION = "Course Registration"
STUDENT_FINANCE = "Student Finance"
LIBRARY_SERVICES = "Library Services"
GENERAL_ENQUIRY = "General Enquiry"

CATEGORIES: tuple[str, ...] = (
    IT_SUPPORT,
    FACILITIES,
    COURSE_REGISTRATION,
    STUDENT_FINANCE,
    LIBRARY_SERVICES,
    GENERAL_ENQUIRY,
)

BUCKET_WEIGHTS: Mapping[str, int] = {
    "phrases": 4,
    "strong": 3,
    "medium": 2,
    "weak": 1,
}

# Multi-word phrases carry the most weight so that contextual phrases such as
# "student loan" and "book loan" beat their ambiguous individual words.
ONTOLOGY: dict[str, dict[str, tuple[str, ...]]] = {
    IT_SUPPORT: {
        "phrases": (
            "campus wifi", "campus wi-fi", "cannot log in", "can not log in",
            "password reset", "reset my password", "account locked", "locked out",
            "no internet", "email not working", "two factor", "network drive",
            "blue screen", "will not connect", "won't connect",
        ),
        "strong": (
            "wifi", "wi-fi", "vpn", "password", "login", "laptop", "malware",
            "virus", "outlook", "moodle", "username", "authentication",
        ),
        "medium": (
            "internet", "network", "computer", "software", "printer", "email",
            "account", "browser", "server", "driver", "scanner",
        ),
        "weak": (
            "error", "crash", "crashed", "reset", "slow", "device", "screen",
            "freeze", "keyboard", "mouse",
        ),
    },
    FACILITIES: {
        "phrases": (
            "air conditioning", "air-conditioning", "lecture hall", "water leak",
            "broken chair", "broken door", "blocked toilet", "toilet blocked",
            "access card", "fire alarm", "car park", "vending machine",
        ),
        "strong": (
            "aircon", "hvac", "toilet", "plumbing", "leaking", "elevator",
            "lift", "cleaner", "cleaning", "cockroach", "furniture",
        ),
        "medium": (
            "classroom", "building", "maintenance", "repair", "light", "chair",
            "door", "window", "parking", "roof", "floor",
        ),
        "weak": (
            "broken", "damaged", "dirty", "noise", "hot", "cold", "leak",
            "bulb", "bin", "printer", "projector",
        ),
    },
    COURSE_REGISTRATION: {
        "phrases": (
            "course registration", "module registration", "add drop", "add or drop",
            "drop a course", "drop a module", "class timetable", "credit hours",
            "change my section", "waiting list", "wait list", "timetable clash",
            "register for", "enrol in", "enroll in",
        ),
        "strong": (
            "registration", "register", "enrol", "enroll", "enrolment",
            "enrollment", "timetable", "prerequisite", "elective", "withdrawal",
            "semester",
        ),
        "medium": (
            "course", "module", "subject", "class", "section", "schedule",
            "lecture", "tutorial", "faculty", "credit",
        ),
        "weak": ("add", "drop", "swap", "seat", "slot", "academic"),
    },
    STUDENT_FINANCE: {
        "phrases": (
            "student loan", "tuition fee", "tuition fees", "late payment",
            "payment plan", "financial aid", "outstanding balance", "fee statement",
            "proof of payment", "double charged", "charged twice", "bank transfer",
            "fee waiver",
        ),
        "strong": (
            "tuition", "invoice", "refund", "scholarship", "bursary", "billing",
            "ptptn", "receipt", "sponsorship", "reimbursement",
        ),
        "medium": (
            "fee", "fees", "payment", "balance", "charge", "charged", "finance",
            "financial", "bill", "penalty", "transaction",
        ),
        "weak": ("pay", "paid", "money", "cost", "bank", "card", "loan"),
    },
    LIBRARY_SERVICES: {
        "phrases": (
            "library book", "library books", "book loan", "borrowed book",
            "renew my book", "renew my loan", "overdue book", "library fine",
            "library card", "study room", "e-book", "e-books", "journal article",
            "research database", "return the book", "reserve a book",
        ),
        "strong": (
            "library", "librarian", "borrow", "borrowing", "overdue", "isbn",
            "catalogue", "catalog", "ebook", "journal", "citation",
        ),
        "medium": (
            "book", "books", "renew", "renewal", "return", "reserve", "shelf",
            "database", "article", "reading",
        ),
        "weak": ("loan", "fine", "due", "print", "author", "title"),
    },
    GENERAL_ENQUIRY: {
        "phrases": (),
        "strong": (),
        "medium": (),
        "weak": (),
    },
}


def _compile_ontology() -> dict[str, tuple[tuple[re.Pattern[str], int, str], ...]]:
    compiled: dict[str, tuple[tuple[re.Pattern[str], int, str], ...]] = {}
    for category, buckets in ONTOLOGY.items():
        entries: list[tuple[re.Pattern[str], int, str]] = []
        for bucket, terms in buckets.items():
            weight = BUCKET_WEIGHTS[bucket]
            for term in terms:
                # Lookarounds work for both ordinary and hyphenated terms and
                # prevent short terms such as "pay" matching "payload".
                pattern = re.compile(
                    rf"(?<!\w){re.escape(term)}(?!\w)",
                    flags=re.IGNORECASE,
                )
                entries.append((pattern, weight, term))
        compiled[category] = tuple(entries)
    return compiled


_COMPILED_ONTOLOGY = _compile_ontology()


def score_text(text: str) -> dict[str, CategoryScore]:
    """Score text against every category and return matched evidence."""
    results: dict[str, CategoryScore] = {}
    candidate = text or ""

    for category, entries in _COMPILED_ONTOLOGY.items():
        score = 0
        matched: list[str] = []
        for pattern, weight, term in entries:
            if pattern.search(candidate):
                score += weight
                matched.append(term)
        results[category] = {"score": score, "matched": matched}

    return results


def confidence_from_scores(scores: Mapping[str, int | float]) -> float:
    """Return a deterministic confidence in the inclusive range 0..1."""
    ordered = sorted((max(0.0, float(value)) for value in scores.values()), reverse=True)
    top = ordered[0] if ordered else 0.0
    if top == 0:
        return 0.30

    second = ordered[1] if len(ordered) > 1 else 0.0
    saturation = min(1.0, top / 8.0)
    margin = max(0.0, (top - second) / top)
    confidence = 0.40 + (0.35 * saturation) + (0.25 * margin)
    return round(max(0.0, min(1.0, confidence)), 2)
