"""Code and Commit Analysis Agent: find changes that shipped near the incident."""

from __future__ import annotations

import re
from datetime import timedelta
from typing import Any

from app.agents.common import EvidenceBuilder, iso, parse_iso, step_result
from app.agents.schemas import IncidentSpec, PlanStep
from app.graph.context import WorkflowContext
from app.tools.base import PermanentToolError

AGENT = "code_analysis"

_DEPENDENCY_FILES = re.compile(
    r"(requirements.*\.txt|pyproject\.toml|package(-lock)?\.json|go\.mod|pom\.xml)$"
)
_CONFIG_FILES = re.compile(r"(\.ya?ml|\.toml|\.ini|\.env|\.json)$")
_MAJOR_BUMP = re.compile(r"(\d+)\.\d+\.\d+\s*(?:->|to)\s*(\d+)\.\d+\.\d+")
_CAPACITY_KEYS = re.compile(
    r"(pool|max_size|overflow|limit|timeout|replicas|workers|threads)", re.I
)


def run(task: dict[str, Any], ctx: WorkflowContext) -> dict[str, Any]:
    spec = IncidentSpec.model_validate(task["incident_spec"])
    step = PlanStep.model_validate(task["step"])
    builder = EvidenceBuilder("code", task["round"])
    if not spec.service_name:
        return step_result(step, builder, status="skipped", note="no service identified")

    deployments = select_deployments(spec, step, ctx)
    if not deployments:
        pivot = spec.pivot_time or spec.window_end
        builder.add(
            "no_recent_deployment",
            f"No deployments of {spec.service_name} in the 24 hours before {pivot}; a code "
            "change is unlikely to be the trigger.",
            details={"service": spec.service_name, "checked_until": pivot},
            references=[f"deploys://{spec.service_name}"],
            source="deployment",
        )
        return step_result(step, builder)

    for deployment in deployments:
        commits = []
        for sha in deployment["commits"]:
            try:
                commits.append(ctx.call_tool(AGENT, "github.get_commit", {"sha": sha}))
            except PermanentToolError:
                builder.add(
                    "missing_commit",
                    f"Commit {sha} listed in {deployment['id']} could not be retrieved.",
                    source="code",
                )
        builder.add(
            "deployment",
            f"Deployment {deployment['id']} ({deployment['version']}) of {deployment['service']} "
            f"at {deployment['deployed_at']} shipped {len(commits)} commit(s); previous "
            f"deployment {deployment['previous_deployment']}.",
            details={
                k: deployment[k]
                for k in (
                    "id",
                    "service",
                    "deployed_at",
                    "version",
                    "previous_deployment",
                    "commits",
                )
            },
            references=[f"deploys://{deployment['service']}/{deployment['id']}"],
            timestamp=deployment["deployed_at"],
            source="deployment",
        )
        for commit in commits:
            signals = risk_signals(commit)
            builder.add(
                "commit",
                f'Commit {commit["sha"]} in {deployment["id"]}: "{commit["message"]}" '
                f"(files: {', '.join(commit['files'])})"
                + (f"; risk signals: {', '.join(signals)}" if signals else ""),
                details={
                    "sha": commit["sha"],
                    "deployment_id": deployment["id"],
                    "message": commit["message"],
                    "files": commit["files"],
                    "diff": commit["diff"][:1500],
                    "risk_signals": signals,
                    "author": commit["author"],
                },
                references=[f"git://{commit['service']}/commit/{commit['sha']}"],
                timestamp=commit["committed_at"],
            )
    return step_result(step, builder)


def select_deployments(spec: IncidentSpec, step: PlanStep, ctx: WorkflowContext) -> list[dict]:
    if spec.deployment_id and step.mode == "default":
        return [ctx.call_tool(AGENT, "deployments.get", {"deployment_id": spec.deployment_id})]

    pivot = parse_iso(spec.pivot_time) or parse_iso(spec.window_end)
    assert pivot is not None
    lookback = timedelta(days=7) if step.mode == "wide" else timedelta(hours=24)
    recent = ctx.call_tool(
        AGENT,
        "deployments.list_recent",
        {
            "service": spec.service_name,
            "before": iso(pivot),
            "limit": 5,
        },
    )
    selected = [d for d in recent if parse_iso(d["deployed_at"]) >= pivot - lookback]
    if step.mode == "wide":
        selected = [d for d in selected if d["id"] != spec.deployment_id]
    return selected


def risk_signals(commit: dict) -> list[str]:
    signals = []
    files = commit["files"]
    diff = commit.get("diff", "")
    if any(_DEPENDENCY_FILES.search(f) for f in files):
        signals.append("dependency change")
        if (match := _MAJOR_BUMP.search(commit["message"] + diff)) and match[1] != match[2]:
            signals.append("major version upgrade")
    if any(_CONFIG_FILES.search(f) for f in files) and _CAPACITY_KEYS.search(diff):
        signals.append("capacity/timeout configuration change")
    removed = [line for line in diff.splitlines() if line.startswith("-") and "(" in line]
    added = [line for line in diff.splitlines() if line.startswith("+") and "(" in line]
    if removed and added:
        signals.append("call signature change")
    return signals
