"""Knowledge retrieval over runbooks, architecture notes, and postmortems.

Keyword retrieval (BM25 over section-level chunks). Embedding-based retrieval can be added
behind the same tool contract.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

from pydantic import BaseModel, Field

from app.tools.base import ToolSpec
from app.tools.mock_data import KnowledgeDoc, MockData

_TOKEN = re.compile(r"[a-z0-9_]+")
_STOPWORDS = frozenset(
    [
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "has",
        "in",
        "is",
        "it",
        "of",
        "on",
        "or",
        "the",
        "to",
        "was",
        "were",
        "with",
        "when",
        "this",
        "that",
        "after",
        "before",
        "during",
        "if",
        "not",
        "into",
    ]
)


def tokenize(text: str) -> list[str]:
    return [tok for tok in _TOKEN.findall(text.lower()) if tok not in _STOPWORDS and len(tok) > 1]


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    doc: KnowledgeDoc
    section: str
    text: str
    tokens: tuple[str, ...]


def chunk_documents(docs: list[KnowledgeDoc]) -> list[Chunk]:
    chunks: list[Chunk] = []
    for doc in docs:
        sections = re.split(r"^## ", doc.body, flags=re.MULTILINE)
        for index, section in enumerate(s for s in sections if s.strip()):
            heading, _, content = section.partition("\n")
            text = content.strip() or heading.strip()
            tokens = tuple(tokenize(f"{doc.title} {heading} {text}"))
            chunks.append(Chunk(f"{doc.doc_id}#{index}", doc, heading.strip(), text, tokens))
    return chunks


class BM25Index:
    def __init__(self, chunks: list[Chunk], k1: float = 1.4, b: float = 0.75) -> None:
        self.chunks = chunks
        self.k1, self.b = k1, b
        self.avg_len = sum(len(c.tokens) for c in chunks) / max(len(chunks), 1)
        doc_freq: Counter[str] = Counter()
        for chunk in chunks:
            doc_freq.update(set(chunk.tokens))
        n = len(chunks)
        self.idf = {t: math.log(1 + (n - df + 0.5) / (df + 0.5)) for t, df in doc_freq.items()}
        self.tf = [Counter(chunk.tokens) for chunk in chunks]

    def search(
        self, query: str, top_k: int, service: str | None = None
    ) -> list[tuple[Chunk, float]]:
        terms = tokenize(query)
        scored = []
        for chunk, tf in zip(self.chunks, self.tf, strict=True):
            score = 0.0
            for term in terms:
                if term not in tf:
                    continue
                freq = tf[term]
                norm = self.k1 * (1 - self.b + self.b * len(chunk.tokens) / self.avg_len)
                score += self.idf[term] * freq * (self.k1 + 1) / (freq + norm)
            if service and (service in chunk.doc.services or "all" in chunk.doc.services):
                score *= 1.25
            if score > 0:
                scored.append((chunk, score))
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:top_k]


class KnowledgeSearchInput(BaseModel):
    query: str = Field(min_length=2, max_length=500)
    service: str | None = Field(default=None, pattern=r"^[a-z0-9-]+$")
    top_k: int = Field(default=4, ge=1, le=10)


def make_retrieval_tools(data: MockData) -> list[ToolSpec]:
    index = BM25Index(chunk_documents(data.knowledge))

    def search(args: KnowledgeSearchInput) -> list[dict]:
        return [
            {
                "chunk_id": chunk.chunk_id,
                "doc_id": chunk.doc.doc_id,
                "title": chunk.doc.title,
                "kind": chunk.doc.kind,
                "section": chunk.section,
                "text": chunk.text,
                "score": round(score, 3),
            }
            for chunk, score in index.search(args.query, args.top_k, args.service)
        ]

    return [
        ToolSpec(
            "knowledge.search",
            "Search runbooks, architecture docs, and postmortems.",
            KnowledgeSearchInput,
            search,
        )
    ]
