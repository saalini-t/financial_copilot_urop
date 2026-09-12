"""Reproducibility utilities: seeding, experiment IDs, JSON round trip."""

import random

import numpy as np

from src.models.user import FinancialLiteracy, RiskTolerance, User
from src.utils import load_json, new_experiment_id, save_json, set_seed


def test_set_seed_makes_random_reproducible():
    set_seed(7)
    first = [random.random() for _ in range(5)]
    set_seed(7)
    second = [random.random() for _ in range(5)]
    assert first == second


def test_set_seed_makes_numpy_reproducible():
    set_seed(11)
    first = np.random.rand(5)
    set_seed(11)
    second = np.random.rand(5)
    assert np.array_equal(first, second)


def test_new_experiment_id_is_unique_and_prefixed():
    ids = {new_experiment_id("full_copilot") for _ in range(20)}
    assert len(ids) == 20
    assert all(i.startswith("full_copilot-") for i in ids)


def test_save_and_load_json_round_trips_a_model(tmp_path):
    user = User(
        user_id="U000002",
        age=41,
        monthly_income=95000,
        monthly_expenses=41000,
        savings=120000,
        assets=300000,
        liabilities=0,
        risk_tolerance=RiskTolerance.MODERATE,
        investment_horizon_years=15,
        emergency_fund_target=246000,
        liquidity_requirements=41000,
        financial_literacy=FinancialLiteracy.HIGH,
    )
    out_path = tmp_path / "user.json"
    save_json(user, out_path)

    restored = load_json(out_path)
    assert restored["user_id"] == "U000002"
    assert User.model_validate(restored) == user
