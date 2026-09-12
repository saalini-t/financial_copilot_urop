"""Configuration 2 -- RAG.

Allowed inputs: the scenario's question (via ExperimentInput) plus evidence
retrieval. Cited evidence, no personalized profile reasoning beyond what the
scenario itself already states. `run()` has no profile parameter, same as
baseline.py -- structurally, this configuration cannot receive a User record.

No retrieval is implemented yet -- Phase 6A freezes the contract only.
"""

from __future__ import annotations

from src.agents._stub import build_stub_output
from src.models.experiment import ConfigurationName, ExecutionMetadata, ExperimentInput
from src.models.response import ExperimentOutput


def run(experiment_input: ExperimentInput, run_id: str, execution_metadata: ExecutionMetadata) -> ExperimentOutput:
    return build_stub_output(experiment_input, ConfigurationName.RAG, run_id, execution_metadata)
