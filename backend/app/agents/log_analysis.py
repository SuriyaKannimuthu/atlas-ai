"""Log Analysis Agent: quantify error-rate changes and cluster error signatures.

Statistics are computed in code. Log text is treated as untrusted data: suspicious lines are
flagged and surfaced, never interpreted as instructions.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from typing import Any

from app.agents.common import EvidenceBuilder, error_signature, iso, parse_iso, step_result
from app.agents.schemas import IncidentSpec, PlanStep
from app.graph.context import WorkflowContext
from app.security.untrusted import looks_like_injection

AGENT = "log_analysis"


def run(task: dict[str, Any], ctx: WorkflowContext) -> dict[str, Any]:
    spec = IncidentSpec.model_validate(task["incident_spec"])
    step = PlanStep.model_validate(task["step"])
    builder = EvidenceBuilder("logs", task["round"])

    if not spec.service_name:
        return step_result(step, builder, status="skipped", note="no service identified")

    start, end = parse_iso(spec.window_start), parse_iso(spec.window_end)
    assert start and end
    if step.mode == "wide":
        start, end = start - timedelta(hours=6), end + timedelta(hours=2)

    rows: list[dict] = ctx.call_tool(
        AGENT,
        "logs.search",
        {
            "service": spec.service_name,
            "start": iso(start),
            "end": iso(end),
            "min_level": "INFO",
            "limit": 2000,
        },
    )
    reference = f"logs://{spec.service_name}?start={iso(start)}&end={iso(end)}"
    if not rows:
        builder.add(
            "no_data",
            f"No log records for {spec.service_name} between {iso(start)} and {iso(end)}.",
            references=[reference],
        )
        return step_result(step, builder)

    pivot = parse_iso(spec.pivot_time) or start + (end - start) / 2
    analyse_error_rates(rows, pivot, spec, builder, reference)
    analyse_signatures(rows, pivot, builder, reference)
    flag_untrusted_lines(rows, builder, reference)
    return step_result(step, builder)


def analyse_error_rates(
    rows: list[dict], pivot, spec: IncidentSpec, builder: EvidenceBuilder, reference: str
) -> None:
    totals = {"before": [0, 0], "after": [0, 0]}  # [errors, all]
    first_error_after: str | None = None
    for row in rows:
        side = "after" if parse_iso(row["timestamp"]) >= pivot else "before"
        totals[side][1] += row["count"]
        if row["level"] == "ERROR":
            totals[side][0] += row["count"]
            if side == "after" and first_error_after is None:
                first_error_after = row["timestamp"]

    def rate(side: str) -> float:
        errors, total = totals[side]
        return round(100 * errors / total, 2) if total else 0.0

    before, after = rate("before"), rate("after")
    pivot_label = (
        f"deployment {spec.deployment_id}" if spec.deployed_at else "the reported incident start"
    )
    onset_minutes = None
    if first_error_after:
        onset_minutes = int((parse_iso(first_error_after) - pivot).total_seconds() // 60)
    builder.add(
        "error_rate_change",
        f"Error rate for {spec.service_name} changed from {before}% before to {after}% after "
        f"{pivot_label} ({iso(pivot)}).",
        details={
            "pivot": iso(pivot),
            "pivot_kind": "deployment" if spec.deployed_at else "reported",
            "error_rate_before_pct": before,
            "error_rate_after_pct": after,
            "errors_before": totals["before"][0],
            "errors_after": totals["after"][0],
            "first_error_after_pivot": first_error_after,
            "onset_minutes": onset_minutes,
        },
        references=[reference],
        timestamp=first_error_after,
    )


def analyse_signatures(rows: list[dict], pivot, builder: EvidenceBuilder, reference: str) -> None:
    clusters: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"count": 0, "before": 0, "first_seen": None, "level": None}
    )
    for row in rows:
        if row["level"] not in ("ERROR", "WARN") or looks_like_injection(row["message"]):
            continue
        cluster = clusters[error_signature(row["message"])]
        cluster["count"] += row["count"]
        cluster["level"] = row["level"]
        if parse_iso(row["timestamp"]) < pivot:
            cluster["before"] += row["count"]
        if cluster["first_seen"] is None:
            cluster["first_seen"] = row["timestamp"]

    ranked = sorted(clusters.items(), key=lambda item: item[1]["count"], reverse=True)
    for signature, info in ranked[:4]:
        new = info["before"] == 0
        builder.add(
            "error_signature",
            f'{info["count"]:,} {info["level"]} events matching "{signature}" '
            f"(first seen {info['first_seen']}{', new since pivot' if new else ''}).",
            details={"signature": signature, **info, "new_since_pivot": new},
            references=[f"{reference}&q={signature[:60]}"],
            timestamp=info["first_seen"],
        )


def flag_untrusted_lines(rows: list[dict], builder: EvidenceBuilder, reference: str) -> None:
    for row in rows:
        if looks_like_injection(row["message"]):
            builder.add(
                "untrusted_content",
                "Log record contains instruction-like text; it was treated as data and ignored "
                "for decision-making.",
                details={"timestamp": row["timestamp"], "excerpt": row["message"][:200]},
                references=[reference],
                timestamp=row["timestamp"],
                flags=["possible_prompt_injection"],
            )
