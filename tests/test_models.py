"""Round-trip and validation tests for the core data models."""

from src.models.artifacts import AuditArtifact, CommunicationArtifact, EvidenceItem, ToolTraceEntry
from src.models.candidate import Candidate, CandidateEvaluation
from src.models.decision import Decision
from src.models.scenario import Scenario, ScenarioType
from src.models.user import FinancialLiteracy, RiskTolerance, User


def make_user() -> User:
    return User(
        user_id="U000001",
        age=34,
        monthly_income=72000,
        monthly_expenses=32000,
        savings=40000,
        assets=120000,
        liabilities=0,
        risk_tolerance=RiskTolerance.LOW,
        investment_horizon_years=25,
        emergency_fund_target=96000,
        liquidity_requirements=32000,
        financial_literacy=FinancialLiteracy.MEDIUM,
    )


def test_user_round_trip():
    user = make_user()
    restored = User.model_validate_json(user.model_dump_json())
    assert restored == user


def test_scenario_requires_valid_type():
    scenario = Scenario(
        scenario_id="S-0001",
        scenario_type=ScenarioType.DEBT_PRIORITIZATION,
        user_id="U-0001",
        question="Should I pay off debt or invest?",
        required_information=["loan_information", "savings"],
        expected_decision_type=ScenarioType.DEBT_PRIORITIZATION,
    )
    assert scenario.scenario_type is ScenarioType.DEBT_PRIORITIZATION


def test_candidate_evaluation_bounds():
    evaluation = CandidateEvaluation(
        candidate_id="repay_high_interest_debt",
        feasible=True,
        goal_alignment_score=0.8,
        suitability_score=1.0,
        financial_objective_score=0.6,
        liquidity_score=0.4,
        total_score=0.7,
    )
    assert 0 <= evaluation.goal_alignment_score <= 1


def test_decision_abstains_without_candidate():
    decision = Decision(
        decision_id="D-0001",
        scenario_id="S-0001",
        confidence=0.0,
        abstained=True,
        abstention_reason="no candidate satisfies hard constraints",
    )
    assert decision.selected_candidate is None
    assert decision.abstained is True


def test_audit_artifact_round_trip():
    decision = Decision(
        decision_id="D-0002",
        scenario_id="S-0001",
        selected_candidate="repay_high_interest_debt",
        confidence=0.87,
        abstained=False,
        evaluated_candidates=[
            CandidateEvaluation(
                candidate_id="repay_high_interest_debt",
                feasible=True,
                goal_alignment_score=0.9,
                suitability_score=1.0,
                financial_objective_score=0.75,
                liquidity_score=0.5,
                total_score=0.81,
            )
        ],
    )
    artifact = AuditArtifact(
        retrieved_evidence=[EvidenceItem(source_id="KB-0417", text="pay high-APR debt first", relevance_score=0.92)],
        tool_traces=[ToolTraceEntry(tool_name="loan_amortization", tool_version="1.0.0", inputs={"apr": 0.22}, outputs={"total_interest": 1200})],
        rejected_candidates=["invest_surplus"],
        assumptions=["no change in income during the horizon"],
        final_decision=decision,
        configuration="full_copilot",
    )
    restored = AuditArtifact.model_validate_json(artifact.model_dump_json())
    assert restored.final_decision.selected_candidate == "repay_high_interest_debt"
    assert restored.configuration == "full_copilot"


def test_communication_artifact_is_independent_schema():
    comm = CommunicationArtifact(
        recommendation="Pay off the high-interest credit card balance first.",
        explanation="This clears the 22% APR debt before any discretionary investing.",
        citations=["KB-0417"],
        constraint_claims=["revolving debt above 15% APR is unsuitable for parallel investing"],
    )
    assert comm.citations == ["KB-0417"]
