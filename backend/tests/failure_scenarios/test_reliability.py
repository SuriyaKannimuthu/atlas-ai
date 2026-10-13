"""Failure injection: transient faults, dead evidence sources, crashes, and cancellation."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import ExitStack
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.graph import nodes
from app.main import build_container, create_app
from app.persistence.repository import IncidentRepository
from app.security.policy import Principal, Role
from tests.conftest import CHECKOUT, headers


def run(settings: Settings, description: str = CHECKOUT) -> tuple[dict, list[dict]]:
    with TestClient(create_app(settings)) as client:
        incident = client.post(
            "/api/v1/incidents", json={"description": description}, headers=headers("operator")
        ).json()
        events = client.get(
            f"/api/v1/incidents/{incident['id']}/events", headers=headers("viewer")
        ).json()["items"]
        return incident, events


def test_transient_tool_failures_are_retried(make_settings: Callable[..., Settings]) -> None:
    incident, events = run(make_settings(fault_injection="logs.search:transient:2"))
    assert incident["status"] == "awaiting_approval"
    retries = [e for e in events if e["type"] == "tool_retry"]
    assert len(retries) == 2 and all(e["payload"]["tool"] == "logs.search" for e in retries)


def test_dead_evidence_source_degrades_instead_of_failing(
    make_settings: Callable[..., Settings],
) -> None:
    incident, events = run(make_settings(fault_injection="logs.search:permanent:10"))
    assert incident["status"] == "awaiting_approval"
    assert [e for e in events if e["type"] == "step_failed"]
    with TestClient(create_app(make_settings())) as client:
        report = client.get(
            f"/api/v1/incidents/{incident['id']}/report", headers=headers("viewer")
        ).json()["report"]
    # Without logs the platform must not claim a confirmed root cause or propose a rollback.
    assert report["status"] != "root_cause_identified"
    assert any("Log data" in u for u in report["unknowns"])


class SimulatedCrash(BaseException):
    """Escapes `except Exception`, like a killed process would."""


def test_resumes_from_checkpoint_after_crash(
    make_settings: Callable[..., Settings], monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = make_settings()
    original_review = nodes.NODES["review"]

    def crash(_state: dict[str, Any], _ctx: Any) -> dict[str, Any]:
        raise SimulatedCrash()

    monkeypatch.setitem(nodes.NODES, "review", crash)
    with ExitStack() as stack:
        container = build_container(settings, stack)
        with pytest.raises(SimulatedCrash):
            container.service.submit(Principal("oscar", Role.OPERATOR), CHECKOUT, {})
        (incident,) = container.repo.list()
        incident_id = incident.id
        assert incident.status == "running"

    monkeypatch.setitem(nodes.NODES, "review", original_review)
    with TestClient(create_app(settings)) as client:  # startup recovery resumes the run
        detail = client.get(f"/api/v1/incidents/{incident_id}", headers=headers("viewer")).json()
        events = client.get(
            f"/api/v1/incidents/{incident_id}/events", headers=headers("viewer")
        ).json()["items"]

    assert detail["status"] == "awaiting_approval"
    assert "workflow_recovered" in [e["type"] for e in events]
    triage_runs = [e for e in events if e["type"] == "node_started" and e["node"] == "triage"]
    assert len(triage_runs) == 1, "completed nodes must not re-run after recovery"


def test_cancellation_stops_at_next_node_boundary(
    make_settings: Callable[..., Settings], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(IncidentRepository, "is_cancel_requested", lambda _self, _id: True)
    incident, events = run(make_settings())
    assert incident["status"] == "cancelled"
    assert not [e for e in events if e["type"] == "node_completed"]


def test_tool_budget_bounds_the_investigation(make_settings: Callable[..., Settings]) -> None:
    incident, events = run(make_settings(max_tool_calls=3))
    assert incident["status"] in {"awaiting_approval", "completed"}
    assert incident["metrics"]["tool_calls"] <= 3
    assert [e for e in events if e["type"] == "step_failed"]
