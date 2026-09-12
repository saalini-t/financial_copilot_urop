"""The frozen candidate catalogue (Experiment Freeze, section 2) and per-candidate scoring.

The catalogue is finite, version-controlled, and identical across every experiment
configuration. Nothing in this module calls an LLM: candidate identity and catalogue
order are fixed data, not generated.
"""

from pydantic import BaseModel, Field

from src.models.scenario import ScenarioType

CATALOGUE_VERSION = "1.0.0"

CANDIDATE_CATALOGUE: dict[ScenarioType, list[str]] = {
    ScenarioType.BUDGETING: [
        "maintain_current_budget",
        "reduce_discretionary_spending",
        "increase_monthly_savings",
        "reduce_savings_target",
    ],
    ScenarioType.DEBT_PRIORITIZATION: [
        "repay_high_interest_debt",
        "repay_low_interest_debt",
        "split_between_debt_and_savings",
        "maintain_cash",
        "invest_surplus",
    ],
    ScenarioType.EMERGENCY_FUND: [
        "build_to_3_months",
        "build_to_6_months",
        "maintain_current_level",
        "increase_monthly_contribution",
    ],
    ScenarioType.INVESTMENT_ALLOCATION: [
        "conservative_allocation",
        "moderate_allocation",
        "growth_allocation",
        "preserve_liquidity",
        "debt_first",
    ],
    ScenarioType.RETIREMENT: [
        "increase_retirement_contribution",
        "maintain_contribution",
        "delay_retirement",
        "reduce_retirement_target",
        "increase_current_savings",
    ],
}

# Scenario types for which liquidity_score participates in ranking and confidence
# (Experiment Freeze, section 2 / section 6). Open question 4 in that document
# still needs sign-off on this exact set.
LIQUIDITY_RELEVANT_SCENARIOS: set[ScenarioType] = {
    ScenarioType.DEBT_PRIORITIZATION,
    ScenarioType.EMERGENCY_FUND,
    ScenarioType.INVESTMENT_ALLOCATION,
}


class Candidate(BaseModel):
    candidate_id: str
    scenario_type: ScenarioType
    parameters: dict = Field(default_factory=dict)
    catalogue_version: str = CATALOGUE_VERSION


def get_candidates(scenario_type: ScenarioType) -> list[Candidate]:
    """Return the frozen catalogue for a scenario type, in fixed catalogue order."""
    return [
        Candidate(candidate_id=candidate_id, scenario_type=scenario_type)
        for candidate_id in CANDIDATE_CATALOGUE[scenario_type]
    ]


def catalogue_order(scenario_type: ScenarioType, candidate_id: str) -> int:
    """Fixed ordinal position of a candidate within its scenario (tie-break of last resort)."""
    try:
        return CANDIDATE_CATALOGUE[scenario_type].index(candidate_id)
    except ValueError as exc:
        raise ValueError(
            f"'{candidate_id}' is not in the frozen catalogue for {scenario_type.value}"
        ) from exc


class CandidateEvaluation(BaseModel):
    """One candidate's score against a specific user + scenario (Experiment Freeze, section 3)."""

    candidate_id: str
    feasible: bool
    hard_constraint_violations: list[str] = Field(default_factory=list)
    goal_alignment_score: float = Field(ge=0, le=1)
    suitability_score: float = Field(ge=0, le=1, description="1 = fully suitable / lowest risk")
    financial_objective_score: float = Field(ge=0, le=1)
    liquidity_score: float = Field(ge=0, le=1)
    total_score: float = Field(description="Composite score used for confidence only, never for ranking")
    rejection_reasons: list[str] = Field(default_factory=list)
