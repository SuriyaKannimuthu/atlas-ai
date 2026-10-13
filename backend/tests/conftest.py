from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

API_KEYS = {
    "key-admin": {"subject": "alice", "role": "admin"},
    "key-operator": {"subject": "oscar", "role": "operator"},
    "key-approver": {"subject": "april", "role": "approver"},
    "key-viewer": {"subject": "victor", "role": "viewer"},
}

CHECKOUT = (
    "Investigate why the latest deployment of checkout-api caused an increase in API errors. "
    "Analyze the logs, inspect recent commits, identify the likely root cause, and prepare a "
    "remediation plan."
)
PAYMENTS = "payments-service is returning 502s on charges since deployment d-3107"
AUTH = "Login latency spiked for auth-service around 2026-10-12 08:00 UTC; slow sign-in"


def headers(role: str) -> dict[str, str]:
    return {"X-API-Key": f"key-{role}"}


@pytest.fixture
def make_settings(tmp_path: Path) -> Callable[..., Settings]:
    def factory(**overrides: object) -> Settings:
        values: dict[str, object] = {
            "app_env": "test",
            "database_url": f"sqlite:///{(tmp_path / 'atlas.db').as_posix()}",
            "checkpointer": "sqlite",
            "checkpoint_url": (tmp_path / "checkpoints.db").as_posix(),
            "api_keys": API_KEYS,
            "executor": "inline",
            "tool_backoff_base_s": 0.0,
            "model_provider": None,
            "model_name": None,
        }
        values.update(overrides)
        return Settings(_env_file=None, **values)  # type: ignore[arg-type]

    return factory


@pytest.fixture
def client(make_settings: Callable[..., Settings]) -> Iterator[TestClient]:
    with TestClient(create_app(make_settings())) as test_client:
        yield test_client
