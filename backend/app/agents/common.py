"""Shared helpers for agents: tokenisation, error signatures, evidence construction."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from app.agents.schemas import Evidence
from app.graph.state import MAX_EVIDENCE_SUMMARY
from app.security.untrusted import looks_like_injection

_IDENT = re.compile(r"[A-Za-z][A-Za-z0-9_]*")
_CAMEL = re.compile(r"[A-Z]?[a-z0-9]+|[A-Z]+(?![a-z])")
_NOISE = frozenset(
    [
        "the",
        "and",
        "for",
        "from",
        "with",
        "into",
        "that",
        "this",
        "was",
        "were",
        "are",
        "has",
        "have",
        "not",
        "get",
        "got",
        "http",
        "https",
        "api",
        "error",
        "errors",
        "failed",
        "fail",
        "info",
        "warn",
        "true",
        "false",
        "none",
        "null",
        "return",
        "def",
        "self",
        "amount",
        "currency",
        "feat",
        "fix",
        "chore",
        "docs",
        "refactor",
        "config",
        "add",
        "update",
    ]
)

EVIDENCE_PREFIX = {"logs": "L", "code": "C", "deployment": "D", "knowledge": "K"}


def technical_tokens(text: str) -> set[str]:
    """Identifier-aware tokens: `StripeClient.create_charge` -> stripeclient, stripe, client,
    create_charge, create, charge."""
    tokens: set[str] = set()
    for ident in _IDENT.findall(text):
        lowered = ident.lower()
        tokens.add(lowered)
        for part in ident.split("_"):
            tokens.update(piece.lower() for piece in _CAMEL.findall(part))
            tokens.add(part.lower())
    return {tok for tok in tokens if len(tok) > 2 and tok not in _NOISE}


def error_signature(message: str) -> str:
    """Normalise variable parts so repeated errors cluster together."""
    signature = re.sub(r"\b[0-9a-f]{8,}\b", "<id>", message)
    signature = re.sub(r"\d+(\.\d+)?(ms|s)\b", "<dur>", signature)
    return signature.strip()[:240]


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def iso(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class EvidenceBuilder:
    """Creates evidence items with stable, human-readable IDs such as `L1.2`."""

    def __init__(self, source: str, round_: int) -> None:
        self.source = source
        self.round = round_
        self.items: list[dict[str, Any]] = []

    def add(
        self,
        kind: str,
        summary: str,
        *,
        details: dict[str, Any] | None = None,
        references: list[str] | None = None,
        timestamp: str | None = None,
        flags: list[str] | None = None,
        source: str | None = None,
    ) -> str:
        source = source or self.source
        flags = list(flags or [])
        if looks_like_injection(summary) and "possible_prompt_injection" not in flags:
            flags.append("possible_prompt_injection")
        evidence_id = f"{EVIDENCE_PREFIX[source]}{self.round}.{len(self.items) + 1}"
        item = Evidence(
            id=evidence_id,
            source=source,  # type: ignore[arg-type]
            kind=kind,
            summary=summary[:MAX_EVIDENCE_SUMMARY],
            details=details or {},
            references=references or [],
            timestamp=timestamp,
            flags=flags,
            round=self.round,
        )
        self.items.append(item.model_dump())
        return evidence_id


def evidence_digest(evidence: list[dict[str, Any]], limit: int = 40) -> str:
    """Compact evidence listing for prompts."""
    lines = []
    for item in evidence[:limit]:
        flags = f" flags={item['flags']}" if item.get("flags") else ""
        lines.append(f"[{item['id']}] ({item['source']}/{item['kind']}) {item['summary']}{flags}")
    return "\n".join(lines)


def step_result(
    step: Any, builder: EvidenceBuilder, status: str = "completed", note: str | None = None
) -> dict[str, Any]:
    """State update returned by an investigation node for one plan step."""
    return {
        "evidence": builder.items,
        "completed_steps": [
            {
                "id": step.id,
                "agent": step.agent,
                "mode": step.mode,
                "status": status,
                "evidence_count": len(builder.items),
                "note": note,
            }
        ],
    }
