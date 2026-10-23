"""Deterministic extraction and chunking for the financial RAG pilot corpus.

Scope: the 5 documents approved in docs/dataset_cards/financial_corpus.md
(round 2), one per synthetic-benchmark scenario type. This module only reads
PDFs and produces chunk records -- it never writes to or modifies the
original files under data/external/financial_corpus/raw/.

Chunking strategy: one chunk per PDF page. Checked during the content audit:
every page in this 5-document corpus is already a self-contained unit (one
NCFE "fundamental message" or one slide), and the largest page is under
2,000 characters -- so page boundaries naturally avoid splitting a warning
or financial rule away from its surrounding context, without needing an
arbitrary sliding window. chunk_id = f"{doc_id}__p{page_number:03d}" is
stable across rebuilds as long as the source PDF's page content doesn't
change (verified by source_sha256 in the manifest).

Extraction uses PyMuPDF (`fitz`), already validated by hand against this
exact corpus during the content audit -- reusing it here rather than
introducing a second PDF library.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

import fitz  # PyMuPDF

MIN_CHUNK_CHARS = 20  # drops pages that are pure page-number artifacts, e.g. a failed scan

# The 5 documents approved in docs/dataset_cards/financial_corpus.md (round 2).
# Listed explicitly, not globbed from raw/, so adding an unreviewed PDF to that
# directory never silently enters the corpus.
APPROVED_DOCUMENTS: dict[str, str] = {
    "budgeting_how_to_plan_your_budget": "budgeting_how_to_plan_your_budget.pdf",
    "debt_fl_loans": "debt_fl_loans.pdf",
    "emergency_savings": "emergency_savings.pdf",
    "investment_investor_guide": "investment_investor_guide.pdf",
    "retirement_retirement_planning": "retirement_retirement_planning.pdf",
}


def _sha256_of_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def _normalize_page_text(raw_text: str) -> str:
    """Conservative normalization only: strip trailing whitespace per line and
    collapse repeated blank lines. Never lowercases, strips punctuation, or
    removes digits/currency symbols/negations -- that would destroy the
    financial terminology, percentages, monetary amounts, and warnings
    (e.g. "don't", "not") this corpus exists to preserve. Case-folding for
    search happens only inside the BM25 tokenizer (src/retrieval/bm25_index.py),
    never here, so the stored chunk text always matches the source document."""
    lines = [line.rstrip() for line in raw_text.splitlines()]
    normalized_lines: list[str] = []
    previous_blank = False
    for line in lines:
        is_blank = line.strip() == ""
        if is_blank and previous_blank:
            continue
        normalized_lines.append(line)
        previous_blank = is_blank
    return "\n".join(normalized_lines).strip()


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    doc_id: str
    source_path: str
    page_number: int
    chunk_order: int
    text: str
    char_count: int = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "char_count", len(self.text))


@dataclass
class DocumentExtractionResult:
    doc_id: str
    source_path: str
    source_sha256: str
    pages_total: int
    chunks: list[Chunk]
    pages_dropped_below_min_chars: int
    status: str  # "ok" or "failed"
    error: str | None = None


def extract_and_chunk_document(doc_id: str, pdf_path: Path, raw_dir: Path) -> DocumentExtractionResult:
    """Extract and chunk one PDF. Never raises on a per-document failure --
    returns a `status="failed"` result instead, so one bad document in a
    future, larger corpus can't abort the whole build (requirement D.5)."""
    relative_source = pdf_path.relative_to(raw_dir.parent).as_posix()
    try:
        source_sha256 = _sha256_of_file(pdf_path)
        doc = fitz.open(pdf_path)
    except Exception as exc:  # noqa: BLE001 -- deliberately broad: any open/read failure is "this document failed"
        return DocumentExtractionResult(
            doc_id=doc_id,
            source_path=relative_source,
            source_sha256="",
            pages_total=0,
            chunks=[],
            pages_dropped_below_min_chars=0,
            status="failed",
            error=f"{type(exc).__name__}: {exc}",
        )

    chunks: list[Chunk] = []
    dropped = 0
    try:
        for page_index, page in enumerate(doc):
            page_number = page_index + 1
            normalized = _normalize_page_text(page.get_text())
            if len(normalized) < MIN_CHUNK_CHARS:
                dropped += 1
                continue
            chunks.append(
                Chunk(
                    chunk_id=f"{doc_id}__p{page_number:03d}",
                    doc_id=doc_id,
                    source_path=relative_source,
                    page_number=page_number,
                    chunk_order=len(chunks),
                    text=normalized,
                )
            )
        pages_total = doc.page_count
    finally:
        doc.close()

    return DocumentExtractionResult(
        doc_id=doc_id,
        source_path=relative_source,
        source_sha256=source_sha256,
        pages_total=pages_total,
        chunks=chunks,
        pages_dropped_below_min_chars=dropped,
        status="ok",
    )


def build_corpus(raw_dir: Path) -> list[DocumentExtractionResult]:
    """Extract and chunk every document in APPROVED_DOCUMENTS, in a fixed
    (dict-definition) order, so chunk_order and manifest contents are
    reproducible across runs regardless of filesystem directory-listing order."""
    results = []
    for doc_id, filename in APPROVED_DOCUMENTS.items():
        pdf_path = raw_dir / filename
        if not pdf_path.exists():
            results.append(
                DocumentExtractionResult(
                    doc_id=doc_id,
                    source_path=(raw_dir / filename).relative_to(raw_dir.parent).as_posix(),
                    source_sha256="",
                    pages_total=0,
                    chunks=[],
                    pages_dropped_below_min_chars=0,
                    status="failed",
                    error="file not found",
                )
            )
            continue
        results.append(extract_and_chunk_document(doc_id, pdf_path, raw_dir))
    return results


_WORD_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    """Deterministic BM25 tokenizer: lowercase, then split on runs of
    alphanumeric characters (regex `[a-z0-9]+`). No stemming, no stopword
    removal -- both would need an extra dependency or a hand-maintained list,
    and this corpus is small enough that exact-term matching is adequate for
    a first pilot. Shared by indexing and querying so both sides tokenize
    identically."""
    return _WORD_RE.findall(text.lower())
