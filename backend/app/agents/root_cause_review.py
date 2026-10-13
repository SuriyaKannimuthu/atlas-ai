"""Root Cause Review Agent: weigh competing hypotheses against the collected evidence.

Candidate hypotheses and their confidence are scored in code from explicit signals (temporal
correlation, overlap between changes and error signatures, runbook support, contradictions).
When a model is configured it may refine statements and scores, but every evidence reference it
returns is validated, and the "sufficient evidence" decision always passes a deterministic gate.
"""

from __future__ import annotations

from typing import Any

from app.agents.common import evidence_digest, technical_tokens
from app.agents.planner import GAP_TO_STEP
from app.agents.schemas import Hypothesis, IncidentSpec, ReviewResult
from app.graph.context import WorkflowContext
from app.security.untrusted import UNTRUSTED_CONTENT_RULES, wrap_untrusted
from app.services.model_gateway import ModelUnavailableError

AGENT = "review"
CODE_KINDS = {"code_change", "config_change", "dependency_upgrade"}
STRONG_SIGNAL = 0.85

SYSTEM_PROMPT = f"""You are the root-cause review agent of an incident investigation platform.
Evaluate candidate hypotheses against the evidence. Every claim must cite evidence IDs exactly as
given (for example L1.2). Prefer fewer, well-supported hypotheses. Lower confidence when evidence
is missing or contradictory; never invent evidence. {UNTRUSTED_CONTENT_RULES}"""


def run(state: dict[str, Any], ctx: WorkflowContext) -> dict[str, Any]:
    spec = IncidentSpec.model_validate(state["incident_spec"])
    evidence: list[dict[str, Any]] = state.get("evidence", [])
    candidates = score_hypotheses(spec, evidence)
    review = assess(candidates, spec, evidence, ctx.settings.sufficient_confidence)

    if ctx.model.enabled:
        emit = ctx.emitter(AGENT)
        try:
            proposed = ctx.model.structured(
                ReviewResult,
                system=SYSTEM_PROMPT,
                prompt=_prompt(spec, evidence, review),
                name="review.assess",
                emit=emit,
            )
            review = validate_model_review(proposed, review, spec, evidence, ctx)
        except ModelUnavailableError:
            emit("agent_fallback", {"agent": AGENT, "reason": "model unavailable"})

    review.missing_evidence = drop_covered_gaps(
        review.missing_evidence, state.get("completed_steps", [])
    )

    ctx.emitter(AGENT)(
        "review_completed",
        {
            "round": state.get("round", 1),
            "top_hypothesis": review.top_hypothesis_id,
            "confidence": review.confidence,
            "sufficient": review.sufficient,
            "missing_evidence": review.missing_evidence,
        },
    )
    return {
        "review": review.model_dump(),
        "hypotheses": [h.model_dump() for h in review.hypotheses],
    }


# --- deterministic scoring --------------------------------------------------------------


def score_hypotheses(spec: IncidentSpec, evidence: list[dict[str, Any]]) -> list[Hypothesis]:
    rate = next((e for e in evidence if e["kind"] == "error_rate_change"), None)
    signatures = _unique(
        [e for e in evidence if e["kind"] == "error_signature"], lambda e: e["details"]["signature"]
    )
    commits = _unique([e for e in evidence if e["kind"] == "commit"], lambda e: e["details"]["sha"])
    knowledge = [e for e in evidence if e["source"] == "knowledge" and e["kind"] != "no_match"]
    no_deploy = [e for e in evidence if e["kind"] == "no_recent_deployment"]

    temporal = _temporal_correlation(rate)
    preexisting = _errors_preexisted(rate)
    hypotheses: list[Hypothesis] = []

    for commit in commits:
        details = commit["details"]
        commit_tokens = technical_tokens(
            " ".join([details["message"], details["diff"], *details["files"]])
        )
        matched = [s for s in signatures if len(_sig_tokens(s) & commit_tokens) >= 2]
        overlap = max((len(_sig_tokens(s) & commit_tokens) for s in signatures), default=0)
        overlap_score = min(overlap / 4, 1.0)
        signal_tokens = commit_tokens | set().union(*(_sig_tokens(s) for s in matched))
        kb_support = [k for k in knowledge if len(_kb_tokens(k) & signal_tokens) >= 3]

        confidence = 0.35 * overlap_score
        if temporal and rate:
            confidence += 0.35
        if kb_support:
            confidence += 0.15
        if any(k["kind"] == "postmortem" for k in kb_support):
            confidence += 0.05
        if not matched:
            confidence *= 0.5
        contradicting = [rate["id"]] if preexisting and rate else []
        if contradicting:
            confidence -= 0.3

        signals = details.get("risk_signals", [])
        kind = (
            "config_change"
            if "capacity/timeout configuration change" in signals
            else "dependency_upgrade"
            if "dependency change" in signals
            else "code_change"
        )
        supporting = [commit["id"], *(s["id"] for s in matched), *(k["id"] for k in kb_support)]
        if temporal and rate:
            supporting.insert(1, rate["id"])
        hypotheses.append(
            Hypothesis(
                id=f"H-{details['sha']}",
                statement=_commit_statement(details, kind, matched, rate, commits),
                kind=kind,  # type: ignore[arg-type]
                supporting_evidence=supporting,
                contradicting_evidence=contradicting,
                confidence=round(max(0.02, min(confidence, 0.95)), 2),
                rationale=(
                    f"overlap={overlap} tokens with error signatures; temporal="
                    f"{'yes' if temporal else 'no'}; runbook support={len(kb_support)}"
                ),
            )
        )

    for dependency in spec.service_dependencies:
        dep_sigs = [
            s for s in signatures if dependency.lower() in s["details"]["signature"].lower()
        ]
        if not dep_sigs:
            continue
        dep_tokens = technical_tokens(dependency) | set().union(*(_sig_tokens(s) for s in dep_sigs))
        kb_support = [k for k in knowledge if len(_kb_tokens(k) & dep_tokens) >= 2]
        coincides = any(s["details"].get("new_since_pivot") for s in dep_sigs)
        # Capped at 0.6: without the dependency's own telemetry this cannot be confirmed.
        confidence = (
            (0.3 if coincides else 0.15) + (0.15 if kb_support else 0) + (0.15 if no_deploy else 0)
        )
        supporting = [*(s["id"] for s in dep_sigs), *(k["id"] for k in kb_support)]
        supporting += [e["id"] for e in no_deploy]
        if rate:
            supporting.append(rate["id"])
        signature = dep_sigs[0]["details"]["signature"]
        hypotheses.append(
            Hypothesis(
                id=f"H-dep-{dependency}",
                statement=(
                    f'Degradation of dependency {dependency} ("{_short(signature)}") is the '
                    f"most likely cause of {', '.join(spec.symptoms[:2]) or 'the symptoms'}"
                    + ("; no deployment preceded the incident." if no_deploy else ".")
                ),
                kind="infrastructure",
                supporting_evidence=supporting,
                confidence=round(min(confidence, 0.6), 2),
                rationale="dependency errors coincide with symptom onset",
            )
        )

    hypotheses.sort(key=lambda h: h.confidence, reverse=True)
    return hypotheses


def assess(
    hypotheses: list[Hypothesis],
    spec: IncidentSpec,
    evidence: list[dict[str, Any]],
    threshold: float,
) -> ReviewResult:
    by_id = {e["id"]: e for e in evidence}
    top = hypotheses[0] if hypotheses else None
    sources = {by_id[i]["source"] for i in (top.supporting_evidence if top else []) if i in by_id}
    # Sufficient = confident, corroborated by 2+ independent sources, and either backed by
    # documentation (runbook / prior incident) or carrying a very strong direct signal.
    sufficient = bool(
        top
        and top.confidence >= threshold
        and len(sources) >= 2
        and ("knowledge" in sources or top.confidence >= STRONG_SIGNAL)
    )

    has = {
        "logs": any(e["source"] == "logs" and e["kind"] != "no_data" for e in evidence),
        "code": any(e["source"] in ("code", "deployment") for e in evidence),
        "knowledge": any(e["source"] == "knowledge" and e["kind"] != "no_match" for e in evidence),
    }
    missing: list[str] = []
    if not sufficient:
        if not has["logs"]:
            missing.append("logs")
        if spec.service_name and not has["code"]:
            missing.append("code")
        if not has["knowledge"] or (top and "knowledge" not in sources):
            missing.append("knowledge")
        if top and top.kind == "infrastructure":
            missing += ["dependency_health", "logs_wide"]
        if top and top.kind in CODE_KINDS and top.contradicting_evidence:
            missing.append("previous_deployments")
        if not top or top.confidence < 0.4:
            missing += ["logs_wide", "previous_deployments"]

    return ReviewResult(
        hypotheses=hypotheses,
        top_hypothesis_id=top.id if top else None,
        confidence=top.confidence if top else 0.0,
        sufficient=sufficient,
        missing_evidence=list(dict.fromkeys(missing)),  # type: ignore[arg-type]
        rationale=(
            f"Top hypothesis supported by {len(sources)} evidence source(s): "
            f"{', '.join(sorted(sources)) or 'none'}."
        ),
    )


def validate_model_review(
    proposed: ReviewResult,
    baseline: ReviewResult,
    spec: IncidentSpec,
    evidence: list[dict[str, Any]],
    ctx: WorkflowContext,
) -> ReviewResult:
    """Accept model refinements only where they are grounded in real evidence IDs."""
    known = {e["id"] for e in evidence}
    cleaned: list[Hypothesis] = []
    for hypothesis in proposed.hypotheses:
        hypothesis.supporting_evidence = [i for i in hypothesis.supporting_evidence if i in known]
        hypothesis.contradicting_evidence = [
            i for i in hypothesis.contradicting_evidence if i in known
        ]
        if hypothesis.supporting_evidence:
            cleaned.append(hypothesis)
    if not cleaned:
        ctx.emitter(AGENT)("model_output_rejected", {"reason": "no grounded hypotheses"})
        return baseline
    cleaned.sort(key=lambda h: h.confidence, reverse=True)
    gated = assess(cleaned, spec, evidence, ctx.settings.sufficient_confidence)
    gated.sufficient = gated.sufficient and proposed.sufficient
    if proposed.rationale:
        gated.rationale = proposed.rationale
    if not gated.sufficient:
        gated.missing_evidence = list(
            dict.fromkeys([*gated.missing_evidence, *proposed.missing_evidence])
        )
    return gated


def drop_covered_gaps(gaps: list[str], completed_steps: list[dict[str, Any]]) -> list[str]:
    """Remove gaps whose investigation step already ran; what remains is genuinely unknown."""
    done = {(s.get("agent"), s.get("mode")) for s in completed_steps if s.get("status") != "failed"}
    return [
        gap for gap in gaps if gap not in GAP_TO_STEP or tuple(GAP_TO_STEP[gap][:2]) not in done
    ]


# --- helpers ----------------------------------------------------------------------------


def _temporal_correlation(rate: dict[str, Any] | None) -> bool:
    if not rate:
        return False
    d = rate["details"]
    onset = d.get("onset_minutes")
    return (
        d.get("pivot_kind") == "deployment"
        and d["error_rate_after_pct"] > 2 * d["error_rate_before_pct"] + 0.5
        and onset is not None
        and 0 <= onset <= 30
    )


def _errors_preexisted(rate: dict[str, Any] | None) -> bool:
    if not rate:
        return False
    d = rate["details"]
    return (
        d["error_rate_before_pct"] > 0.5
        and d["error_rate_before_pct"] >= 0.8 * d["error_rate_after_pct"]
    )


def _commit_statement(
    details: dict[str, Any],
    kind: str,
    matched: list[dict[str, Any]],
    rate: dict[str, Any] | None,
    commits: list[dict[str, Any]],
) -> str:
    where = f"commit {details['sha']} in deployment {details['deployment_id']}"
    signature = _short(matched[0]["details"]["signature"]) if matched else None
    if kind == "config_change":
        text = f'{where} ("{details["message"]}") reduced capacity settings'
    elif kind == "dependency_upgrade":
        text = f'{where} ("{details["message"]}") introduced an incompatible dependency version'
    else:
        text = f'{where} ("{details["message"]}") changed code on the failing path'
    if signature:
        text += f', matching the new error "{signature}"'
    if rate and rate["details"].get("onset_minutes") is not None:
        text += f" that began {rate['details']['onset_minutes']} min after the deployment"
    text += "."
    related = [
        c["details"]
        for c in commits
        if c["details"]["sha"] != details["sha"]
        and c["details"]["deployment_id"] == details["deployment_id"]
        and "major version upgrade" in c["details"].get("risk_signals", [])
    ]
    if related and kind != "dependency_upgrade":
        text += (
            f' The same deployment also shipped "{related[0]["message"]}" '
            f"({related[0]['sha']}); the combination is a likely incompatibility."
        )
    return text[0].upper() + text[1:]


def _sig_tokens(signature_evidence: dict[str, Any]) -> set[str]:
    return technical_tokens(signature_evidence["details"]["signature"])


def _kb_tokens(knowledge_evidence: dict[str, Any]) -> set[str]:
    return technical_tokens(
        knowledge_evidence["details"].get("text") or knowledge_evidence["summary"]
    )


def _short(text: str, limit: int = 90) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _unique(items: list[dict[str, Any]], key) -> list[dict[str, Any]]:  # type: ignore[no-untyped-def]
    seen: set[str] = set()
    result = []
    for item in items:
        k = key(item)
        if k not in seen:
            seen.add(k)
            result.append(item)
    return result


def _prompt(spec: IncidentSpec, evidence: list[dict[str, Any]], baseline: ReviewResult) -> str:
    candidates = "\n".join(
        f"- {h.id} ({h.kind}, {h.confidence:.2f}): {h.statement} "
        f"supports={h.supporting_evidence} contradicts={h.contradicting_evidence}"
        for h in baseline.hypotheses
    )
    return (
        f"Incident: {spec.summary}\nService: {spec.service_name}\n"
        f"Deployment: {spec.deployment_id}\nCategory: {spec.category}\n\n"
        f"{wrap_untrusted('collected_evidence', evidence_digest(evidence))}\n\n"
        f"Candidate hypotheses from rule-based scoring:\n{candidates or '- none'}\n\n"
        "Return the reviewed hypotheses (reuse candidate IDs where applicable), the top "
        "hypothesis, overall confidence, whether evidence is sufficient, and which evidence "
        "categories are missing."
    )
