"""Generate the five dataset-visualization figures for the research report,
from the existing synthetic user dataset only.

Reads data/synthetic/users.json (read-only -- never modified, regenerated, or
overwritten) and writes five PNG figures to visualizations/figures/. Every
plotted value comes directly from the dataset; nothing is invented or
hardcoded.

Usage:
    python visualizations/generate_user_plots.py
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
USERS_PATH = REPO_ROOT / "data" / "synthetic" / "users.json"
FIGURES_DIR = SCRIPT_DIR / "figures"

EXPECTED_USER_COUNT = 1000

plt.rcParams.update(
    {
        "font.size": 12,
        "axes.titlesize": 14,
        "axes.labelsize": 12,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
    }
)


def load_users(path: Path = USERS_PATH) -> list[dict]:
    """Read-only load. Handles both {"users": [...]} and a bare [...] list."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    return raw["users"] if isinstance(raw, dict) else raw


def _horizon_bucket(years: float) -> str:
    if years <= 5:
        return "Short (<=5y)"
    if years <= 15:
        return "Medium (6-15y)"
    return "Long (>15y)"


def plot_income_vs_expenses(users: list[dict]) -> Path:
    income = [u["monthly_income"] for u in users]
    expenses = [u["monthly_expenses"] for u in users]

    fig, ax = plt.subplots(figsize=(7, 5.5))
    ax.scatter(income, expenses, alpha=0.5, s=18)
    ax.set_title("Monthly Income vs. Monthly Expenses")
    ax.set_xlabel("Monthly Income (INR)")
    ax.set_ylabel("Monthly Expenses (INR)")
    ax.grid(True, alpha=0.3)

    out_path = FIGURES_DIR / "income_expenses_scatter.png"
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return out_path


def plot_age_vs_assets(users: list[dict]) -> Path:
    age = [u["age"] for u in users]
    assets = [u["assets"] for u in users]

    fig, ax = plt.subplots(figsize=(7, 5.5))
    ax.scatter(age, assets, alpha=0.5, s=18)
    ax.set_title("Age vs. Assets")
    ax.set_xlabel("Age (years)")
    ax.set_ylabel("Assets (INR)")
    ax.grid(True, alpha=0.3)

    out_path = FIGURES_DIR / "age_assets_scatter.png"
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return out_path


def plot_risk_tolerance_distribution(users: list[dict]) -> tuple[Path, dict[str, int]]:
    counts = Counter(u["risk_tolerance"] for u in users)
    order = ["low", "moderate", "high"]
    labels = ["Low", "Moderate", "High"]
    values = [counts.get(key, 0) for key in order]

    fig, ax = plt.subplots(figsize=(6, 4.5))
    ax.bar(labels, values)
    ax.set_title("Risk Tolerance Distribution")
    ax.set_xlabel("Risk Tolerance")
    ax.set_ylabel("Number of Users")

    out_path = FIGURES_DIR / "risk_tolerance_distribution.png"
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return out_path, dict(zip(labels, values))


def plot_investment_horizon_distribution(users: list[dict]) -> tuple[Path, dict[str, int]]:
    buckets = [_horizon_bucket(u["investment_horizon_years"]) for u in users]
    counts = Counter(buckets)
    order = ["Short (<=5y)", "Medium (6-15y)", "Long (>15y)"]
    values = [counts.get(key, 0) for key in order]

    fig, ax = plt.subplots(figsize=(6, 4.5))
    ax.bar(order, values)
    ax.set_title("Investment Horizon Distribution")
    ax.set_xlabel("Investment Horizon")
    ax.set_ylabel("Number of Users")

    out_path = FIGURES_DIR / "investment_horizon_distribution.png"
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return out_path, dict(zip(order, values))


def plot_financial_literacy_distribution(users: list[dict]) -> tuple[Path, dict[str, int]]:
    counts = Counter(u["financial_literacy"] for u in users)
    order = ["low", "medium", "high"]
    labels = ["Low", "Medium", "High"]
    values = [counts.get(key, 0) for key in order]

    fig, ax = plt.subplots(figsize=(6, 4.5))
    ax.bar(labels, values)
    ax.set_title("Financial Literacy Distribution")
    ax.set_xlabel("Financial Literacy")
    ax.set_ylabel("Number of Users")

    out_path = FIGURES_DIR / "financial_literacy_distribution.png"
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return out_path, dict(zip(labels, values))


def main() -> None:
    users = load_users()

    print(f"Loaded {len(users)} users from {USERS_PATH}")
    if len(users) != EXPECTED_USER_COUNT:
        print(f"WARNING: expected exactly {EXPECTED_USER_COUNT} users, found {len(users)}")
    else:
        print(f"Verified: exactly {EXPECTED_USER_COUNT} users are being plotted.")

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    income_expenses_path = plot_income_vs_expenses(users)
    age_assets_path = plot_age_vs_assets(users)
    risk_path, risk_counts = plot_risk_tolerance_distribution(users)
    horizon_path, horizon_counts = plot_investment_horizon_distribution(users)
    literacy_path, literacy_counts = plot_financial_literacy_distribution(users)

    print("\nFigures generated:")
    print(f"  1. {income_expenses_path.relative_to(REPO_ROOT)}")
    print(f"  2. {age_assets_path.relative_to(REPO_ROOT)}")
    print(f"  3. {risk_path.relative_to(REPO_ROOT)}")
    print(f"  4. {horizon_path.relative_to(REPO_ROOT)}")
    print(f"  5. {literacy_path.relative_to(REPO_ROOT)}")

    print("\nCategory counts:")
    print(f"  Risk tolerance: {risk_counts}")
    print(f"  Investment horizon: {horizon_counts}")
    print(f"  Financial literacy: {literacy_counts}")


if __name__ == "__main__":
    main()
