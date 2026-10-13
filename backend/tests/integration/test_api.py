from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from tests.conftest import AUTH, CHECKOUT, PAYMENTS, headers


def submit(client: TestClient, description: str, role: str = "operator", **hints: Any) -> dict:
    response = client.post(
        "/api/v1/incidents", json={"description": description, **hints}, headers=headers(role)
    )
    assert response.status_code == 202, response.text
    return response.json()


def test_health(client: TestClient) -> None:
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["model"] == "offline-heuristics"


def test_requires_api_key(client: TestClient) -> None:
    assert client.get("/api/v1/incidents").status_code == 401
    assert client.get("/api/v1/incidents", headers={"X-API-Key": "nope"}).status_code == 401


def test_role_based_access(client: TestClient) -> None:
    body = {"description": CHECKOUT}
    assert client.post("/api/v1/incidents", json=body, headers=headers("viewer")).status_code == 403
    assert (
        client.post("/api/v1/incidents", json=body, headers=headers("approver")).status_code == 403
    )
    incident = submit(client, CHECKOUT)
    decision = {"decision": "approved"}
    url = f"/api/v1/incidents/{incident['id']}/approvals"
    assert client.post(url, json=decision, headers=headers("operator")).status_code == 403


def test_request_validation(client: TestClient) -> None:
    for body in (
        {"description": "short"},
        {"description": CHECKOUT, "deployment_id": "rm -rf /"},
        {"description": CHECKOUT, "unexpected": True},
    ):
        response = client.post("/api/v1/incidents", json=body, headers=headers("operator"))
        assert response.status_code == 422


def test_full_investigation_with_approval(client: TestClient) -> None:
    incident = submit(client, CHECKOUT)
    assert incident["status"] == "awaiting_approval"
    pending = incident["pending_approval"]
    assert {a["type"] for a in pending["actions"]} == {"create_ticket", "rollback_deployment"}

    draft = client.get(f"/api/v1/incidents/{incident['id']}/report", headers=headers("viewer"))
    assert draft.status_code == 200 and draft.json()["final"] is False
    report = draft.json()["report"]
    assert report["status"] == "root_cause_identified"
    assert report["root_cause"]["hypothesis_id"] == "H-c1a9f3e"
    evidence_ids = {e["id"] for e in report["evidence"]}
    assert set(report["root_cause"]["evidence_ids"]) <= evidence_ids
    assert report["security_notes"], "planted prompt injection in logs should be flagged"

    url = f"/api/v1/incidents/{incident['id']}/approvals"
    decided = client.post(
        url, json={"decision": "approved", "comment": "go"}, headers=headers("approver")
    )
    assert decided.status_code == 200
    assert decided.json()["status"] == "completed"
    # Decisions are recorded exactly once.
    again = client.post(url, json={"decision": "approved"}, headers=headers("approver"))
    assert again.status_code == 409

    final = client.get(f"/api/v1/incidents/{incident['id']}/report", headers=headers("viewer"))
    actions = {a["type"]: a["outcome"]["status"] for a in final.json()["report"]["actions"]}
    assert actions == {
        "create_ticket": "executed",
        "notify_channel": "executed",
        "rollback_deployment": "executed",
    }

    events = client.get(f"/api/v1/incidents/{incident['id']}/events", headers=headers("viewer"))
    types = [e["type"] for e in events.json()["items"]]
    assert types[0] == "workflow_queued"
    assert "approval_requested" in types and "workflow_completed" in types


def test_rejection_skips_gated_actions_only(client: TestClient) -> None:
    incident = submit(client, PAYMENTS)
    url = f"/api/v1/incidents/{incident['id']}/approvals"
    client.post(url, json={"decision": "rejected"}, headers=headers("approver"))
    report = client.get(f"/api/v1/incidents/{incident['id']}/report", headers=headers("viewer"))
    actions = {a["type"]: a["outcome"]["status"] for a in report.json()["report"]["actions"]}
    assert actions["rollback_deployment"] == "skipped"
    assert actions["create_ticket"] == "skipped"
    assert actions["notify_channel"] == "executed"


def test_ambiguous_incident_is_not_overclaimed(client: TestClient) -> None:
    incident = submit(client, AUTH)
    report = client.get(f"/api/v1/incidents/{incident['id']}/report", headers=headers("viewer"))
    body = report.json()["report"]
    assert body["status"] == "probable_cause"
    assert body["root_cause"]["kind"] == "infrastructure"
    assert body["unknowns"]
    assert "rollback_deployment" not in {a["type"] for a in incident["pending_approval"]["actions"]}


def test_cancel_while_awaiting_approval(client: TestClient) -> None:
    incident = submit(client, CHECKOUT)
    response = client.post(
        f"/api/v1/incidents/{incident['id']}/cancel", headers=headers("operator")
    )
    assert response.json()["status"] == "cancelled"
    assert response.json()["approvals"][0]["status"] == "expired"
    again = client.post(f"/api/v1/incidents/{incident['id']}/cancel", headers=headers("operator"))
    assert again.status_code == 409


def test_list_and_counts(client: TestClient) -> None:
    submit(client, CHECKOUT)
    body = client.get("/api/v1/incidents", headers=headers("viewer")).json()
    assert len(body["items"]) == 1
    assert body["counts"] == {"awaiting_approval": 1}


def test_separation_of_duties(make_settings: Callable[..., Settings]) -> None:
    with TestClient(create_app(make_settings(require_separation_of_duties=True))) as client:
        incident = submit(client, CHECKOUT, role="admin")
        url = f"/api/v1/incidents/{incident['id']}/approvals"
        assert (
            client.post(url, json={"decision": "approved"}, headers=headers("admin")).status_code
            == 403
        )
        assert (
            client.post(url, json={"decision": "approved"}, headers=headers("approver")).status_code
            == 200
        )


def test_rate_limit(make_settings: Callable[..., Settings]) -> None:
    with TestClient(create_app(make_settings(rate_limit_per_minute=1))) as client:
        submit(client, CHECKOUT)
        response = client.post(
            "/api/v1/incidents", json={"description": CHECKOUT}, headers=headers("operator")
        )
        assert response.status_code == 429


def test_me_reports_role(client: TestClient) -> None:
    body = client.get("/api/v1/me", headers=headers("approver")).json()
    assert body["subject"] == "april" and body["role"] == "approver"
    assert "action:approve" in body["permissions"]
