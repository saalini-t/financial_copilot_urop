"""Tests for the synthetic household dataset generator (simulations/generate_users.py).

Uses a smaller user count than the production default (NUM_USERS=1000) so the
suite runs fast, while staying large enough to exercise every edge-case category
and to make the correlation/variation checks meaningful.
"""

import numpy as np
import pytest

from simulations.generate_users import (
    EDGE_CASE_CATEGORIES,
    build_dataset,
    compute_summary,
    generate_users,
)
from src.models.user import FinancialLiteracy, GoalType, LoanType, RiskTolerance, User

TEST_NUM_USERS = 150
TEST_SEED = 42


@pytest.fixture(scope="module")
def users() -> list[User]:
    return generate_users(num_users=TEST_NUM_USERS, seed=TEST_SEED)


# 1. deterministic generation -------------------------------------------------

def test_generation_is_deterministic_for_a_given_seed():
    first = generate_users(num_users=50, seed=TEST_SEED)
    second = generate_users(num_users=50, seed=TEST_SEED)
    assert [u.model_dump() for u in first] == [u.model_dump() for u in second]


# 2. schema validity -----------------------------------------------------------

def test_every_record_is_a_valid_user_and_round_trips(users):
    for user in users:
        assert isinstance(user, User)
        assert User.model_validate_json(user.model_dump_json()) == user


# 3. required fields ------------------------------------------------------------

REQUIRED_FIELDS = {
    "user_id", "age", "monthly_income", "monthly_expenses", "savings", "assets",
    "liabilities", "loans", "loan_interest_rates", "risk_tolerance",
    "investment_horizon_years", "emergency_fund_target", "financial_goals",
    "liquidity_requirements", "financial_literacy",
}


def test_every_record_has_every_required_field(users):
    dumped = users[0].model_dump(mode="json")
    assert REQUIRED_FIELDS.issubset(dumped.keys())
    for user in users:
        assert REQUIRED_FIELDS.issubset(user.model_dump(mode="json").keys())


# 4. value ranges ----------------------------------------------------------------

def test_value_ranges_hold_for_every_user(users):
    for user in users:
        assert 18 <= user.age <= 80
        assert user.monthly_income > 0
        assert user.monthly_expenses >= 0
        assert user.savings >= 0
        assert user.assets >= user.savings
        assert user.liabilities >= sum(loan.balance for loan in user.loans)
        assert all(loan.balance >= 0 for loan in user.loans)
        assert all(loan.interest_rate >= 0 for loan in user.loans)
        assert user.investment_horizon_years > 0
        assert user.emergency_fund_target >= 0
        assert user.risk_tolerance in set(RiskTolerance)
        assert user.financial_literacy in set(FinancialLiteracy)


# 5. no duplicate user IDs --------------------------------------------------------

def test_no_duplicate_user_ids(users):
    ids = [user.user_id for user in users]
    assert len(ids) == len(set(ids))


# 6. loan / liability consistency -------------------------------------------------

def test_liabilities_are_never_less_than_total_loan_balance(users):
    for user in users:
        total_loans = sum(loan.balance for loan in user.loans)
        assert user.liabilities >= total_loans - 1e-6


# 7. expense / income consistency -------------------------------------------------

def test_expenses_are_positively_correlated_with_income(users):
    incomes = np.array([u.monthly_income for u in users])
    expenses = np.array([u.monthly_expenses for u in users])
    correlation = np.corrcoef(incomes, expenses)[0, 1]
    assert correlation > 0.5, f"expected expenses to track income, got corr={correlation}"


# 8. emergency-fund relationship --------------------------------------------------

def test_emergency_fund_target_is_correlated_with_expenses(users):
    expenses = np.array([u.monthly_expenses for u in users])
    targets = np.array([u.emergency_fund_target for u in users])
    correlation = np.corrcoef(expenses, targets)[0, 1]
    assert correlation > 0.5, f"expected emergency fund target to track expenses, got corr={correlation}"


# 9. investment-horizon validity ---------------------------------------------------

def test_investment_horizon_is_compatible_with_age(users):
    # A generous global bound: nobody's horizon implies working/investing past 100.
    for user in users:
        assert user.age + user.investment_horizon_years <= 100, (
            f"{user.user_id}: age {user.age} + horizon {user.investment_horizon_years} "
            "is not a plausible combination"
        )


# 10. categorical values -------------------------------------------------------------

def test_categorical_fields_use_only_allowed_values(users):
    allowed_risk = {"low", "moderate", "high"}
    allowed_literacy = {"low", "medium", "high"}
    allowed_loan_types = {t.value for t in LoanType}
    allowed_goal_types = {t.value for t in GoalType}
    for user in users:
        assert user.risk_tolerance.value in allowed_risk
        assert user.financial_literacy.value in allowed_literacy
        for loan in user.loans:
            assert loan.loan_type.value in allowed_loan_types
        for goal in user.financial_goals:
            assert goal.goal_type.value in allowed_goal_types


# 11. reproducibility using the same seed --------------------------------------------

def test_full_dataset_payload_is_reproducible_excluding_timestamp():
    users_a = generate_users(num_users=40, seed=7)
    users_b = generate_users(num_users=40, seed=7)
    dataset_a = build_dataset(users_a, num_users=40, seed=7)
    dataset_b = build_dataset(users_b, num_users=40, seed=7)

    assert dataset_a["users"] == dataset_b["users"]
    meta_a = {k: v for k, v in dataset_a["metadata"].items() if k != "generated_at"}
    meta_b = {k: v for k, v in dataset_b["metadata"].items() if k != "generated_at"}
    assert meta_a == meta_b
    # The timestamp is metadata only -- it's allowed (expected) to differ.
    assert "generated_at" in dataset_a["metadata"]


# 12. different output using a different seed ------------------------------------------

def test_different_seeds_produce_different_datasets():
    users_a = generate_users(num_users=40, seed=1)
    users_b = generate_users(num_users=40, seed=2)
    assert [u.model_dump() for u in users_a] != [u.model_dump() for u in users_b]


# Meaningful variation, not just internal consistency ------------------------------------

def test_dataset_contains_meaningful_variation(users):
    incomes = [u.monthly_income for u in users]
    assert np.std(incomes) > 5_000, "monthly_income should vary substantially across users"

    ages = {u.age for u in users}
    assert len(ages) > 10, "expected a meaningful spread of ages"

    assert len({u.risk_tolerance for u in users}) == 3
    assert len({u.financial_literacy for u in users}) == 3

    pct_with_loans = sum(1 for u in users if u.loans) / len(users)
    assert 0.1 < pct_with_loans < 0.95, "loans should be common but not universal"


# Edge-case coverage (section 6 of the Phase 3 brief) --------------------------------------

def test_every_edge_case_category_is_represented(users):
    # Every category should be reachable at this dataset size; each check below is a
    # necessary condition for at least one member of its category to be present.
    assert any(not user.loans for user in users), "expected at least one no_loans user"
    assert any(len(user.financial_goals) >= 4 for user in users), "expected a multiple_goals user"
    assert any(not user.financial_goals for user in users), "expected a no_goals user"
    assert any(user.savings < 500.01 for user in users), "expected a very_low_savings user"
    assert any(
        user.savings < user.emergency_fund_target for user in users
    ), "expected a user with insufficient emergency savings"
    assert any(user.investment_horizon_years <= 3 for user in users), "expected a short_horizon user"
    assert any(user.investment_horizon_years >= 30 for user in users), "expected a long_horizon user"
    assert any(user.monthly_expenses >= user.monthly_income * 0.94 for user in users), (
        "expected a high_expense_ratio user"
    )


def test_edge_case_category_count_scales_with_dataset_size():
    small = generate_users(num_users=len(EDGE_CASE_CATEGORIES), seed=TEST_SEED)
    assert len(small) == len(EDGE_CASE_CATEGORIES)


# compute_summary sanity -------------------------------------------------------------------

def test_compute_summary_reports_expected_keys(users):
    summary = compute_summary(users)
    assert summary["num_users"] == len(users)
    for key in ("age", "monthly_income", "monthly_expenses"):
        assert {"mean", "median", "min", "max"} <= summary[key].keys()
    assert "correlations_for_validation_only" in summary
    correlations = summary["correlations_for_validation_only"]
    for key in (
        "income_vs_expenses",
        "income_vs_assets",
        "age_vs_assets",
        "expenses_vs_emergency_fund_target",
        "income_vs_savings",
    ):
        assert key in correlations
        assert -1.0 <= correlations[key] <= 1.0


def test_num_users_must_be_positive():
    with pytest.raises(ValueError):
        generate_users(num_users=0, seed=TEST_SEED)
