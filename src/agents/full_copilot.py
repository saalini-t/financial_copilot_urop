"""Configuration 4 -- Full proposed copilot.

Allowed inputs: the scenario's question (via ExperimentInput) plus the
referenced user's own profile (via `profile`, same explicit-parameter rule as
personalized.py) -- and, once implemented, retrieval, the bounded candidate
catalogue, deterministic financial tools, hard constraints, candidate ranking,
deterministic confidence, abstention, artifact-based explanation, and an audit
log. This is the only configuration meant to exercise the full pipeline.

None of that reasoning is implemented yet -- Phase 6A freezes the contract
only. It deliberately does NOT reimplement src.decision (Phase 5's ground-
truth engine) -- that stays the independent evaluation oracle this
configuration will later be scored against, not a component it calls.
"""

from __future__ import annotations

from src.agents._stub import build_stub_output
from src.models.experiment import ConfigurationName, ExecutionMetadata, ExperimentInput
from src.models.response import ExperimentOutput
from src.models.user import User


def run(
    experiment_input: ExperimentInput,
    profile: User,
    run_id: str,
    execution_metadata: ExecutionMetadata,
) -> ExperimentOutput:
    return build_stub_output(
        experiment_input, ConfigurationName.FULL_COPILOT, run_id, execution_metadata, profile=profile
    )
