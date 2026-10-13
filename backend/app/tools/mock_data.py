"""Read-only access to the mock integration data in `backend/data/`.

These fixtures stand in for real log stores, source control, and deployment systems so the
whole workflow can run locally and in CI. Swap the tool implementations, not the agents, to
connect real systems.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path


def parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


@dataclass(frozen=True)
class KnowledgeDoc:
    doc_id: str
    title: str
    kind: str
    services: tuple[str, ...]
    body: str


@dataclass(frozen=True)
class MockData:
    services: list[dict]
    deployments: list[dict]
    commits: list[dict]
    logs: list[dict]
    knowledge: list[KnowledgeDoc]


@lru_cache(maxsize=4)
def load_mock_data(data_dir: Path) -> MockData:
    def read(name: str) -> list[dict]:
        return json.loads((data_dir / name).read_text(encoding="utf-8"))

    docs = [_parse_doc(path) for path in sorted((data_dir / "knowledge").glob("*.md"))]
    return MockData(
        services=read("services.json"),
        deployments=read("deployments.json"),
        commits=read("commits.json"),
        logs=read("logs.json"),
        knowledge=docs,
    )


def _parse_doc(path: Path) -> KnowledgeDoc:
    text = path.read_text(encoding="utf-8")
    meta: dict[str, str] = {}
    body = text
    if text.startswith("---"):
        _, header, body = text.split("---", 2)
        for line in header.strip().splitlines():
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
    services = tuple(s.strip() for s in meta.get("services", "").split(",") if s.strip())
    return KnowledgeDoc(
        doc_id=path.stem,
        title=meta.get("title", path.stem),
        kind=meta.get("kind", "document"),
        services=services,
        body=body.strip(),
    )
