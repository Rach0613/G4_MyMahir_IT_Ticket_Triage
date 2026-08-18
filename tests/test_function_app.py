"""Ticket-creation integration tests without Azure or Cosmos connections."""

from __future__ import annotations

import importlib
import json
import pathlib
import sys
import types
from unittest.mock import Mock

import azure.functions as func
import pytest


API_ROOT = pathlib.Path(__file__).resolve().parents[1] / "api"


@pytest.fixture()
def backend(monkeypatch):
    """Load function_app with its repository replaced before module import."""
    monkeypatch.syspath_prepend(str(API_ROOT))

    repository = types.ModuleType("shared.repository")
    repository.create_ticket = Mock(side_effect=lambda ticket: ticket)
    repository.get_all_tickets = Mock(return_value=[])
    repository.get_ticket_by_id = Mock(return_value=None)
    repository.update_ticket = Mock(return_value=None)
    monkeypatch.setitem(sys.modules, "shared.repository", repository)
    sys.modules.pop("function_app", None)

    module = importlib.import_module("function_app")
    yield module, repository
    sys.modules.pop("function_app", None)


def ticket_request(**overrides):
    payload = {
        "name": "Aiman Rahman",
        "email": "aiman@example.com",
        "title": "Cannot access campus Wi-Fi",
        "description": "My laptop cannot connect to the campus Wi-Fi network.",
        "priority": "Medium",
        "category": "",
    }
    payload.update(overrides)
    return func.HttpRequest(
        method="POST",
        url="http://localhost/api/tickets",
        body=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        params={},
        route_params={},
    )


def response_json(response):
    return json.loads(response.get_body().decode("utf-8"))


def test_ticket_creation_classifies_then_saves_existing_contract(backend):
    module, repository = backend
    module.classify_ticket = Mock(return_value={
        "category": "IT Support",
        "confidence": 0.94,
        "method": "azure-ai-language-custom",
        "evidence": ["model class: IT Support (0.94)"],
    })

    response = module.create_ticket(ticket_request())
    ticket = response_json(response)

    assert response.status_code == 201
    module.classify_ticket.assert_called_once_with(
        "Cannot access campus Wi-Fi",
        "My laptop cannot connect to the campus Wi-Fi network.",
    )
    assert ticket["category"] == "IT Support"
    assert ticket["suggestedCategory"] == "IT Support"
    assert ticket["categorySource"] == "auto"
    assert ticket["classificationMethod"] == "azure-ai-language-custom"
    assert ticket["classificationConfidence"] == 0.94
    assert ticket["classificationEvidence"] == ["model class: IT Support (0.94)"]
    repository.create_ticket.assert_called_once_with(ticket)


def test_manual_category_override_keeps_automatic_suggestion(backend):
    module, repository = backend
    module.classify_ticket = Mock(return_value={
        "category": "IT Support",
        "confidence": 0.88,
        "method": "keyword-rules",
        "evidence": ["wifi"],
    })

    response = module.create_ticket(ticket_request(category="Facilities"))
    ticket = response_json(response)

    assert response.status_code == 201
    assert ticket["category"] == "Facilities"
    assert ticket["suggestedCategory"] == "IT Support"
    assert ticket["categorySource"] == "manual"
    repository.create_ticket.assert_called_once_with(ticket)


def test_validation_failure_does_not_classify_or_save(backend):
    module, repository = backend
    module.classify_ticket = Mock()

    response = module.create_ticket(ticket_request(title=""))

    assert response.status_code == 400
    module.classify_ticket.assert_not_called()
    repository.create_ticket.assert_not_called()
