"""The common experimental output contract -- Phase 6A.

Every configuration's `run()` function (src/agents/) returns an
ExperimentOutput with this exact shape, regardless of how much of the interior
is actually implemented yet -- Phase 6A's agents are placeholder stubs (see
src/agents/_stub.py); this schema is what later phases' real implementations
must also satisfy.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator

from src.models.artifacts import Artifact, Evidence
from src.models.experiment import ConfigurationName, ExecutionMetadata


class AbstentionReason(str, Enum):
    """Experiment-level abstention reasons -- a superset tailored to
    LLM-based configurations, deliberately distinct from
    src.decision.ranking.AbstentionReason (the Phase 5 ground-truth oracle's
    own, narrower set: MISSING_REQUIRED_INFORMATION, NO_VALID_CANDIDATE,
    UNSUPPORTED_SCENARIO, TOOL_REQUIRED, UNRESOLVED_TIE). A configuration's
    abstention reason need not match the ground truth's reason for the same
    scenario -- that mismatch is itself an evaluation signal for a later
    phase, not an error here.
    """

    MISSING_REQUIRED_INFORMATION = "MISSING_REQUIRED_INFORMATION"
    NO_VALID_CANDIDATE = "NO_VALID_CANDIDATE"
    TOOL_FAILURE = "TOOL_FAILURE"
    EVIDENCE_UNAVAILABLE = "EVIDENCE_UNAVAILABLE"
    UNSUPPORTED_SCENARIO = "UNSUPPORTED_SCENARIO"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    OTHER = "OTHER"


class Confidence(BaseModel):
    """A structured stand-in for "how sure is this decision" -- never a bare
    float a model was asked to invent. `available=False` is a first-class,
    honest state: a configuration with no deterministic way to compute
    confidence (e.g. BASELINE, which has no candidate scores to take a margin
    over) must say so explicitly rather than fabricate a number that looks
    calibrated but isn't.
    """

    available: bool
    value: float | None = Field(default=None, ge=0, le=1)
    method: str = Field(description="e.g. 'deterministic_margin', 'unavailable', 'not_applicable'")
    reason: str | None = Field(default=None, description="required context when available=False")

    @model_validator(mode="after")
    def _value_matches_availability(self) -> "Confidence":
        if self.available and self.value is None:
            raise ValueError("Confidence.value is required when available=True")
        if not self.available and self.value is not None:
            raise ValueError("Confidence.value must be None when available=False")
        return self


class ExperimentOutput(BaseModel):
    experiment_id: str
    configuration: ConfigurationName
    scenario_id: str
    user_id: str
    decision: str
    abstention: bool
    abstention_reason: AbstentionReason | None = None
    explanation: str
    evidence: list[Evidence] = Field(default_factory=list)
    confidence: Confidence
    artifacts: list[Artifact] = Field(default_factory=list)
    execution_metadata: ExecutionMetadata

    @model_validator(mode="after")
    def _abstention_reason_matches_abstention(self) -> "ExperimentOutput":
        if self.abstention and self.abstention_reason is None:
            raise ValueError("abstention_reason is required when abstention=True")
        if not self.abstention and self.abstention_reason is not None:
            raise ValueError("abstention_reason must be None when abstention=False")
        return self
