"""The system's decision for one scenario, deterministic-engine or system-under-test alike."""

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field

from src.models.candidate import CandidateEvaluation


class Decision(BaseModel):
    decision_id: str
    scenario_id: str
    selected_candidate: Optional[str] = Field(
        default=None, description="Catalogue candidate_id; None if abstained"
    )
    confidence: float = Field(ge=0, le=1)
    abstained: bool
    abstention_reason: Optional[str] = None
    evaluated_candidates: list[CandidateEvaluation] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
