"""Generate the synthetic household financial dataset shared by every experiment
configuration (Baseline, RAG, Personalized, Full Copilot).

Phase 3 scope only: this script produces `User` records and nothing else -- no
scenarios, no ground truth, no recommendations, no LLM calls. Every field is
sampled from correlated, seeded distributions; nothing here reads or writes real
individuals' data.

Usage:
    python simulations/generate_users.py
    python simulations/generate_users.py --num-users 1000 --seed 42

Running the same command twice produces byte-identical `users` records (the
`generated_at` metadata timestamp is the only thing that changes between runs).
"""

from __future__ import annotations

import argparse
import random
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    # Allow `python simulations/generate_users.py` to find the `src` package
    # without requiring an editable install.
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np
from pydantic import ValidationError

from src.models.user import FinancialGoal, FinancialLiteracy, GoalType, Loan, LoanType, RiskTolerance, User
from src.utils import save_json, set_seed

NUM_USERS = 1000
RANDOM_SEED = 42

DATASET_VERSION = "v1.0"
GENERATOR_VERSION = "v1.0"
SCHEMA_VERSION = "1.0.0"
DEFAULT_OUTPUT_PATH = REPO_ROOT / "data" / "synthetic" / "users.json"
DEFAULT_SUMMARY_PATH = REPO_ROOT / "results" / "metrics" / "user_dataset_summary.json"

RETIREMENT_AGE = 60

# Intentionally guaranteed edge-case categories (section 6 of the Phase 3 brief).
# Each is a single, plausible override applied to an otherwise normally generated
# user -- never a pathological or internally impossible combination.
EDGE_CASE_CATEGORIES = [
    "very_low_savings",
    "high_expense_ratio",
    "high_debt_to_income",
    "no_loans",
    "no_goals",
    "multiple_goals",
    "very_high_liquidity_requirement",
    "short_horizon",
    "long_horizon",
    "insufficient_emergency_savings",
]

GOAL_POOL = list(GoalType)
LOAN_POOL = list(LoanType)


def _sample_loan(loan_type: LoanType, monthly_income: float) -> Loan:
    """Plausible synthetic loan terms by type. Not modeled on any real lender's product."""
    annual_income = monthly_income * 12
    if loan_type == LoanType.HOME:
        balance = annual_income * float(np.random.uniform(2, 6))
        rate = float(np.random.uniform(0.07, 0.11))
    elif loan_type == LoanType.VEHICLE:
        balance = float(np.random.uniform(50_000, 1_200_000))
        rate = float(np.random.uniform(0.08, 0.14))
    elif loan_type == LoanType.EDUCATION:
        balance = float(np.random.uniform(50_000, 2_000_000))
        rate = float(np.random.uniform(0.06, 0.12))
    else:  # PERSONAL
        balance = float(np.random.uniform(20_000, 500_000))
        rate = float(np.random.uniform(0.11, 0.24))
    return Loan(loan_type=loan_type, balance=round(balance, 2), interest_rate=round(rate, 4))


def _goal_amount_and_liquidity_bump(goal_type: GoalType, emergency_fund_target: float) -> tuple[float, float]:
    """Target amount for one goal, and how much it should raise liquidity_requirements.

    Short-term purchases, home purchases, and emergency-fund goals raise near-term
    liquidity needs the most; retirement goals raise it least (it mainly lengthens
    investment horizon, which is handled separately by age).
    """
    if goal_type == GoalType.SHORT_TERM_PURCHASE:
        amt = float(np.random.uniform(20_000, 300_000))
        return amt, amt * float(np.random.uniform(0.5, 1.0))
    if goal_type == GoalType.HOME_PURCHASE:
        amt = float(np.random.uniform(500_000, 5_000_000))
        return amt, amt * float(np.random.uniform(0.1, 0.3))
    if goal_type == GoalType.EMERGENCY_FUND:
        amt = emergency_fund_target
        return amt, amt * float(np.random.uniform(0.8, 1.0))
    if goal_type == GoalType.RETIREMENT:
        amt = float(np.random.uniform(2_000_000, 20_000_000))
        return amt, amt * 0.01
    if goal_type == GoalType.EDUCATION:
        amt = float(np.random.uniform(200_000, 2_000_000))
        return amt, amt * float(np.random.uniform(0.2, 0.5))
    amt = float(np.random.uniform(10_000, 200_000))  # OTHER
    return amt, amt * float(np.random.uniform(0.2, 0.6))


def _edge_case_for_index(index: int, num_users: int, num_edge: int) -> str | None:
    """Reserve the last `num_edge` indices for edge cases, cycling through categories."""
    first_edge_index = num_users - num_edge
    if index < first_edge_index:
        return None
    return EDGE_CASE_CATEGORIES[(index - first_edge_index) % len(EDGE_CASE_CATEGORIES)]


def _num_edge_cases(num_users: int) -> int:
    if num_users <= 0:
        return 0
    return min(num_users, max(len(EDGE_CASE_CATEGORIES), round(num_users * 0.05)))


def _generate_one(index: int, edge_case: str | None) -> User:
    """Sample one internally-consistent user. `edge_case`, when set, biases exactly
    the sampling steps needed to guarantee that category -- it never patches an
    already-built record, so every cross-field invariant still holds by construction.
    """
    user_id = f"U{index + 1:06d}"

    # --- age --------------------------------------------------------------
    age = int(np.clip(np.random.normal(42, 13), 18, 80))
    if edge_case == "long_horizon":
        # A long horizon and old age would be an impossible combination -- bias
        # age young so this edge case stays plausible, not pathological.
        age = int(np.random.uniform(18, 30))

    # --- income -> expenses (correlated by construction: expenses is a ------
    # noisy multiple of income, so the two move together across the dataset) --
    monthly_income = float(np.clip(np.random.lognormal(np.log(45_000), 0.6), 8_000, 400_000))

    expense_ratio = float(np.clip(np.random.normal(0.75, 0.18), 0.35, 1.3))
    if edge_case == "high_expense_ratio":
        expense_ratio = float(np.random.uniform(0.95, 1.2))
    monthly_expenses = round(monthly_income * expense_ratio, 2)

    # --- savings: driven by net cash flow (can be negative), with an --------
    # accumulation-time factor and a small income-independent noise floor -----
    net_cash_flow = monthly_income - monthly_expenses
    savings_months = float(np.random.uniform(0.5, 18))
    savings = max(0.0, net_cash_flow) * savings_months + float(np.random.uniform(0, monthly_income * 0.1))
    if edge_case == "very_low_savings":
        savings = float(np.random.uniform(0, 500))
    savings = round(max(savings, 0.0), 2)

    # --- assets: scales with income and years of working life (age), heavy --
    # multiplicative noise for diversity; always >= savings by construction ---
    age_years_working = max(age - 18, 1)
    expected_nonliquid = monthly_income * 12 * 0.15 * (age_years_working / 10)
    nonliquid_assets = max(expected_nonliquid * float(np.random.lognormal(0, 0.8)), 0.0)
    assets = round(savings + nonliquid_assets, 2)

    # --- investment horizon: bounded by distance to retirement age ----------
    if age < RETIREMENT_AGE:
        base_horizon = RETIREMENT_AGE - age
        horizon = max(1, round(base_horizon * float(np.random.uniform(0.6, 1.3))))
    else:
        horizon = max(1, round(float(np.random.uniform(1, 8))))
    if edge_case == "short_horizon":
        horizon = int(np.random.randint(1, 4))
    elif edge_case == "long_horizon":
        horizon = int(np.random.randint(30, 41))
    investment_horizon_years = int(np.clip(horizon, 1, 45))

    # --- risk tolerance: correlated with horizon and (inversely) age, but ---
    # a random term keeps it from being perfectly determined by either --------
    horizon_score = min(investment_horizon_years / 30, 1.0)
    age_score = 1 - (age - 18) / (80 - 18)
    propensity = 0.5 * horizon_score + 0.3 * age_score + 0.2 * float(np.random.uniform(0, 1))
    if propensity > 0.66:
        risk_tolerance = RiskTolerance.HIGH
    elif propensity > 0.4:
        risk_tolerance = RiskTolerance.MODERATE
    else:
        risk_tolerance = RiskTolerance.LOW

    # --- financial literacy: fully independent, so it never becomes a -------
    # proxy for income -------------------------------------------------------
    financial_literacy = FinancialLiteracy(str(np.random.choice(["low", "medium", "high"], p=[0.3, 0.45, 0.25])))

    # --- loans ---------------------------------------------------------------
    num_loans = int(np.random.choice([0, 1, 2, 3], p=[0.35, 0.35, 0.2, 0.1]))
    if edge_case == "no_loans":
        num_loans = 0
    chosen_types = random.sample(LOAN_POOL, k=min(num_loans, len(LOAN_POOL)))
    loans = [_sample_loan(loan_type, monthly_income) for loan_type in chosen_types]
    if edge_case == "high_debt_to_income":
        if not loans:
            loans = [_sample_loan(LoanType.PERSONAL, monthly_income)]
        scale = float(np.random.uniform(3, 6))
        loans = [Loan(loan_type=l.loan_type, balance=round(l.balance * scale, 2), interest_rate=l.interest_rate) for l in loans]
    total_loan_balance = sum(loan.balance for loan in loans)

    # --- liabilities: loans plus a small unmodeled revolving-debt buffer -----
    extra_liabilities = float(np.random.uniform(0, monthly_income * float(np.random.uniform(0, 2))))
    liabilities = round(total_loan_balance + extra_liabilities, 2)

    # --- emergency fund target: a multiple of monthly expenses ---------------
    target_multiple = int(np.random.choice([1, 3, 6, 9], p=[0.1, 0.45, 0.35, 0.1]))
    emergency_fund_target = round(monthly_expenses * target_multiple, 2)
    if edge_case == "insufficient_emergency_savings":
        savings = round(emergency_fund_target * float(np.random.uniform(0.1, 0.6)), 2)
        assets = round(max(assets, savings), 2)

    # --- financial goals -> liquidity requirements ----------------------------
    num_goals = int(np.random.choice([0, 1, 2, 3], p=[0.1, 0.4, 0.35, 0.15]))
    if edge_case == "no_goals":
        num_goals = 0
    elif edge_case == "multiple_goals":
        num_goals = min(4, len(GOAL_POOL))
    goal_types = random.sample(GOAL_POOL, k=num_goals)
    goals: list[FinancialGoal] = []
    liquidity_requirement = savings * 0.1
    for goal_type in goal_types:
        amount, bump = _goal_amount_and_liquidity_bump(goal_type, emergency_fund_target)
        liquidity_requirement += bump
        goals.append(FinancialGoal(goal_type=goal_type, target_amount=round(amount, 2)))
    if edge_case == "very_high_liquidity_requirement":
        liquidity_requirement += savings * float(np.random.uniform(2, 4)) + monthly_income * 3
    liquidity_requirements = round(liquidity_requirement, 2)

    try:
        return User(
            user_id=user_id,
            age=age,
            monthly_income=round(monthly_income, 2),
            monthly_expenses=monthly_expenses,
            savings=savings,
            assets=assets,
            liabilities=liabilities,
            loans=loans,
            risk_tolerance=risk_tolerance,
            investment_horizon_years=investment_horizon_years,
            emergency_fund_target=emergency_fund_target,
            financial_goals=goals,
            liquidity_requirements=liquidity_requirements,
            financial_literacy=financial_literacy,
        )
    except ValidationError as exc:
        # Fail loudly and name the record -- generation logic bugs must not be
        # silently repaired.
        raise RuntimeError(
            f"Generated record for index {index} (user_id={user_id}, edge_case={edge_case}) "
            f"failed validation:\n{exc}"
        ) from exc


def generate_users(num_users: int, seed: int) -> list[User]:
    """Deterministically generate `num_users` synthetic users for the given seed."""
    if num_users <= 0:
        raise ValueError("num_users must be positive")
    set_seed(seed)
    num_edge = _num_edge_cases(num_users)
    return [
        _generate_one(i, _edge_case_for_index(i, num_users, num_edge))
        for i in range(num_users)
    ]


def build_dataset(users: list[User], num_users: int, seed: int) -> dict:
    """Wrap generated users with metadata. The timestamp is metadata only -- it
    never affects, and is never affected by, the seeded user values above."""
    return {
        "metadata": {
            "dataset_version": DATASET_VERSION,
            "generator_version": GENERATOR_VERSION,
            "schema_version": SCHEMA_VERSION,
            "num_users": num_users,
            "random_seed": seed,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "edge_case_categories": EDGE_CASE_CATEGORIES,
            "num_edge_cases": _num_edge_cases(num_users),
        },
        "users": [user.model_dump(mode="json") for user in users],
    }


def _distribution(values: list[str]) -> dict[str, int]:
    return dict(sorted(Counter(values).items()))


def _horizon_distribution(horizons: np.ndarray) -> dict[str, int]:
    bins = {"short (<=5y)": 0, "medium (6-15y)": 0, "long (>15y)": 0}
    for h in horizons:
        if h <= 5:
            bins["short (<=5y)"] += 1
        elif h <= 15:
            bins["medium (6-15y)"] += 1
        else:
            bins["long (>15y)"] += 1
    return bins


def compute_summary(users: list[User]) -> dict:
    """D1-style descriptive statistics and structural-validation correlations.
    This never modifies `users` -- it only reads them."""
    ages = np.array([u.age for u in users], dtype=float)
    incomes = np.array([u.monthly_income for u in users], dtype=float)
    expenses = np.array([u.monthly_expenses for u in users], dtype=float)
    savings = np.array([u.savings for u in users], dtype=float)
    assets = np.array([u.assets for u in users], dtype=float)
    ef_targets = np.array([u.emergency_fund_target for u in users], dtype=float)
    total_loan_balances = np.array([sum(l.balance for l in u.loans) for u in users], dtype=float)
    horizons = np.array([u.investment_horizon_years for u in users], dtype=float)

    def stats(arr: np.ndarray) -> dict[str, float]:
        return {
            "mean": round(float(np.mean(arr)), 2),
            "median": round(float(np.median(arr)), 2),
            "min": round(float(np.min(arr)), 2),
            "max": round(float(np.max(arr)), 2),
        }

    def corr(a: np.ndarray, b: np.ndarray) -> float:
        return round(float(np.corrcoef(a, b)[0, 1]), 3)

    pct_with_loans = round(100 * sum(1 for u in users if u.loans) / len(users), 2)
    debt_to_income = total_loan_balances / (incomes * 12)
    expense_to_income = expenses / incomes

    return {
        "num_users": len(users),
        "age": stats(ages),
        "monthly_income": stats(incomes),
        "monthly_expenses": stats(expenses),
        "savings": {"mean": round(float(np.mean(savings)), 2), "median": round(float(np.median(savings)), 2)},
        "risk_tolerance_distribution": _distribution([u.risk_tolerance.value for u in users]),
        "financial_literacy_distribution": _distribution([u.financial_literacy.value for u in users]),
        "investment_horizon_distribution": _horizon_distribution(horizons),
        "percent_with_loans": pct_with_loans,
        "average_debt_to_income_ratio": round(float(np.mean(debt_to_income)), 3),
        "average_expense_to_income_ratio": round(float(np.mean(expense_to_income)), 3),
        "correlations_for_validation_only": {
            "note": "Descriptive Pearson correlations confirming the intended structural "
            "relationships exist in the synthetic data -- not a causal claim.",
            "income_vs_expenses": corr(incomes, expenses),
            "income_vs_assets": corr(incomes, assets),
            "age_vs_assets": corr(ages, assets),
            "expenses_vs_emergency_fund_target": corr(expenses, ef_targets),
            "income_vs_savings": corr(incomes, savings),
        },
    }


def print_summary(summary: dict) -> None:
    print(f"\nSynthetic user dataset -- {summary['num_users']} users")
    print("-" * 50)
    for field in ("age", "monthly_income", "monthly_expenses"):
        s = summary[field]
        print(f"{field}: mean={s['mean']} median={s['median']} min={s['min']} max={s['max']}")
    s = summary["savings"]
    print(f"savings: mean={s['mean']} median={s['median']}")
    print(f"risk_tolerance: {summary['risk_tolerance_distribution']}")
    print(f"financial_literacy: {summary['financial_literacy_distribution']}")
    print(f"investment_horizon: {summary['investment_horizon_distribution']}")
    print(f"% with loans: {summary['percent_with_loans']}%")
    print(f"avg debt-to-income ratio: {summary['average_debt_to_income_ratio']}")
    print(f"avg expense-to-income ratio: {summary['average_expense_to_income_ratio']}")
    print("\ncorrelations (validation only, not causal):")
    for key, value in summary["correlations_for_validation_only"].items():
        if key != "note":
            print(f"  {key}: {value}")
    print()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--num-users", type=int, default=NUM_USERS)
    parser.add_argument("--seed", type=int, default=RANDOM_SEED)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--summary-output", type=Path, default=DEFAULT_SUMMARY_PATH)
    args = parser.parse_args(argv)

    users = generate_users(num_users=args.num_users, seed=args.seed)
    dataset = build_dataset(users, num_users=args.num_users, seed=args.seed)
    save_json(dataset, args.output)

    summary = compute_summary(users)
    save_json(summary, args.summary_output)
    print_summary(summary)

    print(f"Wrote {len(users)} users to {args.output}")
    print(f"Wrote dataset summary to {args.summary_output}")


if __name__ == "__main__":
    main()
