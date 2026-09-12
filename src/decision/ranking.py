"""Deterministic ranking and abstention over already-scored candidates.

Separated from candidate_evaluator.py on purpose (requirement: hard constraints,
soft scoring, final ranking, and abstention must stay distinguishable steps, not
one opaque blended score):

  1. Hard-constraint elimination -- candidate_evaluator.CandidateScore.feasible
  2. Soft scoring                -- candidate_evaluator.py's four independent components
  3. Final ranking               -- this module's sort key
  4. Abstention                  -- this module's AbstentionReason + rank()
"""

from enum import Enum

from src.decision.candidate_catalogue import ABSTAIN, catalogue_order
from src.decision.candidate_evaluator import CandidateScore
from src.models.scenario import ScenarioType


class AbstentionReason(str, Enum):
    MISSING_REQUIRED_INFORMATION = "MISSING_REQUIRED_INFORMATION"
    NO_VALID_CANDIDATE = "NO_VALID_CANDIDATE"
    UNSUPPORTED_SCENARIO = "UNSUPPORTED_SCENARIO"
    TOOL_REQUIRED = "TOOL_REQUIRED"
    UNRESOLVED_TIE = "UNRESOLVED_TIE"


def _sort_key(score: CandidateScore, scenario_type: ScenarioType) -> tuple:
    """Priority 2-6 as a single lexicographic key (ascending sort => first wins):
    maximize goal_alignment, minimize suitability_assessment, maximize
    financial_objective_score, maximize liquidity_score, then fixed catalogue
    order as the tie-break of last resort."""
    return (
        -score.goal_alignment,
        score.suitability_assessment,
        -score.financial_objective_score,
        -score.liquidity_score,
        catalogue_order(scenario_type, score.candidate_id),
    )


def rank(
    scores: list[CandidateScore], scenario_type: ScenarioType
) -> tuple[str | None, list[str], list[str], AbstentionReason | None]:
    """Apply Priority 1 (elimination) then Priority 2-6 (ranking) to `scores`.

    Returns (winner_candidate_id_or_None, valid_ids, rejected_ids, abstention_reason).
    A hard-constraint violation can never be overridden by a higher soft score --
    infeasible candidates are removed from `scores` entirely before ranking runs,
    so they cannot appear anywhere in the sort.
    """
    valid = [s for s in scores if s.feasible]
    rejected = [s for s in scores if not s.feasible]
    valid_ids = [s.candidate_id for s in valid]
    rejected_ids = [s.candidate_id for s in rejected]

    if not valid:
        return None, valid_ids, rejected_ids, AbstentionReason.NO_VALID_CANDIDATE

    ranked = sorted(valid, key=lambda s: _sort_key(s, scenario_type))

    # Catalogue order is a strict total order over a finite, duplicate-free set,
    # so two candidates can never tie all the way through the sort key -- this
    # branch is unreachable by construction. Kept as an explicit, documented
    # safety valve rather than silently assuming it can't happen.
    if len(ranked) >= 2 and _sort_key(ranked[0], scenario_type) == _sort_key(ranked[1], scenario_type):
        return None, valid_ids, rejected_ids, AbstentionReason.UNRESOLVED_TIE

    return ranked[0].candidate_id, valid_ids, rejected_ids, None


__all__ = ["AbstentionReason", "rank", "ABSTAIN"]
