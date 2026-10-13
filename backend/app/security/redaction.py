"""Redaction of secrets and personal data before anything is persisted or traced."""

from __future__ import annotations

import re
from typing import Any

_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?i)\b(bearer)\s+[a-z0-9._\-]{8,}"), r"\1 [REDACTED]"),
    (re.compile(r"\bsk-[A-Za-z0-9_\-]{12,}"), "[REDACTED_KEY]"),
    (re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"), "[REDACTED_AWS_KEY]"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"), "[REDACTED_GH_TOKEN]"),
    (
        re.compile(r"(?i)\b(password|passwd|secret|api[_-]?key|token)\s*[=:]\s*[^\s,;\"']+"),
        r"\1=[REDACTED]",
    ),
    (re.compile(r"(?i)(postgres(?:ql)?(?:\+\w+)?://[^:\s]+:)[^@\s]+@"), r"\1[REDACTED]@"),
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "[REDACTED_EMAIL]"),
]


def redact_text(text: str) -> str:
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def redact(value: Any) -> Any:
    """Recursively redact strings inside dicts/lists/tuples."""
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        return {key: redact(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    return value
