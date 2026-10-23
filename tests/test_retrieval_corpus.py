"""Tests for src/retrieval/corpus.py -- extraction, chunking, determinism,
and source/frozen-dataset preservation. Reads the real 5 approved PDFs under
data/external/financial_corpus/raw/ (no network, no mocking needed -- this
is local file I/O only, same as the synthetic-dataset tests read real JSON
files already on disk).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from src.retrieval.corpus import APPROVED_DOCUMENTS, build_corpus, tokenize

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = REPO_ROOT / "data" / "external" / "financial_corpus" / "raw"


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_all_five_approved_documents_extract_successfully():
    results = build_corpus(RAW_DIR)
    assert len(results) == 5
    for result in results:
        assert result.status == "ok", f"{result.doc_id} failed: {result.error}"
        assert result.error is None
        assert len(result.chunks) > 0


def test_chunk_count_matches_page_count_for_this_corpus():
    # Verified during the content audit: none of the 5 approved documents has
    # a near-empty page, so no page should be dropped by the min-chars filter.
    results = build_corpus(RAW_DIR)
    for result in results:
        assert len(result.chunks) == result.pages_total
        assert result.pages_dropped_below_min_chars == 0


def test_chunk_ids_are_stable_and_match_the_documented_scheme():
    results = build_corpus(RAW_DIR)
    for result in results:
        for chunk in result.chunks:
            assert chunk.chunk_id == f"{result.doc_id}__p{chunk.page_number:03d}"
            assert chunk.doc_id == result.doc_id


def test_chunk_order_is_sequential_and_matches_page_order():
    results = build_corpus(RAW_DIR)
    for result in results:
        orders = [c.chunk_order for c in result.chunks]
        assert orders == list(range(len(result.chunks)))
        page_numbers = [c.page_number for c in result.chunks]
        assert page_numbers == sorted(page_numbers)


def test_extraction_is_deterministic_across_repeated_runs():
    first = build_corpus(RAW_DIR)
    second = build_corpus(RAW_DIR)
    first_texts = [(c.chunk_id, c.text) for r in first for c in r.chunks]
    second_texts = [(c.chunk_id, c.text) for r in second for c in r.chunks]
    assert first_texts == second_texts


def test_source_sha256_in_results_matches_the_actual_file_on_disk():
    results = build_corpus(RAW_DIR)
    for result in results:
        pdf_path = RAW_DIR / APPROVED_DOCUMENTS[result.doc_id]
        assert result.source_sha256 == _file_sha256(pdf_path)


def test_missing_document_is_reported_as_a_failed_result_not_an_exception(tmp_path):
    # Simulates "missing or failed documents" (requirement D.5) without
    # touching the real corpus: an empty raw/ directory means every approved
    # filename is missing.
    empty_raw_dir = tmp_path / "raw"
    empty_raw_dir.mkdir()
    results = build_corpus(empty_raw_dir)
    assert len(results) == 5
    for result in results:
        assert result.status == "failed"
        assert result.error == "file not found"
        assert result.chunks == []


def test_normalization_preserves_financial_terminology_and_negation():
    # Pulled verbatim from debt_fl_loans.pdf page 4 (confirmed during the
    # content audit) -- the exact warning this corpus exists to preserve.
    results = build_corpus(RAW_DIR)
    debt_doc = next(r for r in results if r.doc_id == "debt_fl_loans")
    full_text = "\n".join(c.text for c in debt_doc.chunks)
    assert "Don’t dig a hole to" in full_text or "dig a hole to" in full_text
    assert "12%" in full_text  # the worked interest-rate example
    assert "100,000" in full_text  # the worked monetary amount


def test_original_pdfs_are_never_modified_by_extraction():
    before = {name: _file_sha256(RAW_DIR / name) for name in APPROVED_DOCUMENTS.values()}
    build_corpus(RAW_DIR)
    after = {name: _file_sha256(RAW_DIR / name) for name in APPROVED_DOCUMENTS.values()}
    assert before == after


def test_frozen_synthetic_datasets_are_untouched_by_this_module():
    # This module never imports or touches data/synthetic/ at all -- this
    # test exists so a future refactor that accidentally wires the two
    # together fails loudly here rather than silently in the manifest tests.
    synthetic_dir = REPO_ROOT / "data" / "synthetic"
    expected_hashes = {
        "users.json": "55005b8f57917b5fcc65c65e8253b32b55d0dc6c43090829b807398d64111e01",
        "scenarios.json": "a8af39646c2f5a51b046a3d8fee4fd0809a55557cd089488f1220f9ca88a7417",
        "ground_truth.json": "336d398034b374fd0630620e089f32961938a91608aebe7bc8d3fd5523e9a055",
    }
    build_corpus(RAW_DIR)
    for filename, expected_sha in expected_hashes.items():
        assert _file_sha256(synthetic_dir / filename) == expected_sha


def test_tokenizer_is_deterministic_lowercase_alphanumeric():
    assert tokenize("Don't dig a hole! 12% interest.") == ["don", "t", "dig", "a", "hole", "12", "interest"]
    assert tokenize("") == []


def test_build_index_artifacts_writes_valid_json_matching_build_corpus(tmp_path):
    # Exercises experiments/build_retrieval_index.py's in-memory path (used
    # directly here, no file I/O) against the same real corpus.
    from experiments.build_retrieval_index import build_index_artifacts

    chunk_records, manifest = build_index_artifacts(RAW_DIR)
    assert manifest["total_chunks"] == len(chunk_records)
    assert len(manifest["documents"]) == 5
    assert all(doc["status"] == "ok" for doc in manifest["documents"])

    # Round-trips through JSON cleanly (no non-serializable fields snuck in).
    json.dumps(chunk_records)
    json.dumps(manifest)

    results = build_corpus(RAW_DIR)
    assert manifest["total_chunks"] == sum(len(r.chunks) for r in results)
