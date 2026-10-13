"""Knowledge Retrieval Agent: ground the investigation in runbooks and prior incidents."""

from __future__ import annotations

from typing import Any

from app.agents.common import EvidenceBuilder, step_result
from app.agents.schemas import IncidentSpec, PlanStep
from app.graph.context import WorkflowContext

AGENT = "knowledge_retrieval"
MIN_SCORE = 2.0


def run(task: dict[str, Any], ctx: WorkflowContext) -> dict[str, Any]:
    spec = IncidentSpec.model_validate(task["incident_spec"])
    step = PlanStep.model_validate(task["step"])
    builder = EvidenceBuilder("knowledge", task["round"])

    query = build_query(spec, step, task.get("evidence", []))
    args: dict[str, Any] = {"query": query[:500], "top_k": 4}
    if spec.service_name:
        args["service"] = spec.service_name
    results: list[dict] = ctx.call_tool(AGENT, "knowledge.search", args)

    seen_docs: set[str] = set()
    for hit in results:
        if hit["score"] < MIN_SCORE or hit["doc_id"] in seen_docs:
            continue
        seen_docs.add(hit["doc_id"])
        builder.add(
            hit["kind"],
            f"{hit['title']} - {hit['section']}: {hit['text'][:360]}",
            details={
                "doc_id": hit["doc_id"],
                "title": hit["title"],
                "chunk_id": hit["chunk_id"],
                "score": hit["score"],
                "text": hit["text"][:1200],
                "query": query[:200],
            },
            references=[f"kb://{hit['doc_id']}#{hit['section'].lower().replace(' ', '-')}"],
        )
    if not builder.items:
        builder.add("no_match", f'No runbook or prior incident matched: "{query[:120]}".')
    return step_result(step, builder)


def build_query(spec: IncidentSpec, step: PlanStep, evidence: list[dict]) -> str:
    parts = [*spec.symptoms, *spec.keywords, spec.category.replace("_", " ")]
    if step.mode == "wide":
        # Second pass: search by the concrete error signatures found so far.
        parts = [
            e["details"].get("signature", "")
            for e in evidence
            if e.get("kind") == "error_signature"
        ][:3] + parts[:4]
    return " ".join(p for p in parts if p)
