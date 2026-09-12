"""Configuration 1 -- Baseline.

Allowed inputs: the scenario's question only (via ExperimentInput). No
retrieval, no persistent user profile, no deterministic financial tools, free-
form explanation. `run()` has no profile parameter in its signature at all --
there is no way to pass a User object to it even by mistake; this is a
structural fairness guarantee, not just a documented convention (see
tests/test_experiment_contracts.py::test_baseline_and_rag_have_no_profile_parameter).

No LLM call is implemented yet -- Phase 6A freezes the contract only.
"""

from __future__ import annotations

from src.agents._stub import build_stub_output
from src.models.experiment import ConfigurationName, ExecutionMetadata, ExperimentInput
from src.models.response import ExperimentOutput


def run(experiment_input: ExperimentInput, run_id: str, execution_metadata: ExecutionMetadata) -> ExperimentOutput:
    return build_stub_output(experiment_input, ConfigurationName.BASELINE, run_id, execution_metadata)
