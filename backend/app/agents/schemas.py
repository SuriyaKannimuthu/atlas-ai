"""Typed contracts exchanged between agents and used for LLM structured output."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Category = Literal[
    "deployment_regression", "error_spike", "latency", "availability", "security", "unknown"
]
Severity = Literal["sev1", "sev2", "sev3", "sev4"]
AgentName = Literal["log_analysis", "code_analysis", "knowledge_retrieval"]


class TriageExtraction(BaseModel):
    """What the triage model extracts. Identifiers are validated deterministically afterwards."""

    summary: str = Field(description="One-sentence restatement of the incident.")
    category: Category
    severity: Severity
    symptoms: list[str] = Field(
        default_factory=list,
        max_length=8,
        description="Observable symptoms, e.g. 'HTTP 500 on checkout'.",
    )
    keywords: list[str] = Field(
        default_factory=list,
        max_length=12,
        description="Technical search terms useful for logs and docs.",
    )
    service_name: str | None = Field(default=None, description="Exact catalog service name.")
    deployment_id: str | None = Field(default=None, description="Deployment ID like d-1234.")
    incident_time: str | None = Field(default=None, description="ISO-8601 time if stated.")


class IncidentSpec(BaseModel):
    summary: str
    category: Category
    severity: Severity
    symptoms: list[str]
    keywords: list[str]
    service_name: str | None
    service_team: str | None = None
    service_channel: str | None = None
    service_dependencies: list[str] = Field(default_factory=list)
    deployment_id: str | None
    deployment_inferred: bool = False
    deployed_at: str | None = None
    window_start: str
    window_end: str
    pivot_time: str | None = Field(
        default=None, description="Deployment or reported start time used as pivot."
    )


class PlanStep(BaseModel):
    id: str
    agent: AgentName
    objective: str
    mode: Literal["default", "wide"] = "default"
    query: str | None = None


class Evidence(BaseModel):
    id: str
    source: Literal["logs", "code", "deployment", "knowledge"]
    kind: str
    summary: str = Field(max_length=600)
    details: dict = Field(default_factory=dict)
    references: list[str] = Field(default_factory=list)
    timestamp: str | None = None
    flags: list[str] = Field(default_factory=list)
    round: int = 1


class Hypothesis(BaseModel):
    id: str
    statement: str
    kind: Literal[
        "code_change", "config_change", "dependency_upgrade", "infrastructure", "traffic", "unknown"
    ]
    supporting_evidence: list[str] = Field(default_factory=list)
    contradicting_evidence: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = ""


MissingEvidence = Literal[
    "logs", "logs_wide", "code", "previous_deployments", "knowledge", "dependency_health"
]


class ReviewResult(BaseModel):
    hypotheses: list[Hypothesis]
    top_hypothesis_id: str | None = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    sufficient: bool = False
    missing_evidence: list[MissingEvidence] = Field(default_factory=list)
    rationale: str = ""


class ReportNarrative(BaseModel):
    """Narrative fields the reporting model writes; structure and references are deterministic."""

    title: str = Field(max_length=140)
    summary: str = Field(description="3-5 sentences for an incident channel.")
    impact: str
    remediation: list[str] = Field(max_length=8)
    unknowns: list[str] = Field(default_factory=list, max_length=8)


class ProposedAction(BaseModel):
    id: str
    type: str
    params: dict
    rationale: str
    requires_approval: bool = True
    risk: str = "high"
