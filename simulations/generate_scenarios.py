"""Generate household financial decision scenarios for the synthetic user population.

Phase 3 scope only: this script produces `Scenario` records referencing existing
`User` records (see simulations/generate_users.py) -- no ground truth, candidate
evaluation, or recommendation logic. Questions come from deterministic string
templates, never an LLM call, and every value a template inserts is copied
directly from the referenced user's own profile -- nothing is invented.

Usage:
    python simulations/generate_scenarios.py
    python simulations/generate_scenarios.py --num-scenarios-per-user 5 --seed 42

Requires data/synthetic/users.json to already exist (run generate_users.py first).
Running the same command against the same users.json twice produces byte-identical
`scenarios` records (the `generated_at` metadata timestamp is the only thing that
changes between runs).
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
    sys.path.insert(0, str(REPO_ROOT))

from src.models.scenario import Scenario, ScenarioType
from src.models.user import GoalType, User
from src.utils import load_json, save_json

NUM_SCENARIOS_PER_USER = 5
RANDOM_SEED = 42

DATASET_VERSION = "v1.0"
GENERATOR_VERSION = "v1.0"
SCHEMA_VERSION = "1.0.0"

DEFAULT_USERS_INPUT_PATH = REPO_ROOT / "data" / "synthetic" / "users.json"
DEFAULT_OUTPUT_PATH = REPO_ROOT / "data" / "synthetic" / "scenarios.json"

SCENARIO_TYPE_ORDER = list(ScenarioType)  # BUDGETING, DEBT_PRIORITIZATION, EMERGENCY_FUND, ...


def _money(value: float) -> str:
    return f"₹{value:,.0f}"


# Each template builder returns (question, relevant_field_names) pairs -- a random
# one is chosen per (user, scenario_type). Every number quoted in a question is
# read straight from `user`; nothing here is a made-up figure.


def _budgeting_templates(user: User, rng: random.Random) -> tuple[str, list[str]]:
    net_cash_flow = max(user.monthly_income - user.monthly_expenses, 0)
    options: list[tuple[str, list[str]]] = [
        (
            f"My monthly income is {_money(user.monthly_income)} and my expenses are about "
            f"{_money(user.monthly_expenses)}. Can I increase my monthly savings without "
            "creating a cash-flow problem?",
            ["monthly_income", "monthly_expenses", "savings"],
        ),
        (
            "Can I increase my monthly savings without creating a cash-flow problem?",
            ["monthly_income", "monthly_expenses", "savings"],
        ),
        (
            f"I currently have about {_money(net_cash_flow)} left over each month. Where could I "
            "realistically cut back to save more?",
            ["monthly_income", "monthly_expenses"],
        ),
        (
            "Is my current spending sustainable given my income?",
            ["monthly_income", "monthly_expenses"],
        ),
    ]
    return rng.choice(options)


def _debt_templates(user: User, rng: random.Random) -> tuple[str, list[str]]:
    if user.loans:
        costliest = max(user.loans, key=lambda loan: loan.interest_rate)
        total_balance = sum(loan.balance for loan in user.loans)
        max_rate = max(loan.interest_rate for loan in user.loans)
        options: list[tuple[str, list[str]]] = [
            (
                f"I have {_money(user.savings)} available. Should I repay my {costliest.loan_type.value} "
                "loan or invest it?",
                ["savings", "loans"],
            ),
            (
                f"I have loans totaling {_money(total_balance)} with rates up to {max_rate:.1%}. "
                "Should I focus on paying these off before investing?",
                ["loans", "monthly_income"],
            ),
            (
                "Should I prioritize paying down debt or investing my surplus?",
                ["loans", "savings", "monthly_income"],
            ),
        ]
    else:
        # Deliberately under-specified: the question implies debt that this user's
        # profile does not actually contain -- a natural abstention/suitability case.
        options = [
            (
                "Should I prioritize paying down debt or investing my surplus?",
                ["loans", "savings"],
            ),
            (
                "I want to avoid taking on debt. Is that the right call for my situation?",
                ["loans", "monthly_income", "savings"],
            ),
        ]
    return rng.choice(options)


def _emergency_fund_templates(user: User, rng: random.Random) -> tuple[str, list[str]]:
    options: list[tuple[str, list[str]]] = [
        (
            "How much should I keep as an emergency fund?",
            ["monthly_expenses", "savings"],
        ),
        (
            f"My monthly expenses are about {_money(user.monthly_expenses)}. How much should I keep "
            "as an emergency fund?",
            ["monthly_expenses"],
        ),
        (
            f"I currently have {_money(user.savings)} in savings. Is that enough for emergencies?",
            ["savings", "monthly_expenses", "emergency_fund_target"],
        ),
    ]
    return rng.choice(options)


def _investment_templates(user: User, rng: random.Random) -> tuple[str, list[str]]:
    options: list[tuple[str, list[str]]] = [
        (
            "How should I allocate my available savings given my risk tolerance?",
            ["savings", "risk_tolerance", "investment_horizon_years"],
        ),
        (
            f"I have {_money(user.savings)} to invest over the next {user.investment_horizon_years} "
            f"years. What allocation makes sense given my {user.risk_tolerance.value} risk tolerance?",
            ["savings", "investment_horizon_years", "risk_tolerance"],
        ),
        (
            "I want to grow my money. What should I invest in?",
            ["savings", "risk_tolerance", "investment_horizon_years"],
        ),
    ]
    return rng.choice(options)


def _retirement_templates(user: User, rng: random.Random) -> tuple[str, list[str]]:
    retirement_goal = next((g for g in user.financial_goals if g.goal_type == GoalType.RETIREMENT), None)
    options: list[tuple[str, list[str]]] = [
        (
            "Am I on track for my retirement goal?",
            ["age", "investment_horizon_years", "monthly_income", "financial_goals"],
        ),
        (
            f"I am {user.age} years old with a {user.investment_horizon_years}-year investment "
            "horizon. Am I saving enough for retirement?",
            ["age", "investment_horizon_years", "monthly_income"],
        ),
    ]
    if retirement_goal is not None:
        # Only cite a retirement target when the user's profile actually has one.
        options.append((
            f"I want to have {_money(retirement_goal.target_amount)} saved by retirement. "
            "Am I on track?",
            ["age", "investment_horizon_years", "financial_goals", "monthly_income"],
        ))
    else:
        options.append((
            "How much do I need to save monthly to retire comfortably?",
            ["age", "investment_horizon_years", "monthly_income", "financial_goals"],
        ))
    return rng.choice(options)


TEMPLATE_BUILDERS = {
    ScenarioType.BUDGETING: _budgeting_templates,
    ScenarioType.DEBT_PRIORITIZATION: _debt_templates,
    ScenarioType.EMERGENCY_FUND: _emergency_fund_templates,
    ScenarioType.INVESTMENT_ALLOCATION: _investment_templates,
    ScenarioType.RETIREMENT: _retirement_templates,
}


def _snapshot(user: User, fields: list[str]) -> dict:
    """Copy the named fields straight out of the user's own record. This is the
    only source of values `relevant_user_attributes` is ever built from."""
    dumped = user.model_dump(mode="json")
    return {field: dumped[field] for field in fields if field in dumped}


def load_users(path: str | Path = DEFAULT_USERS_INPUT_PATH) -> list[User]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"{path} does not exist -- run `python simulations/generate_users.py` first."
        )
    raw = load_json(path)
    records = raw.get("users") if isinstance(raw, dict) else raw
    if not records:
        raise ValueError(
            f"{path} contains no users -- run `python simulations/generate_users.py` first."
        )
    return [User.model_validate(record) for record in records]


def generate_scenarios(users: list[User], num_scenarios_per_user: int, seed: int) -> list[Scenario]:
    """Deterministically generate `num_scenarios_per_user` scenarios for each user.

    Uses a dedicated `random.Random(seed)` instance rather than the project's
    global `set_seed` utility -- scenario selection is the only randomness here
    (no numpy sampling), and an isolated instance keeps this function's output
    independent of whatever else has touched the global RNG state in-process,
    which matters for calling it repeatedly within one test session.
    """
    if num_scenarios_per_user <= 0:
        raise ValueError("num_scenarios_per_user must be positive")

    rng = random.Random(seed)
    scenarios: list[Scenario] = []
    counter = 1
    for user in users:
        for i in range(num_scenarios_per_user):
            scenario_type = SCENARIO_TYPE_ORDER[i % len(SCENARIO_TYPE_ORDER)]
            question, fields = TEMPLATE_BUILDERS[scenario_type](user, rng)
            scenarios.append(
                Scenario(
                    scenario_id=f"S{counter:06d}",
                    scenario_type=scenario_type,
                    user_id=user.user_id,
                    question=question,
                    relevant_user_attributes=_snapshot(user, fields),
                    required_information=fields,
                    expected_decision_type=scenario_type,
                )
            )
            counter += 1
    return scenarios


def build_dataset(
    scenarios: list[Scenario],
    *,
    num_users: int,
    num_scenarios_per_user: int,
    seed: int,
    source_users_path: Path,
) -> dict:
    """Wrap generated scenarios with metadata. The timestamp is metadata only --
    it never affects, and is never affected by, the seeded scenario values above."""
    source_meta = {}
    users_raw = load_json(source_users_path)
    if isinstance(users_raw, dict):
        source_meta = users_raw.get("metadata", {})

    distribution = Counter(s.scenario_type.value for s in scenarios)
    return {
        "metadata": {
            "dataset_version": DATASET_VERSION,
            "generator_version": GENERATOR_VERSION,
            "schema_version": SCHEMA_VERSION,
            "random_seed": seed,
            "num_users": num_users,
            "num_scenarios_per_user": num_scenarios_per_user,
            "num_scenarios": len(scenarios),
            "scenario_distribution": {t.value: distribution.get(t.value, 0) for t in ScenarioType},
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_user_dataset_version": source_meta.get("dataset_version"),
            "source_user_dataset_seed": source_meta.get("random_seed"),
        },
        "scenarios": [scenario.model_dump(mode="json") for scenario in scenarios],
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--num-scenarios-per-user", type=int, default=NUM_SCENARIOS_PER_USER)
    parser.add_argument("--seed", type=int, default=RANDOM_SEED)
    parser.add_argument("--users-input", type=Path, default=DEFAULT_USERS_INPUT_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    args = parser.parse_args(argv)

    users = load_users(args.users_input)
    scenarios = generate_scenarios(users, num_scenarios_per_user=args.num_scenarios_per_user, seed=args.seed)
    dataset = build_dataset(
        scenarios,
        num_users=len(users),
        num_scenarios_per_user=args.num_scenarios_per_user,
        seed=args.seed,
        source_users_path=args.users_input,
    )
    save_json(dataset, args.output)

    print(f"\nGenerated {len(scenarios)} scenarios for {len(users)} users")
    print(f"scenario_distribution: {dataset['metadata']['scenario_distribution']}")
    print(f"Wrote {len(scenarios)} scenarios to {args.output}")


if __name__ == "__main__":
    main()
