"""Incident Triage Agent: classify the incident and build a validated incident specification.

The model (when configured) interprets free text. Identifiers it returns - service names,
deployment IDs, timestamps - are then resolved against the catalog and deployment system
deterministically, so a hallucinated identifier can never steer the investigation.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Any

from app.agents.common import iso, parse_iso
from app.agents.schemas import IncidentSpec, TriageExtraction
from app.graph.context import WorkflowContext
from app.security.untrusted import UNTRUSTED_CONTENT_RULES, wrap_untrusted
from app.services.model_gateway import ModelUnavailableError

AGENT = "triage"

_DEPLOYMENT_ID = re.compile(r"\bd-\d{1,8}\b")
_ISO_TIME = re.compile(r"\b\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?)?(?:Z|\s?UTC)?")

_CATEGORY_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("security", ("breach", "unauthorized", "leak", "exfiltrat", "credential")),
    ("deployment_regression", ("deploy", "release", "rollout", "regression", "new version")),
    ("availability", ("outage", "down", "unavailable", "unreachable")),
    ("latency", ("latency", "slow", "p95", "p99", "timeout", "timing out")),
    ("error_spike", ("error", "5xx", "500", "502", "503", "exception", "failing", "failure")),
]

_SYMPTOM_PATTERNS = [
    (re.compile(r"\b5\d\d\b|5xx", re.I), "elevated HTTP 5xx responses"),
    (re.compile(r"latenc|slow|p9[59]", re.I), "increased latency"),
    (re.compile(r"timeout|timing out", re.I), "timeouts"),
    (re.compile(r"error", re.I), "increased error rate"),
    (re.compile(r"login|auth", re.I), "authentication flow affected"),
    (re.compile(r"payment|charge", re.I), "payment processing affected"),
    (re.compile(r"checkout", re.I), "checkout flow affected"),
]

SYSTEM_PROMPT = f"""You are the triage agent of an incident investigation platform.
Extract a structured incident specification from the operator's description.
Only use service names from the provided catalog; use null when unsure.
Do not speculate about root causes. {UNTRUSTED_CONTENT_RULES}"""


def run(state: dict[str, Any], ctx: WorkflowContext) -> dict[str, Any]:
    emit = ctx.emitter(AGENT)
    description: str = state["description"]
    hints: dict[str, Any] = state.get("hints") or {}
    catalog: list[dict] = ctx.call_tool(AGENT, "services.list", {})

    extraction = None
    if ctx.model.enabled:
        try:
            extraction = ctx.model.structured(
                TriageExtraction,
                system=SYSTEM_PROMPT,
                prompt=(
                    f"Service catalog: {', '.join(s['name'] for s in catalog)}\n\n"
                    f"{wrap_untrusted('operator_description', description)}"
                ),
                name="triage.extract",
                emit=emit,
            )
        except ModelUnavailableError:
            emit("agent_fallback", {"agent": AGENT, "reason": "model unavailable"})
    if extraction is None:
        extraction = heuristic_extraction(description, catalog)

    spec = resolve_spec(extraction, hints, catalog, ctx)
    return {"incident_spec": spec.model_dump()}


def heuristic_extraction(description: str, catalog: list[dict]) -> TriageExtraction:
    text = description.lower()
    category = next(
        (name for name, words in _CATEGORY_KEYWORDS if any(w in text for w in words)),
        "unknown",
    )
    symptoms = [label for pattern, label in _SYMPTOM_PATTERNS if pattern.search(description)]
    service = _match_service(text, catalog)
    severity = "sev2"
    if any(word in text for word in ("outage", "all users", "sev1", "down")):
        severity = "sev1"
    elif category in ("latency", "unknown"):
        severity = "sev3"
    keywords = sorted({w for w in re.findall(r"[a-z][a-z0-9_\-]{3,}", text) if w not in _STOP})[:12]
    deployment = _DEPLOYMENT_ID.search(description)
    time_match = _ISO_TIME.search(description)
    return TriageExtraction(
        summary=description.strip().split("\n")[0][:200],
        category=category,  # type: ignore[arg-type]
        severity=severity,  # type: ignore[arg-type]
        symptoms=symptoms[:8],
        keywords=keywords,
        service_name=service,
        deployment_id=deployment.group(0) if deployment else None,
        incident_time=time_match.group(0) if time_match else None,
    )


def resolve_spec(
    extraction: TriageExtraction, hints: dict[str, Any], catalog: list[dict], ctx: WorkflowContext
) -> IncidentSpec:
    by_name = {service["name"]: service for service in catalog}

    service_name = hints.get("service_name") or extraction.service_name
    if service_name not in by_name:
        service_name = None
    service = by_name.get(service_name or "")

    deployment_id = hints.get("deployment_id") or extraction.deployment_id
    deployment: dict | None = None
    inferred = False
    if deployment_id and _DEPLOYMENT_ID.fullmatch(deployment_id) and service_name:
        recent = ctx.call_tool(
            AGENT, "deployments.list_recent", {"service": service_name, "limit": 20}
        )
        deployment = next((d for d in recent if d["id"] == deployment_id), None)
    elif service_name and extraction.category == "deployment_regression":
        # "the latest deployment" - resolve to the most recent deployment of the service.
        recent = ctx.call_tool(
            AGENT, "deployments.list_recent", {"service": service_name, "limit": 1}
        )
        deployment = recent[0] if recent else None
        inferred = deployment is not None

    incident_time = parse_iso(_normalise_time(extraction.incident_time))
    deployed_at = parse_iso(deployment["deployed_at"]) if deployment else None
    pivot = deployed_at or incident_time
    if pivot is not None:
        window_start, window_end = pivot - timedelta(hours=2), pivot + timedelta(hours=2)
    else:
        window_end = datetime.now(UTC)
        window_start = window_end - timedelta(hours=6)

    category = extraction.category
    if deployment is not None and category == "unknown":
        category = "deployment_regression"

    return IncidentSpec(
        summary=extraction.summary,
        category=category,
        severity=hints.get("severity") or extraction.severity,
        symptoms=extraction.symptoms,
        keywords=extraction.keywords,
        service_name=service_name,
        service_team=service.get("team") if service else None,
        service_channel=service.get("channel") if service else None,
        service_dependencies=list(service.get("dependencies", [])) if service else [],
        deployment_id=deployment["id"] if deployment else None,
        deployment_inferred=inferred,
        deployed_at=deployment["deployed_at"] if deployment else None,
        window_start=iso(window_start),
        window_end=iso(window_end),
        pivot_time=iso(pivot) if pivot else None,
    )


def _match_service(text: str, catalog: list[dict]) -> str | None:
    candidates: list[tuple[int, str]] = []
    for service in catalog:
        for alias in [service["name"], *service.get("aliases", [])]:
            if re.search(rf"\b{re.escape(alias.lower())}\b", text):
                candidates.append((len(alias), service["name"]))
    return max(candidates)[1] if candidates else None


def _normalise_time(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip().replace(" UTC", "Z").replace("UTC", "Z")
    if len(value) == 10:  # date only
        value += "T00:00:00Z"
    return value.replace(" ", "T")


_STOP = frozenset(
    [
        "investigate",
        "why",
        "the",
        "latest",
        "deployment",
        "caused",
        "increase",
        "analyze",
        "analyse",
        "logs",
        "inspect",
        "recent",
        "commits",
        "identify",
        "likely",
        "root",
        "cause",
        "prepare",
        "remediation",
        "plan",
        "with",
        "that",
        "this",
        "from",
        "have",
        "been",
        "around",
        "after",
        "before",
        "since",
        "about",
        "please",
        "check",
        "what",
    ]
)
