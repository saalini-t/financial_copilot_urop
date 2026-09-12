"""The candidate catalogue must stay finite, ordered, and identical across configs."""

import pytest

from src.models.candidate import (
    CANDIDATE_CATALOGUE,
    LIQUIDITY_RELEVANT_SCENARIOS,
    catalogue_order,
    get_candidates,
)
from src.models.scenario import ScenarioType

EXPECTED_SIZES = {
    ScenarioType.BUDGETING: 4,
    ScenarioType.DEBT_PRIORITIZATION: 5,
    ScenarioType.EMERGENCY_FUND: 4,
    ScenarioType.INVESTMENT_ALLOCATION: 5,
    ScenarioType.RETIREMENT: 5,
}


def test_every_scenario_type_has_a_catalogue():
    assert set(CANDIDATE_CATALOGUE) == set(ScenarioType)


@pytest.mark.parametrize("scenario_type,size", EXPECTED_SIZES.items())
def test_catalogue_size_matches_frozen_spec(scenario_type, size):
    assert len(CANDIDATE_CATALOGUE[scenario_type]) == size


def test_candidate_ids_are_unique_within_scenario():
    for scenario_type, ids in CANDIDATE_CATALOGUE.items():
        assert len(ids) == len(set(ids)), f"duplicate candidate id in {scenario_type}"


def test_get_candidates_preserves_catalogue_order():
    candidates = get_candidates(ScenarioType.DEBT_PRIORITIZATION)
    assert [c.candidate_id for c in candidates] == CANDIDATE_CATALOGUE[ScenarioType.DEBT_PRIORITIZATION]


def test_catalogue_order_is_stable_and_zero_indexed():
    assert catalogue_order(ScenarioType.DEBT_PRIORITIZATION, "repay_high_interest_debt") == 0
    assert catalogue_order(ScenarioType.DEBT_PRIORITIZATION, "invest_surplus") == 4


def test_catalogue_order_rejects_unknown_candidate():
    with pytest.raises(ValueError):
        catalogue_order(ScenarioType.BUDGETING, "not_a_real_candidate")


def test_liquidity_relevance_matches_frozen_spec():
    assert LIQUIDITY_RELEVANT_SCENARIOS == {
        ScenarioType.DEBT_PRIORITIZATION,
        ScenarioType.EMERGENCY_FUND,
        ScenarioType.INVESTMENT_ALLOCATION,
    }
