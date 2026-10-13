"""Evaluation runner: execute the workflow over the incident dataset and score each run.

    python -m app.evaluation.run                      # offline heuristics, default dataset
    python -m app.evaluation.run --use-env-model      # use MODEL_PROVIDER / MODEL_NAME from .env
    python -m app.evaluation.run --fault logs.search:transient:1 --out results.json

Gated actions are always rejected during evaluation, so nothing with side effects runs.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from app.config import BACKEND_ROOT, Settings
from app.evaluation.evaluators import EVALUATORS
from app.graph.context import WorkflowContext
from app.graph.state import initial_state
from app.graph.workflow import build_workflow
from app.services.model_gateway import ModelGateway
from app.tools import build_tool_registry
from app.tools.base import CallBudget
from app.tools.ticketing import IdempotentStore

DEFAULT_DATASET = BACKEND_ROOT / "datasets" / "incidents" / "eval_cases.json"


def run_case(case: dict[str, Any], settings: Settings) -> dict[str, Any]:
    graph = build_workflow(InMemorySaver(), max_rounds=settings.max_investigation_rounds)
    model = ModelGateway(settings)
    ctx = WorkflowContext(
        incident_id=f"eval-{case['id']}",
        settings=settings,
        tools=build_tool_registry(settings, IdempotentStore()),
        model=model,
        record_event=lambda *_args: None,
        budget=CallBudget(limit=settings.max_tool_calls),
    )
    config = {
        "configurable": {"thread_id": ctx.incident_id},
        "run_name": f"eval:{case['id']}",
        "tags": ["atlas", "evaluation"],
        "metadata": {"case": case["id"]},
    }
    started = time.perf_counter()
    error = None
    try:
        graph.invoke(
            initial_state(ctx.incident_id, case["description"], case["hints"]), config, context=ctx
        )
        if graph.get_state(config).interrupts:
            graph.invoke(
                Command(resume={"decision": "rejected", "decided_by": "evaluator"}),
                config,
                context=ctx,
            )
    except Exception as exc:  # recorded as a failed case, not a crashed run
        error = f"{type(exc).__name__}: {exc}"
    latency_ms = int((time.perf_counter() - started) * 1000)

    state = graph.get_state(config).values
    scores = {name: fn(case["expected"], state) for name, fn in EVALUATORS.items()}
    report = state.get("final_report") or {}
    return {
        "case": case["id"],
        "error": error,
        "latency_ms": latency_ms,
        "status": report.get("status"),
        "root_cause": (report.get("root_cause") or {}).get("hypothesis_id"),
        "confidence": (report.get("root_cause") or {}).get("confidence"),
        "rounds": state.get("round"),
        "tool_calls": ctx.budget.used,
        "tokens": ctx.usage.get("input_tokens", 0) + ctx.usage.get("output_tokens", 0),
        "model": model.label,
        "scores": scores,
    }


def summarise(results: list[dict[str, Any]]) -> dict[str, Any]:
    latencies = sorted(r["latency_ms"] for r in results)
    summary: dict[str, Any] = {
        "cases": len(results),
        "errors": sum(bool(r["error"]) for r in results),
        "investigation_success_rate": statistics.mean(
            r["scores"]["outcome_acceptable"] for r in results
        ),
        "latency_p50_ms": latencies[len(latencies) // 2],
        "latency_p95_ms": latencies[min(len(latencies) - 1, int(len(latencies) * 0.95))],
        "total_tokens": sum(r["tokens"] for r in results),
    }
    for metric in EVALUATORS:
        summary[metric] = round(statistics.mean(r["scores"][metric] for r in results), 3)
    return summary


def evaluate(dataset: Path, settings: Settings) -> dict[str, Any]:
    cases = json.loads(dataset.read_text(encoding="utf-8"))
    results = [run_case(case, settings) for case in cases]
    return {"dataset": dataset.name, "summary": summarise(results), "results": results}


def render(outcome: dict[str, Any]) -> str:
    lines = [
        "| case | status | root cause | conf. | root-cause acc. | grounding | latency |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in outcome["results"]:
        s = r["scores"]
        lines.append(
            f"| {r['case']} | {r['status'] or r['error']} | {r['root_cause'] or '-'} | "
            f"{r['confidence'] if r['confidence'] is not None else '-'} | "
            f"{s['root_cause_accuracy']:.2f} | {s['evidence_grounding']:.2f} | "
            f"{r['latency_ms']} ms |"
        )
    lines.append("")
    lines += [f"- **{k}**: {v}" for k, v in outcome["summary"].items()]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--use-env-model", action="store_true")
    parser.add_argument("--fault", default="")
    args = parser.parse_args()

    overrides: dict[str, Any] = {"fault_injection": args.fault, "tool_backoff_base_s": 0.05}
    if not args.use_env_model:
        overrides.update(model_provider=None, model_name=None)
    settings = Settings(**overrides)

    outcome = evaluate(args.dataset, settings)
    print(render(outcome))
    if args.out:
        args.out.write_text(json.dumps(outcome, indent=2, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
