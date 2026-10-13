from typing import Any

from app.agents.common import technical_tokens
from app.agents.root_cause_review import assess, drop_covered_gaps
from app.agents.schemas import Hypothesis, IncidentSpec
from app.agents.triage import heuristic_extraction
from app.config import BACKEND_ROOT
from app.tools.mock_data import load_mock_data
from app.tools.retrieval import BM25Index, chunk_documents

CATALOG = [
    {"name": "checkout-api", "aliases": ["checkout"]},
    {"name": "auth-service", "aliases": ["login", "auth"]},
]


def make_spec(**overrides: Any) -> IncidentSpec:
    values: dict[str, Any] = {
        "summary": "s",
        "category": "error_spike",
        "severity": "sev2",
        "symptoms": [],
        "keywords": [],
        "service_name": "checkout-api",
        "deployment_id": None,
        "window_start": "2026-10-10T12:00:00Z",
        "window_end": "2026-10-10T16:00:00Z",
    }
    values.update(overrides)
    return IncidentSpec(**values)


def test_triage_heuristics_extract_service_category_and_deployment() -> None:
    result = heuristic_extraction("checkout-api 500 errors after deploy d-2041", CATALOG)
    assert result.service_name == "checkout-api"
    assert result.category == "deployment_regression"
    assert result.deployment_id == "d-2041"


def test_triage_matches_aliases() -> None:
    assert heuristic_extraction("login is very slow", CATALOG).service_name == "auth-service"


def test_technical_tokens_split_identifiers() -> None:
    tokens = technical_tokens("StripeClient.create_charge() idempotency_key")
    assert {"stripe", "client", "create_charge", "charge", "idempotency_key"} <= tokens


def test_sufficiency_requires_two_sources_and_corroboration() -> None:
    evidence = [
        {"id": "L1.1", "source": "logs", "kind": "error_rate_change"},
        {"id": "C1.1", "source": "code", "kind": "commit"},
        {"id": "K1.1", "source": "knowledge", "kind": "runbook"},
    ]
    weak = Hypothesis(
        id="H",
        statement="x",
        kind="config_change",
        confidence=0.75,
        supporting_evidence=["L1.1", "C1.1"],
    )
    assert not assess([weak], make_spec(), evidence, 0.7).sufficient
    corroborated = weak.model_copy(update={"supporting_evidence": ["L1.1", "C1.1", "K1.1"]})
    assert assess([corroborated], make_spec(), evidence, 0.7).sufficient
    one_source = weak.model_copy(update={"confidence": 0.9, "supporting_evidence": ["L1.1"]})
    assert not assess([one_source], make_spec(), evidence, 0.7).sufficient


def test_completed_steps_close_gaps_but_failed_steps_do_not() -> None:
    steps = [
        {"agent": "log_analysis", "mode": "wide", "status": "completed"},
        {"agent": "knowledge_retrieval", "mode": "wide", "status": "failed"},
    ]
    gaps = drop_covered_gaps(["logs_wide", "knowledge", "dependency_health"], steps)
    assert gaps == ["knowledge", "dependency_health"]


def test_bm25_retrieval_ranks_pool_documents_first() -> None:
    index = BM25Index(chunk_documents(load_mock_data(BACKEND_ROOT / "data").knowledge))
    top_chunk, _score = index.search("QueuePool limit reached connection pool", top_k=1)[0]
    assert top_chunk.doc.doc_id in {
        "runbook-db-pool-exhaustion",
        "postmortem-2026-07-checkout-pool",
    }
