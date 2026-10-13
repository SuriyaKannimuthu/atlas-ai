"""Log search tool (mock log store)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.tools.base import PermanentToolError, ToolSpec
from app.tools.mock_data import MockData, parse_ts

_LEVELS = {"DEBUG": 10, "INFO": 20, "WARN": 30, "ERROR": 40}


class LogSearchInput(BaseModel):
    service: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9-]+$")
    start: datetime
    end: datetime
    min_level: str = Field(default="INFO", pattern=r"^(DEBUG|INFO|WARN|ERROR)$")
    contains: str | None = Field(default=None, max_length=200)
    limit: int = Field(default=500, ge=1, le=2000)

    @model_validator(mode="after")
    def _window(self) -> LogSearchInput:
        if self.end <= self.start:
            raise ValueError("end must be after start")
        if (self.end - self.start).total_seconds() > 7 * 24 * 3600:
            raise ValueError("search window may not exceed 7 days")
        return self


def make_log_tools(data: MockData) -> list[ToolSpec]:
    known_services = {service["name"] for service in data.services}

    def search(args: LogSearchInput) -> list[dict]:
        if args.service not in known_services:
            raise PermanentToolError(f"unknown service {args.service!r}")
        threshold = _LEVELS[args.min_level]
        needle = args.contains.lower() if args.contains else None
        rows = [
            row
            for row in data.logs
            if row["service"] == args.service
            and args.start <= parse_ts(row["timestamp"]) < args.end
            and _LEVELS.get(row["level"], 0) >= threshold
            and (needle is None or needle in row["message"].lower())
        ]
        return rows[: args.limit]

    return [
        ToolSpec(
            name="logs.search",
            description="Search aggregated service logs within a bounded time window.",
            input_model=LogSearchInput,
            func=search,
        )
    ]
