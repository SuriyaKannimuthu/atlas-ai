"""Side-effecting integrations (mock ticketing, chat notifications, deploy rollback).

Every call takes an idempotency key. Replaying a call with the same key returns the original
result instead of acting twice, which is what makes retries and workflow resumption safe.
"""

from __future__ import annotations

import threading
import zlib
from datetime import UTC, datetime
from typing import Annotated, Any

from pydantic import BaseModel, Field

from app.tools.base import ToolSpec

IdempotencyKey = Annotated[str, Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9:_\-]+$")]


class CreateTicketInput(BaseModel):
    idempotency_key: IdempotencyKey
    title: str = Field(min_length=3, max_length=200)
    body: str = Field(max_length=20_000)
    service: str = Field(pattern=r"^[a-z0-9-]+$")
    severity: str = Field(pattern=r"^(sev1|sev2|sev3|sev4)$")


class NotifyInput(BaseModel):
    idempotency_key: IdempotencyKey
    channel: str = Field(pattern=r"^#[a-z0-9-]+$")
    message: str = Field(max_length=4_000)


class RollbackInput(BaseModel):
    idempotency_key: IdempotencyKey
    service: str = Field(pattern=r"^[a-z0-9-]+$")
    from_deployment: str = Field(pattern=r"^d-\d{1,8}$")
    to_deployment: str = Field(pattern=r"^d-\d{1,8}$")


class IdempotentStore:
    """In-memory record of executed external actions, keyed by idempotency key."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._results: dict[str, dict[str, Any]] = {}
        self.execution_count = 0

    def run_once(self, key: str, action: Any) -> dict[str, Any]:
        with self._lock:
            if key in self._results:
                return {**self._results[key], "replayed": True}
            result = action()
            self.execution_count += 1
            self._results[key] = result
            return {**result, "replayed": False}


def make_action_tools(store: IdempotentStore) -> list[ToolSpec]:
    def now() -> str:
        return datetime.now(UTC).isoformat()

    def create_ticket(args: CreateTicketInput) -> dict:
        return store.run_once(
            args.idempotency_key,
            lambda: {
                "ticket_id": f"OPS-{zlib.crc32(args.idempotency_key.encode()) % 9000 + 1000}",
                "url": "https://tickets.example.internal/browse/OPS",
                "created_at": now(),
            },
        )

    def notify(args: NotifyInput) -> dict:
        return store.run_once(
            args.idempotency_key,
            lambda: {
                "channel": args.channel,
                "delivered_at": now(),
            },
        )

    def rollback(args: RollbackInput) -> dict:
        return store.run_once(
            args.idempotency_key,
            lambda: {
                "service": args.service,
                "rolled_back_from": args.from_deployment,
                "active_deployment": args.to_deployment,
                "status": "rollback_started",
                "started_at": now(),
            },
        )

    return [
        ToolSpec(
            "ticketing.create_ticket",
            "Create an incident ticket.",
            CreateTicketInput,
            create_ticket,
            side_effect=True,
        ),
        ToolSpec(
            "ticketing.notify",
            "Post a message to a team channel.",
            NotifyInput,
            notify,
            side_effect=True,
        ),
        ToolSpec(
            "deploy.rollback",
            "Roll a service back to a previous deployment.",
            RollbackInput,
            rollback,
            side_effect=True,
        ),
    ]
