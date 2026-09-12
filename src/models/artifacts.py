"""Artifact and evidence schemas.

The two explanation artifacts (architecture spec, section 9): AuditArtifact is
the structured, machine-readable source of truth, CommunicationArtifact is a
rendering of it. Nothing here enforces that rendering relationship in code yet
-- that belongs to the explanation module in a later phase -- these are the
schemas both artifacts must conform to.

`Artifact` and `Evidence` (below) are Phase 6A additions: a generic,
configuration-agnostic record of one step any agent took (retrieval, tool
call, ranking, explanation rendering) and a structured evidence citation,
respectively. Neither may ever contain chain-of-thought or a model's exposed
hidden reasoning -- only structured, inspectable input/output data. Evidence's
`source_reference` must point to something that actually exists in a
knowledge base or retrieval index; fabricating one defeats the entire point of
these fields, which exist so a claim can be checked, not just asserted.
"""

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from src.models.candidate import CandidateEvaluation
from src.models.decision import Decision


class EvidenceItem(BaseModel):
    source_id: str
    text: str
    relevance_score: float = Field(ge=0, le=1)


class ToolTraceEntry(BaseModel):
    tool_name: str
    tool_version: str
    inputs: dict = Field(default_factory=dict)
    outputs: dict = Field(default_factory=dict)


class ConstraintRecord(BaseModel):
    rule_id: str
    description: str
    binding: bool
    violated_by: list[str] = Field(default_factory=list, description="candidate_ids this rule rejected")


class AuditArtifact(BaseModel):
    retrieved_evidence: list[EvidenceItem] = Field(default_factory=list)
    tool_traces: list[ToolTraceEntry] = Field(default_factory=list)
    constraints: list[ConstraintRecord] = Field(default_factory=list)
    candidate_evaluations: list[CandidateEvaluation] = Field(default_factory=list)
    rejected_candidates: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    final_decision: Decision
    configuration: str = Field(description="config_name this decision was produced under")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class NumericalClaim(BaseModel):
    claim: str
    value: float
    source_field: str = Field(description="Pointer into the audit artifact this claim must match")


class CommunicationArtifact(BaseModel):
    recommendation: str
    explanation: str
    citations: list[str] = Field(default_factory=list)
    numerical_claims: list[NumericalClaim] = Field(default_factory=list)
    constraint_claims: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


class Artifact(BaseModel):
    """A generic, auditable record of one step a configuration's agent took.
    Every ExperimentOutput carries a list of these (src/models/response.py).
    Never a substitute for chain-of-thought -- `input`/`output` are structured
    data a human or evaluator could inspect, not a reasoning transcript."""

    artifact_type: str = Field(description="e.g. 'retrieval', 'tool_call', 'ranking', 'explanation_render'")
    source: str = Field(description="module/component that produced this artifact")
    input: dict = Field(default_factory=dict)
    output: dict = Field(default_factory=dict)
    execution_id: str = Field(description="deterministic identifier for this execution step")
    provenance: dict = Field(default_factory=dict)


class Evidence(BaseModel):
    """A structured evidence citation (Phase 6A). Distinct from EvidenceItem
    above, which is the full-copilot audit artifact's internal shape -- this is
    the leaner, configuration-agnostic form every ExperimentOutput carries."""

    evidence_id: str
    source_type: str = Field(description="e.g. 'knowledge_base', 'user_profile', 'tool_output'")
    source_reference: str = Field(description="must point to something that actually exists -- never fabricated")
    excerpt_or_fact: str
    relevance: float = Field(ge=0, le=1)
    provenance: dict = Field(default_factory=dict)
