"""Builds the financial-corpus retrieval index artifacts on disk.

Mirrors experiments/manifest.py's role for the synthetic benchmark: a
deterministic build step over frozen (here: approved, unmodified-since-
download) inputs, producing a versioned manifest alongside the derived
artifacts. Reads only from data/external/financial_corpus/raw/ (never
writes there) and writes chunks.json + corpus_manifest.json under
data/external/financial_corpus/index/.

Usage: python -m experiments.build_retrieval_index
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from importlib.metadata import version as package_version
from pathlib import Path

import fitz

from src.retrieval.bm25_index import BM25_B, BM25_K1, BM25_PACKAGE, BM25_VARIANT
from src.retrieval.corpus import MIN_CHUNK_CHARS, build_corpus

CORPUS_MANIFEST_VERSION = "1.0.0"

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = REPO_ROOT / "data" / "external" / "financial_corpus" / "raw"
INDEX_DIR = REPO_ROOT / "data" / "external" / "financial_corpus" / "index"


def build_index_artifacts(raw_dir: Path = RAW_DIR) -> tuple[list[dict], dict]:
    """Returns (chunk_records, manifest) without writing anything -- used
    directly by tests so they can assert on the data without touching disk."""
    results = build_corpus(raw_dir)

    chunk_records = []
    documents_manifest = []
    for result in results:
        for chunk in result.chunks:
            chunk_records.append(
                {
                    "chunk_id": chunk.chunk_id,
                    "doc_id": chunk.doc_id,
                    "source_path": chunk.source_path,
                    "page_number": chunk.page_number,
                    "chunk_order": chunk.chunk_order,
                    "text": chunk.text,
                    "char_count": chunk.char_count,
                }
            )
        documents_manifest.append(
            {
                "doc_id": result.doc_id,
                "source_path": result.source_path,
                "source_sha256": result.source_sha256,
                "pages_total": result.pages_total,
                "chunks_produced": len(result.chunks),
                "pages_dropped_below_min_chars": result.pages_dropped_below_min_chars,
                "status": result.status,
                "error": result.error,
            }
        )

    manifest = {
        "manifest_version": CORPUS_MANIFEST_VERSION,
        "built_at_utc": datetime.now(timezone.utc).isoformat(),
        "extraction": {
            "tool": "PyMuPDF",
            "tool_version": fitz.pymupdf_version,
            "method": "page.get_text()",
        },
        "chunking": {
            "strategy": "per_page",
            "min_chunk_chars": MIN_CHUNK_CHARS,
        },
        "bm25": {
            "package": BM25_PACKAGE,
            "package_version": package_version("rank-bm25"),
            "variant": BM25_VARIANT,
            "k1": BM25_K1,
            "b": BM25_B,
            "tokenizer": "lowercase_alphanumeric_regex",
        },
        "documents": documents_manifest,
        "total_chunks": len(chunk_records),
    }
    return chunk_records, manifest


def main() -> None:
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    chunk_records, manifest = build_index_artifacts()

    chunks_path = INDEX_DIR / "chunks.json"
    manifest_path = INDEX_DIR / "corpus_manifest.json"
    chunks_path.write_text(json.dumps(chunk_records, indent=2, ensure_ascii=False), encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Wrote {len(chunk_records)} chunks from {len(manifest['documents'])} documents to {chunks_path}")
    print(f"Wrote manifest to {manifest_path}")


if __name__ == "__main__":
    main()
