"""The bounded, fixed candidate catalogue for the deterministic ground-truth engine.

Distinct from `src/models/candidate.py`'s catalogue (that one belongs to the
future full LLM copilot's candidate-generation step). This one is coarser and
purpose-built for an independent, hand-auditable reference decision.

ABSTAIN is listed last in every scenario type's catalogue for schema
completeness (it is a valid `ground_truth_decision` value) but is never scored
or ranked like the substantive candidates -- see ranking.py.
"""

from src.models.scenario import ScenarioType

CATALOGUE_VERSION = "1.0.0"

ABSTAIN = "ABSTAIN"

CANDIDATE_CATALOGUE: dict[ScenarioType, list[str]] = {
    ScenarioType.BUDGETING: [
        "INCREASE_SAVINGS",
        "MAINTAIN_CURRENT_SAVINGS",
        "REDUCE_EXPENSES_FIRST",
        ABSTAIN,
    ],
    ScenarioType.DEBT_PRIORITIZATION: [
        "REPAY_LOAN",
        "INVEST",
        "SPLIT_DEBT_AND_INVESTMENT",
        "BUILD_EMERGENCY_FUND_FIRST",
        ABSTAIN,
    ],
    ScenarioType.EMERGENCY_FUND: [
        "BUILD_TO_3_MONTHS",
        "BUILD_TO_6_MONTHS",
        "BUILD_TO_9_MONTHS",
        "MAINTAIN_CURRENT",
        ABSTAIN,
    ],
    ScenarioType.INVESTMENT_ALLOCATION: [
        "CONSERVATIVE",
        "MODERATE",
        "BALANCED",
        "GROWTH",
        "AGGRESSIVE",
        ABSTAIN,
    ],
    ScenarioType.RETIREMENT: [
        "ON_TRACK",
        "INCREASE_RETIREMENT_SAVING",
        "REDUCE_RETIREMENT_SPENDING_TARGET",
        "EXTEND_RETIREMENT_HORIZON",
        ABSTAIN,
    ],
}


def substantive_candidates(scenario_type: ScenarioType) -> list[str]:
    """The catalogue for a scenario type, excluding the ABSTAIN sentinel."""
    return [c for c in CANDIDATE_CATALOGUE[scenario_type] if c != ABSTAIN]


def catalogue_order(scenario_type: ScenarioType, candidate_id: str) -> int:
    """Fixed ordinal position within the scenario's catalogue -- the tie-break
    of last resort (Priority 6). Raises if the candidate isn't in the frozen set."""
    try:
        return CANDIDATE_CATALOGUE[scenario_type].index(candidate_id)
    except ValueError as exc:
        raise ValueError(
            f"'{candidate_id}' is not in the frozen catalogue for {scenario_type.value}"
        ) from exc
