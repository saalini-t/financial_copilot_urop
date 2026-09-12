"""The common experimental interface -- Phase 6A.

ExperimentInput is built once from a frozen Scenario record and is identical,
field for field, across all four configurations for a given scenario -- that
identity is the fairness guarantee requirement 5 of the Phase 6A brief asks
for. No configuration receives a rephrased question or an enriched snapshot
another configuration doesn't also see; `build_experiment_input` is the one
place an ExperimentInput is ever constructed, so there is no second code path
that could quietly diverge.

Synthetic user *profile* access (the full `User` record) is a separate,
explicit parameter on PERSONALIZED and FULL_COPILOT's `run()` functions in
src/agents/ -- never a field on ExperimentInput. BASELINE and RAG's `run()`
functions have no such parameter in their signatures at all, so there is no
way to pass one even by mistake; see tests/test_experiment_contracts.py for
the structural check.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from src.models.scenario import Scenario, ScenarioType


class ConfigurationName(str, Enum):
    BASELINE = "baseline"
    RAG = "rag"
    PERSONALIZED = "personalized"
    FULL_COPILOT = "full_copilot"


class ExperimentInput(BaseModel):
    """Common to all four configurations -- see module docstring."""

    user_id: str
    scenario_id: str
    scenario_type: ScenarioType
    question: str
    relevant_user_attributes: dict = Field(default_factory=dict)
    required_information: list[str] = Field(default_factory=list)


class ExecutionMetadata(BaseModel):
    """Never contains API keys, credentials, or other secrets -- experimental
    settings only. Populated from configs/*.yaml (via src.config.ExperimentConfig)
    so no agent implementation hard-codes a model name, temperature, prompt
    version, retrieval parameter, or threshold."""

    configuration: ConfigurationName
    model_identifier: str | None = None
    prompt_version: str | None = None
    dataset_version: str | None = None
    scenario_dataset_version: str | None = None
    ground_truth_version: str | None = None
    experiment_seed: int | None = None
    retrieval_configuration: dict = Field(default_factory=dict)
    tool_configuration: dict = Field(default_factory=dict)


def make_experiment_id(configuration: ConfigurationName, scenario_id: str, run_id: str) -> str:
    """Deterministic: configuration + scenario_id + run_id, nothing else -- the
    same three inputs always produce the same experiment_id. Distinct from
    src.utils.new_experiment_id, which is timestamp/uuid-based and names a
    whole experiment *run's* log directory, not one scenario's record within it.
    """
    return f"{configuration.value}__{scenario_id}__{run_id}"


def build_experiment_input(scenario: Scenario) -> ExperimentInput:
    """The single place an ExperimentInput is ever built from a Scenario. Copies
    values out (never holds a reference into the source record), so nothing a
    caller does to the result can affect the scenario dataset."""
    return ExperimentInput(
        user_id=scenario.user_id,
        scenario_id=scenario.scenario_id,
        scenario_type=scenario.scenario_type,
        question=scenario.question,
        relevant_user_attributes=dict(scenario.relevant_user_attributes),
        required_information=list(scenario.required_information),
    )
