"""The four experiment configurations -- baseline, rag, personalized, full_copilot.

Phase 6A: each module exposes a `run()` function conforming to the frozen
input/output contract (src/models/experiment.py, src/models/response.py), but
none of them contains real reasoning yet -- every call returns a clearly
labeled placeholder (see src/agents/_stub.py). No LLM call, retrieval, or
tool logic is implemented anywhere in this package yet; do not mistake a
run() call for a working component.
"""
