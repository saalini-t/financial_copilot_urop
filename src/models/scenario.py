"""Household financial decision scenarios."""

from enum import Enum

from pydantic import BaseModel, Field


class ScenarioType(str, Enum):
    BUDGETING = "BUDGETING"
    DEBT_PRIORITIZATION = "DEBT_PRIORITIZATION"
    EMERGENCY_FUND = "EMERGENCY_FUND"
    INVESTMENT_ALLOCATION = "INVESTMENT_ALLOCATION"
    RETIREMENT = "RETIREMENT"


class Scenario(BaseModel):
    scenario_id: str
    scenario_type: ScenarioType
    user_id: str
    question: str
    relevant_user_attributes: dict = Field(
        default_factory=dict,
        description="Snapshot of the referenced user's own field values relevant to this "
        "question -- always copied from the User record, never fabricated",
    )
    required_information: list[str] = Field(
        default_factory=list,
        description="Profile/evidence fields the decision cannot be made without",
    )
    expected_decision_type: ScenarioType
