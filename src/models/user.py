"""Synthetic household financial profile.

Schema frozen for Phase 3 (synthetic dataset generation, see
simulations/generate_users.py and docs/data_dictionary.md). All values are
fully synthetic -- no real names, contact details, or account numbers.
"""

from enum import Enum

from pydantic import BaseModel, Field, computed_field, model_validator


class RiskTolerance(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


class FinancialLiteracy(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class LoanType(str, Enum):
    """Synthetic loan categories -- not modeled on any real lender's product."""

    PERSONAL = "personal"
    EDUCATION = "education"
    VEHICLE = "vehicle"
    HOME = "home"


class Loan(BaseModel):
    loan_type: LoanType
    balance: float = Field(ge=0, description="Outstanding balance, INR")
    interest_rate: float = Field(ge=0, description="Annual rate, e.g. 0.11 for 11%")


class GoalType(str, Enum):
    SHORT_TERM_PURCHASE = "short_term_purchase"
    HOME_PURCHASE = "home_purchase"
    EMERGENCY_FUND = "emergency_fund"
    RETIREMENT = "retirement"
    EDUCATION = "education"
    OTHER = "other"


class FinancialGoal(BaseModel):
    goal_type: GoalType
    target_amount: float = Field(ge=0, description="INR")


class User(BaseModel):
    """A synthetic financial user. Never populated from real individuals."""

    user_id: str = Field(pattern=r"^U\d{6}$", description="e.g. U000001")
    age: int = Field(ge=18, le=80)
    monthly_income: float = Field(gt=0, description="INR/month")
    monthly_expenses: float = Field(ge=0, description="INR/month")
    savings: float = Field(ge=0, description="Liquid savings balance, INR")
    assets: float = Field(ge=0, description="Total assets (includes savings), INR")
    liabilities: float = Field(ge=0, description="Total liabilities (includes loan balances), INR")
    loans: list[Loan] = Field(default_factory=list)
    risk_tolerance: RiskTolerance
    investment_horizon_years: int = Field(gt=0)
    emergency_fund_target: float = Field(ge=0, description="Target emergency fund balance, INR")
    financial_goals: list[FinancialGoal] = Field(default_factory=list)
    liquidity_requirements: float = Field(ge=0, description="Minimum liquid reserve the user requires, INR")
    financial_literacy: FinancialLiteracy

    @computed_field  # type: ignore[prop-decorator]
    @property
    def loan_interest_rates(self) -> list[float]:
        """Derived from `loans` -- kept as its own field per the frozen schema, never stored separately."""
        return [loan.interest_rate for loan in self.loans]

    @model_validator(mode="after")
    def _check_cross_field_consistency(self) -> "User":
        if self.assets < self.savings:
            raise ValueError(
                f"{self.user_id}: assets ({self.assets}) must be >= savings ({self.savings})"
            )
        total_loan_balance = sum(loan.balance for loan in self.loans)
        if self.liabilities < total_loan_balance:
            raise ValueError(
                f"{self.user_id}: liabilities ({self.liabilities}) must be >= "
                f"total loan balance ({total_loan_balance})"
            )
        return self
