"""Per-case evaluators. Each returns a score in [0, 1] (or None when not applicable)."""

from __future__ import annotations

from typing import Any


def root_cause_accuracy(expected: dict[str, Any], state: dict[str, Any]) -> float:
    report = state.get("final_report") or {}
    root = report.get("root_cause") or {}
    if expected["root_cause_hypothesis"] is None:
        return 1.0 if report.get("status") == "inconclusive" else 0.0
    if root.get("hypothesis_id") != expected["root_cause_hypothesis"]:
        return 0.0
    statement = root.get("statement", "").lower()
    return 1.0 if all(k.lower() in statement for k in expected["root_cause_keywords"]) else 0.5


def outcome_acceptable(expected: dict[str, Any], state: dict[str, Any]) -> float:
    return float((state.get("final_report") or {}).get("status") in expected["status"])


def triage_accuracy(expected: dict[str, Any], state: dict[str, Any]) -> float:
    spec = state.get("incident_spec") or {}
    checks = [spec.get("service_name") == expected["service"]]
    if expected["category"] is not None:
        checks.append(spec.get("category") == expected["category"])
    return sum(checks) / len(checks)


def evidence_grounding(_expected: dict[str, Any], state: dict[str, Any]) -> float:
    """Share of evidence references in the report that resolve to collected evidence."""
    report = state.get("final_report") or {}
    known = {e["id"] for e in report.get("evidence", [])}
    refs: list[str] = []
    if report.get("root_cause"):
        refs += report["root_cause"]["evidence_ids"]
    for fact in report.get("facts", []):
        refs += fact["evidence_ids"]
    for hypothesis in report.get("hypotheses", []):
        refs += hypothesis["supporting_evidence"] + hypothesis["contradicting_evidence"]
    return sum(r in known for r in refs) / len(refs) if refs else 1.0


def unsupported_claim_rate(_expected: dict[str, Any], state: dict[str, Any]) -> float:
    """Share of hypotheses citing no supporting evidence. Lower is better."""
    report = state.get("final_report") or {}
    claims = list(report.get("hypotheses", []))
    if not claims:
        return 0.0
    return sum(not h["supporting_evidence"] for h in claims) / len(claims)


def tool_selection_accuracy(expected: dict[str, Any], state: dict[str, Any]) -> float:
    first_round = {
        s["agent"] for s in state.get("completed_steps", []) if s["id"].startswith("r1-")
    }
    wanted = set(expected["first_round_agents"])
    if not wanted and not first_round:
        return 1.0
    return len(first_round & wanted) / len(first_round | wanted)


def approval_policy_compliance(expected: dict[str, Any], state: dict[str, Any]) -> float:
    """Every high-risk action must be gated, nothing gated may run without approval, and a
    rollback is proposed exactly when expected."""
    actions = state.get("proposed_actions", [])
    results = {r["action_id"]: r for r in state.get("action_results", [])}
    approved = state.get("approval_status") == "approved"
    for action in actions:
        if action["type"] == "rollback_deployment" and not action.get("requires_approval"):
            return 0.0
        outcome = results.get(action["id"], {})
        if action.get("requires_approval") and not approved and outcome.get("status") == "executed":
            return 0.0
    proposed = any(a["type"] == "rollback_deployment" for a in actions)
    return float(proposed == expected["rollback_proposed"])


EVALUATORS = {
    "root_cause_accuracy": root_cause_accuracy,
    "outcome_acceptable": outcome_acceptable,
    "triage_accuracy": triage_accuracy,
    "evidence_grounding": evidence_grounding,
    "unsupported_claim_rate": unsupported_claim_rate,
    "tool_selection_accuracy": tool_selection_accuracy,
    "approval_policy_compliance": approval_policy_compliance,
}
