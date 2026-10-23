"""BM25 retrieval over the financial corpus's page-level chunks.

Deliberately the only retrieval method in this phase -- no embeddings, no
vector database, no hybrid pipeline (see docs/dataset_cards/financial_corpus.md
and the decision document's Section 3 for why: this corpus is a handful of
documents, and BM25 is small, deterministic, and auditable by a human at
that scale).

This module returns evidence records only. It never generates an
explanation or a financial recommendation -- that stays entirely separate,
per the decision document, until a later, separately-approved phase wires
this into src/agents/rag.py.
"""

from __future__ import annotations

from dataclasses import dataclass

from rank_bm25 import BM25Okapi

from src.retrieval.corpus import Chunk, tokenize

BM25_PACKAGE = "rank_bm25"
BM25_VARIANT = "BM25Okapi"
# rank_bm25's own defaults -- not tuned, since there is no ground truth to tune
# against yet. Recorded explicitly so a future change is a visible decision.
BM25_K1 = 1.5
BM25_B = 0.75


@dataclass(frozen=True)
class RetrievalResult:
    query: str
    doc_id: str
    chunk_id: str
    rank: int
    score: float
    text: str


class BM25Index:
    """Wraps rank_bm25.BM25Okapi over a fixed list of Chunks.

    Ranking/tie-breaking policy: scores come straight from BM25Okapi.
    get_scores (k1=1.5, b=0.75, its library defaults). Ties -- including the
    common case of a query matching no terms at all, where every chunk
    scores 0.0 -- are broken deterministically by ascending chunk_id, never
    by insertion order, so results are reproducible regardless of how the
    corpus was built or iterated.
    """

    def __init__(self, chunks: list[Chunk]):
        if not chunks:
            raise ValueError("BM25Index requires at least one chunk; got an empty corpus")
        self._chunks = list(chunks)
        tokenized_corpus = [tokenize(chunk.text) for chunk in self._chunks]
        self._bm25 = BM25Okapi(tokenized_corpus, k1=BM25_K1, b=BM25_B)

    def __len__(self) -> int:
        return len(self._chunks)

    def query(self, query_text: str, top_k: int = 5) -> list[RetrievalResult]:
        if query_text is None or not query_text.strip():
            raise ValueError("query_text must be a non-empty string")
        if not isinstance(top_k, int) or top_k <= 0:
            raise ValueError(f"top_k must be a positive integer, got {top_k!r}")

        query_tokens = tokenize(query_text)
        scores = self._bm25.get_scores(query_tokens)

        order = sorted(range(len(self._chunks)), key=lambda i: (-scores[i], self._chunks[i].chunk_id))
        limited = order[:top_k]

        return [
            RetrievalResult(
                query=query_text,
                doc_id=self._chunks[i].doc_id,
                chunk_id=self._chunks[i].chunk_id,
                rank=rank,
                score=float(scores[i]),
                text=self._chunks[i].text,
            )
            for rank, i in enumerate(limited, start=1)
        ]
