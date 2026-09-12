"""Shared helper for the Phase 6A placeholder agents.

None of src/agents/*.py implements real reasoning yet -- every run() function
returns a clearly-labeled placeholder ExperimentOutput that satisfies the
common contract (src/models/response.py), so the contract itself can be
frozen and tested before any LLM, retrieval, or tool logic exists. Not part
of the public contract: baseline.py / rag.py / personalized.py /
full_copilot.py are the public surface.
"""

from __future__ import annotations

from src.models.artifacts import Artifact
from src.models.experiment import ConfigurationName, ExecutionMetadata, ExperimentInput, make_experiment_id
from src.models.response import AbstentionReason, Confidence, ExperimentOutput
from src.models.user import User


def build_stub_output(
    experiment_input: ExperimentInput,
    configuration: ConfigurationName,
    run_id: str,
    execution_metadata: ExecutionMetadata,
    profile: User | None = None,
) -> ExperimentOutput:
    """A syntactically valid, honestly-labeled non-answer. `profile`, when
    given, is reflected into the artifact's provenance only -- proof the
    parameter is genuinely wired through this configuration's run(), not proof
    of any actual personalization logic (there isn't any yet)."""
    experiment_id = make_experiment_id(configuration, experiment_input.scenario_id, run_id)

    provenance: dict = {
        "scenario_id": experiment_input.scenario_id,
        "user_id": experiment_input.user_id,
    }
    if profile is not None:
        provenance["profile_user_id"] = profile.user_id

    return ExperimentOutput(
        experiment_id=experiment_id,
        configuration=configuration,
        scenario_id=experiment_input.scenario_id,
        user_id=experiment_input.user_id,
        decision="NOT_IMPLEMENTED",
        abstention=True,
        abstention_reason=AbstentionReason.OTHER,
        explanation=(
            f"Phase 6A placeholder: the {configuration.value} agent has no LLM, retrieval, or "
            "tool logic implemented yet. This output only demonstrates the frozen contract."
        ),
        evidence=[],
        confidence=Confidence(
            available=False,
            method="not_applicable",
            reason="Phase 6A stub -- no reasoning implemented, so no confidence can be computed",
        ),
        artifacts=[
            Artifact(
                artifact_type="phase_6a_stub",
                source=f"src.agents.{configuration.value}",
                input={"question": experiment_input.question},
                output={"note": "placeholder only, no reasoning was performed"},
                execution_id=experiment_id,
                provenance=provenance,
            )
        ],
        execution_metadata=execution_metadata,
    )
