"""Deterministic ground-truth decision engine (Phase 5).

No LLM, RAG, embeddings, or external calls anywhere in this package. Every
module here is pure Python arithmetic and comparisons over `User` and
`Scenario` records already on disk -- see ground_truth.py for the orchestrator.

This catalogue and scoring logic is independent from `src/models/candidate.py`
(the coarser-grained catalogue frozen for the future full LLM copilot in the
experiment-design spec). The two are deliberately separate: this package exists
to produce an independent reference decision to evaluate LLM configurations
against, not to be the candidate space an LLM configuration itself uses.
"""
