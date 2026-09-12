"""Tests for the synthetic scenario generator (simulations/generate_scenarios.py).

Uses a small synthetic user population built in-process (not the full 1000-user
data/synthetic/users.json) so the suite runs fast and stays independent of
whatever the on-disk dataset currently contains.
"""

import tempfile
from pathlib import Path

import pytest

from simulations.generate_scenarios import build_dataset, generate_scenarios, load_users
from simulations.generate_users import build_dataset as build_users_dataset
from simulations.generate_users import generate_users
from src.models.scenario import Scenario, ScenarioType
from src.models.user import GoalType
from src.utils import save_json

TEST_NUM_USERS = 60
TEST_SCENARIOS_PER_USER = 5
TEST_SEED = 42


@pytest.fixture(scope="module")
def users():
    return generate_users(num_users=TEST_NUM_USERS, seed=TEST_SEED)


@pytest.fixture(scope="module")
def scenarios(users):
    return generate_scenarios(users, num_scenarios_per_user=TEST_SCENARIOS_PER_USER, seed=TEST_SEED)


# scenario validity -----------------------------------------------------------

def test_every_scenario_is_valid_and_round_trips(scenarios):
    for scenario in scenarios:
        assert isinstance(scenario, Scenario)
        assert Scenario.model_validate_json(scenario.model_dump_json()) == scenario


def test_every_scenario_has_a_nonempty_question_and_required_information(scenarios):
    for scenario in scenarios:
        assert scenario.question.strip()
        assert len(scenario.required_information) > 0


def test_scenario_ids_are_unique(scenarios):
    ids = [s.scenario_id for s in scenarios]
    assert len(ids) == len(set(ids))


def test_expected_decision_type_matches_scenario_type(scenarios):
    for scenario in scenarios:
        assert scenario.expected_decision_type == scenario.scenario_type


# user references ---------------------------------------------------------------

def test_every_scenario_references_an_existing_user(users, scenarios):
    user_ids = {u.user_id for u in users}
    for scenario in scenarios:
        assert scenario.user_id in user_ids


def test_every_user_gets_exactly_num_scenarios_per_user(users, scenarios):
    by_user: dict[str, int] = {}
    for scenario in scenarios:
        by_user[scenario.user_id] = by_user.get(scenario.user_id, 0) + 1
    assert set(by_user) == {u.user_id for u in users}
    assert all(count == TEST_SCENARIOS_PER_USER for count in by_user.values())


# no invented facts ----------------------------------------------------------------

def test_relevant_user_attributes_are_never_invented(users, scenarios):
    """Every value in relevant_user_attributes must be a literal copy of a field on
    the referenced user -- the core requirement of this phase."""
    users_by_id = {u.user_id: u for u in users}
    for scenario in scenarios:
        user = users_by_id[scenario.user_id]
        dumped_user = user.model_dump(mode="json")
        for field, value in scenario.relevant_user_attributes.items():
            assert field in dumped_user, f"{field} is not a real User field"
            assert dumped_user[field] == value, (
                f"{scenario.scenario_id}: relevant_user_attributes[{field}]={value!r} does not "
                f"match the referenced user's actual value {dumped_user[field]!r}"
            )


def test_required_information_matches_relevant_attribute_keys(scenarios):
    for scenario in scenarios:
        assert set(scenario.required_information) == set(scenario.relevant_user_attributes.keys())


def test_debt_scenarios_never_fabricate_a_loan_for_loan_free_users(users, scenarios):
    users_by_id = {u.user_id: u for u in users}
    debt_scenarios = [s for s in scenarios if s.scenario_type is ScenarioType.DEBT_PRIORITIZATION]
    loan_free_debt_scenarios = [s for s in debt_scenarios if not users_by_id[s.user_id].loans]
    assert loan_free_debt_scenarios, "expected at least one loan-free user in this sample"
    for scenario in loan_free_debt_scenarios:
        assert scenario.relevant_user_attributes.get("loans") == []
        assert "loan or invest it" not in scenario.question  # that template needs a real loan


def test_retirement_scenarios_only_cite_a_target_when_the_goal_exists(users, scenarios):
    users_by_id = {u.user_id: u for u in users}
    retirement_scenarios = [s for s in scenarios if s.scenario_type is ScenarioType.RETIREMENT]
    for scenario in retirement_scenarios:
        user = users_by_id[scenario.user_id]
        has_retirement_goal = any(g.goal_type == GoalType.RETIREMENT for g in user.financial_goals)
        if "saved by retirement" in scenario.question:
            assert has_retirement_goal, (
                f"{scenario.scenario_id} cites a retirement target but the user has no "
                "RETIREMENT goal in their profile"
            )


# scenario distribution -------------------------------------------------------------

def test_scenario_type_distribution_is_balanced(users, scenarios):
    counts: dict[ScenarioType, int] = {t: 0 for t in ScenarioType}
    for scenario in scenarios:
        counts[scenario.scenario_type] += 1
    # NUM_SCENARIOS_PER_USER == number of scenario types, so each type should
    # appear exactly once per user.
    for scenario_type, count in counts.items():
        assert count == len(users), f"{scenario_type} appeared {count} times, expected {len(users)}"


def _write_users_file(users) -> Path:
    dataset = build_users_dataset(users, num_users=len(users), seed=TEST_SEED)
    path = Path(tempfile.mkdtemp()) / "users.json"
    save_json(dataset, path)
    return path


def test_build_dataset_reports_scenario_distribution(users, scenarios):
    dataset = build_dataset(
        scenarios,
        num_users=len(users),
        num_scenarios_per_user=TEST_SCENARIOS_PER_USER,
        seed=TEST_SEED,
        source_users_path=_write_users_file(users),
    )
    distribution = dataset["metadata"]["scenario_distribution"]
    assert set(distribution) == {t.value for t in ScenarioType}
    assert sum(distribution.values()) == len(scenarios)
    assert dataset["metadata"]["num_scenarios"] == len(scenarios)
    assert dataset["metadata"]["random_seed"] == TEST_SEED


# deterministic regeneration ---------------------------------------------------------

def test_generation_is_deterministic_for_a_given_seed(users):
    first = generate_scenarios(users, num_scenarios_per_user=TEST_SCENARIOS_PER_USER, seed=TEST_SEED)
    second = generate_scenarios(users, num_scenarios_per_user=TEST_SCENARIOS_PER_USER, seed=TEST_SEED)
    assert [s.model_dump() for s in first] == [s.model_dump() for s in second]


def test_different_seed_changes_at_least_some_question_choices(users):
    a = generate_scenarios(users, num_scenarios_per_user=TEST_SCENARIOS_PER_USER, seed=1)
    b = generate_scenarios(users, num_scenarios_per_user=TEST_SCENARIOS_PER_USER, seed=2)
    questions_a = [s.question for s in a]
    questions_b = [s.question for s in b]
    assert questions_a != questions_b


# loading users.json -------------------------------------------------------------------

def test_load_users_rejects_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_users(tmp_path / "does_not_exist.json")


def test_load_users_rejects_empty_dataset(tmp_path):
    from src.utils import save_json

    path = tmp_path / "empty_users.json"
    save_json({"metadata": {}, "users": []}, path)
    with pytest.raises(ValueError):
        load_users(path)


def test_num_scenarios_per_user_must_be_positive(users):
    with pytest.raises(ValueError):
        generate_scenarios(users, num_scenarios_per_user=0, seed=TEST_SEED)
