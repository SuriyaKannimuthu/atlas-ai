"""Reporting Agent: assemble an evidence-backed incident report and propose actions.

Report structure, evidence references, and proposed actions are built in code. A configured
model only writes narrative fields (title, summary, impact, remediation wording).
"""

from __future__ import annotations

from typing import Any

from app.agents.common import evidence_digest
from app.agents.schemas import (
    Hypothesis,
    IncidentSpec,
    ProposedAction,
    ReportNarrative,
    ReviewResult,
)
from app.graph.context import WorkflowContext
from app.security.untrusted import UNTRUSTED_CONTENT_RULES, wrap_untrusted
from app.services.model_gateway import ModelUnavailableError

AGENT = "report"
CODE_KINDS = {"code_change", "config_change", "dependency_upgrade"}

_GAP_TEXT = {
    "logs": "Log data for the incident window was unavailable or incomplete.",
    "logs_wide": "It is not confirmed whether the error pattern predates the incident window.",
    "code": "Recent code changes could not be inspected.",
    "previous_deployments": "Earlier deployments were not ruled out as contributing changes.",
    "knowledge": "No runbook or prior incident corroborates the leading hypothesis.",
    "dependency_health": "Telemetry from the affected dependency (failover events, saturation) "
    "is not connected to the platform.",
}

SYSTEM_PROMPT = f"""You write incident reports for on-call engineers.
Be precise and brief. Distinguish verified facts from hypotheses, cite evidence IDs in brackets,
and do not claim more certainty than the stated confidence. {UNTRUSTED_CONTENT_RULES}"""


def run(state: dict[str, Any], ctx: WorkflowContext) -> dict[str, Any]:
    spec = IncidentSpec.model_validate(state["incident_spec"])
    review = ReviewResult.model_validate(state["review"])
    evidence: list[dict[str, Any]] = state.get("evidence", [])
    by_id = {e["id"]: e for e in evidence}
    top = next((h for h in review.hypotheses if h.id == review.top_hypothesis_id), None)

    if review.sufficient:
        status = "root_cause_identified"
    elif top and top.confidence >= 0.4:
        status = "probable_cause"
    else:
        status = "inconclusive"

    narrative = heuristic_narrative(spec, review, top, status, by_id)
    generated_by = "heuristic"
    if ctx.model.enabled:
        emit = ctx.emitter(AGENT)
        try:
            narrative = ctx.model.structured(
                ReportNarrative,
                system=SYSTEM_PROMPT,
                prompt=_prompt(spec, review, status, evidence),
                name="report.narrative",
                emit=emit,
            )
            generated_by = ctx.model.label
        except ModelUnavailableError:
            emit("agent_fallback", {"agent": AGENT, "reason": "model unavailable"})

    unknowns = list(
        dict.fromkeys([*narrative.unknowns, *(_GAP_TEXT[g] for g in review.missing_evidence)])
    )
    actions = propose_actions(state["incident_id"], spec, review, top, narrative.summary, by_id)
    report = {
        "title": narrative.title,
        "status": status,
        "summary": narrative.summary,
        "impact": narrative.impact,
        "root_cause": (
            {
                "hypothesis_id": top.id,
                "statement": top.statement,
                "kind": top.kind,
                "confidence": top.confidence,
                "evidence_ids": top.supporting_evidence,
            }
            if top
            else None
        ),
        "facts": build_facts(evidence, top),
        "hypotheses": [h.model_dump() for h in review.hypotheses],
        "timeline": build_timeline(evidence),
        "unknowns": unknowns,
        "remediation": narrative.remediation,
        "security_notes": [
            {"evidence_id": e["id"], "note": e["summary"]}
            for e in evidence
            if "possible_prompt_injection" in e.get("flags", [])
        ],
        "evidence": evidence,
        "investigation": {
            "rounds": state.get("round", 1),
            "steps": state.get("completed_steps", []),
            "review_rationale": review.rationale,
        },
        "generated_by": generated_by,
        "incident_spec": spec.model_dump(),
    }
    return {"final_report": report, "proposed_actions": [a.model_dump() for a in actions]}


def heuristic_narrative(
    spec: IncidentSpec,
    review: ReviewResult,
    top: Hypothesis | None,
    status: str,
    by_id: dict[str, dict[str, Any]],
) -> ReportNarrative:
    service = spec.service_name or "unidentified service"
    rate = next((e for e in by_id.values() if e["kind"] == "error_rate_change"), None)
    if rate:
        d = rate["details"]
        impact = (
            f"Error rate for {service} rose from {d['error_rate_before_pct']}% to "
            f"{d['error_rate_after_pct']}% after {d['pivot']} "
            f"({d['errors_after']:,} failed events in the analysed window) [{rate['id']}]."
        )
    else:
        impact = f"Impact on {service} could not be quantified from available logs."

    lead = {
        "root_cause_identified": "Root cause identified",
        "probable_cause": "Probable cause identified; confirmation needed",
        "inconclusive": "Investigation inconclusive",
    }[status]
    summary = f"{lead} for {service}."
    if top:
        summary += (
            f" {top.statement} Confidence {top.confidence:.0%}, supported by "
            f"{', '.join(top.supporting_evidence)}."
        )
    if len(review.hypotheses) > 1:
        runner_up = review.hypotheses[1]
        summary += f" Alternative considered: {runner_up.id} ({runner_up.confidence:.0%})."

    title = f"{service}: " + (
        {
            "config_change": "configuration change",
            "dependency_upgrade": "dependency upgrade",
            "code_change": "code change",
            "infrastructure": "dependency degradation",
        }.get(top.kind, "incident")
        if top
        else "incident"
    )
    if spec.deployment_id and top and top.kind in CODE_KINDS:
        title += f" in {spec.deployment_id}"
    title += f" ({spec.category.replace('_', ' ')})"

    return ReportNarrative(
        title=title[:140],
        summary=summary,
        impact=impact,
        remediation=remediation_steps(spec, top, by_id),
        unknowns=[],
    )


def remediation_steps(
    spec: IncidentSpec, top: Hypothesis | None, by_id: dict[str, dict[str, Any]]
) -> list[str]:
    steps: list[str] = []
    previous = _previous_deployment(by_id, spec.deployment_id)
    if top and top.kind in CODE_KINDS and spec.deployment_id:
        steps.append(
            f"Roll back {spec.service_name} from {spec.deployment_id} to "
            f"{previous or 'the previous deployment'} to restore service, then fix forward."
        )
    if top and top.kind == "config_change":
        steps.append("Restore the previous capacity settings and load test before reapplying.")
    if top and top.kind in ("dependency_upgrade", "code_change"):
        steps.append(
            "Pin the affected dependency or correct the call site, and add contract tests."
        )
    if top and top.kind == "infrastructure":
        steps.append("Escalate to the platform team owning the degraded dependency.")
        steps.append("Review failover and saturation metrics for the dependency during the window.")
    for evidence_id in top.supporting_evidence if top else []:
        item = by_id.get(evidence_id)
        if item and item["source"] == "knowledge" and item["kind"] == "runbook":
            title = item["details"].get("title", "").removeprefix("Runbook - ")
            steps.append(f"Follow runbook: {title} [{evidence_id}].")
    if not steps:
        steps.append("Collect additional telemetry and re-run the investigation.")
    return list(dict.fromkeys(steps))[:8]


def build_facts(evidence: list[dict[str, Any]], top: Hypothesis | None) -> list[dict[str, Any]]:
    relevant = set(top.supporting_evidence if top else [])
    facts = []
    for item in evidence:
        if item["kind"] in ("error_rate_change", "deployment", "no_recent_deployment") or (
            item["id"] in relevant and item["source"] != "knowledge"
        ):
            facts.append({"statement": item["summary"], "evidence_ids": [item["id"]]})
    return facts[:12]


def build_timeline(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    entries = []
    seen: set[tuple[str, str]] = set()
    for item in evidence:
        if not item.get("timestamp") or item["kind"] == "untrusted_content":
            continue
        key = (item["timestamp"], item["kind"])
        if key in seen:
            continue
        seen.add(key)
        entries.append(
            {"timestamp": item["timestamp"], "event": item["summary"], "evidence_id": item["id"]}
        )
    entries.sort(key=lambda e: e["timestamp"])
    return entries[:15]


def propose_actions(
    incident_id: str,
    spec: IncidentSpec,
    review: ReviewResult,
    top: Hypothesis | None,
    summary: str,
    by_id: dict[str, dict[str, Any]],
) -> list[ProposedAction]:
    """Propose actions; whether they need approval is decided later by the policy gate."""
    if not spec.service_name:
        return []
    actions = [
        ProposedAction(
            id="act-ticket",
            type="create_ticket",
            params={
                "title": f"[{spec.severity.upper()}] {spec.service_name}: {spec.summary}"[:200],
                "body": f"Atlas AI investigation {incident_id}\n\n{summary}",
                "service": spec.service_name,
                "severity": spec.severity,
            },
            rationale="Track remediation and follow-ups.",
        )
    ]
    if spec.service_channel:
        actions.append(
            ProposedAction(
                id="act-notify",
                type="notify_channel",
                params={"channel": spec.service_channel, "message": summary[:4000]},
                rationale=f"Inform the owning team ({spec.service_team}).",
            )
        )
    if (
        top
        and top.kind in CODE_KINDS
        and review.sufficient
        and spec.deployment_id
        and (previous := _previous_deployment(by_id, spec.deployment_id))
    ):
        actions.append(
            ProposedAction(
                id="act-rollback",
                type="rollback_deployment",
                params={
                    "service": spec.service_name,
                    "from_deployment": spec.deployment_id,
                    "to_deployment": previous,
                },
                rationale=f"{top.id} attributes the regression to {spec.deployment_id} "
                f"with {top.confidence:.0%} confidence.",
            )
        )
    return actions


def _previous_deployment(by_id: dict[str, dict[str, Any]], deployment_id: str | None) -> str | None:
    for item in by_id.values():
        if item["kind"] == "deployment" and item["details"].get("id") == deployment_id:
            return item["details"].get("previous_deployment")
    return None


def _prompt(spec: IncidentSpec, review: ReviewResult, status: str, evidence: list[dict]) -> str:
    hypotheses = "\n".join(
        f"- {h.id} ({h.confidence:.2f}): {h.statement} supports={h.supporting_evidence}"
        for h in review.hypotheses
    )
    return (
        f"Incident: {spec.summary}\nService: {spec.service_name} (team {spec.service_team})\n"
        f"Severity: {spec.severity}\nStatus: {status}\n"
        f"Missing evidence: {review.missing_evidence}\n\n"
        f"Hypotheses:\n{hypotheses or '- none'}\n\n"
        f"{wrap_untrusted('collected_evidence', evidence_digest(evidence))}"
    )
