"""Evaluation regression gate: fails CI if offline investigation quality drops."""

from __future__ import annotations

from collections.abc import Callable

from app.config import Settings
from app.evaluation.run import DEFAULT_DATASET, evaluate


def test_offline_evaluation_meets_quality_bar(make_settings: Callable[..., Settings]) -> None:
    outcome = evaluate(DEFAULT_DATASET, make_settings())
    summary = outcome["summary"]
    failures = [r["case"] for r in outcome["results"] if r["scores"]["root_cause_accuracy"] < 1]
    assert summary["errors"] == 0
    assert summary["root_cause_accuracy"] >= 0.95, failures
    assert summary["investigation_success_rate"] >= 0.95, failures
    assert summary["evidence_grounding"] == 1.0
    assert summary["unsupported_claim_rate"] == 0.0
    assert summary["approval_policy_compliance"] == 1.0


def test_evaluation_survives_transient_faults(make_settings: Callable[..., Settings]) -> None:
    settings = make_settings(fault_injection="logs.search:transient:1,knowledge.search:transient:1")
    summary = evaluate(DEFAULT_DATASET, settings)["summary"]
    assert summary["errors"] == 0
    assert summary["root_cause_accuracy"] >= 0.95
