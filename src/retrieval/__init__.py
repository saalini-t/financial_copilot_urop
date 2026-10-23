"""Retrieval over the financial RAG pilot corpus.

src.retrieval.corpus: deterministic PDF extraction + per-page chunking for
the 5 documents approved in docs/dataset_cards/financial_corpus.md.
src.retrieval.bm25_index: a BM25Okapi wrapper returning evidence records.

Not wired into src.agents.rag or any other agent yet -- this is a standalone
retrieval index, built and tested on its own, per a separate approval step.
It must not be mistaken for a working RAG configuration.
"""
