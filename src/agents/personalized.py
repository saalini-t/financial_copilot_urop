"""Configuration 3 -- Personalized.

Allowed inputs: the scenario's question (via ExperimentInput) plus the
referenced user's own profile, passed explicitly as `profile` -- never looked
up or inferred internally from anything other than this parameter. Per
docs/experiment_design.md's already-frozen Configuration 3 definition,
retrieval and deterministic tools stay active (`configs/personalized.yaml`
carries the reasoning for why "no RAG/tools unless explicitly required by the
experiment design" resolves to "keep them" here); the full
constraint/guardrail pipeline (hard constraints, deterministic
confidence/abstention) stays off -- that's FULL_COPILOT-only.

No personalization logic is implemented yet -- Phase 6A freezes the contract only.
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
    return build_stub_output(experiment_input, ConfigurationName.PERSONALIZED, run_id, execution_metadata, profile=profile)
