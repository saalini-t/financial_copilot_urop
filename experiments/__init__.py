"""Phase 6B: the experiment execution/orchestration layer.

Everything here dispatches through the frozen Phase 6A agent interfaces
(src/agents/) and the frozen ExperimentInput/ExperimentOutput contracts
(src/models/experiment.py, src/models/response.py) -- it adds no reasoning of
its own. No LLM call, retrieval, tool, ranking, or evaluation logic lives in
this package.
"""
