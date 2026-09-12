"""Tests for the Phase 6A frozen experimental interface and configuration contracts.

None of these tests exercise real reasoning -- src/agents/*.py are placeholder
stubs (src/agents/_stub.py). The point of this suite is to verify the CONTRACT:
same input schema, same output schema, preserved identifiers, no mutation, and
the structural fairness guarantee that baseline/rag cannot receive a profile.
"""

import copy
import inspect
from pathlib import Path

import pytest

from src.agents import baseline, full_copilot, personalized, rag
from src.config import ExperimentConfig, load_config
from src.models.experiment import (
    ConfigurationName,
    ExecutionMetadata,
    ExperimentInput,
    build_experiment_input,
    make_experiment_id,
)
from src.models.response import AbstentionReason, Confidence, ExperimentOutput
from src.models.scenario import Scenario, ScenarioType
from src.models.user import FinancialLiteracy, RiskTolerance, User

CONFIGS_DIR = Path(__file__).resolve().parent.parent / "configs"
LADDER_FILES = ["baseline.yaml", "rag.yaml", "personalized.yaml", "full_copilot.yaml"]

NO_PROFILE_AGENTS = {"baseline": baseline, "rag": rag}
PROFILE_AGENTS = {"personalized": personalized, "full_copilot": full_copilot}


@pytest.fixture
def scenario() -> Scenario:
    return Scenario(
        scenario_id="S000001",
        scenario_type=ScenarioType.BUDGETING,
        user_id="U000001",
        question="Can I increase my monthly savings without creating a cash-flow problem?",
        relevant_user_attributes={"monthly_income": 50000.0, "monthly_expenses": 30000.0, "savings": 10000.0},
        required_information=["monthly_income", "monthly_expenses", "savings"],
        expected_decision_type=ScenarioType.BUDGETING,
    )


@pytest.fixture
def user() -> User:
    return User(
        user_id="U000001",
        age=30,
        monthly_income=50000,
        monthly_expenses=30000,
        savings=10000,
        assets=10000,
        liabilities=0,
        risk_tolerance=RiskTolerance.MODERATE,
        investment_horizon_years=10,
        emergency_fund_target=90000,
        liquidity_requirements=30000,
        financial_literacy=FinancialLiteracy.MEDIUM,
    )


def _execution_metadata(configuration: ConfigurationName) -> ExecutionMetadata:
    return ExecutionMetadata(
        configuration=configuration,
        model_identifier="mock-llm",
        prompt_version="test-v1",
        dataset_version="v1.0",
        scenario_dataset_version="v1.0",
        ground_truth_version="1.0.0",
        experiment_seed=42,
    )


def _run_all_configurations(experiment_input: ExperimentInput, user: User) -> dict[str, ExperimentOutput]:
    outputs = {}
    outputs["baseline"] = baseline.run(experiment_input, run_id="r1", execution_metadata=_execution_metadata(ConfigurationName.BASELINE))
    outputs["rag"] = rag.run(experiment_input, run_id="r1", execution_metadata=_execution_metadata(ConfigurationName.RAG))
    outputs["personalized"] = personalized.run(
        experiment_input, profile=user, run_id="r1", execution_metadata=_execution_metadata(ConfigurationName.PERSONALIZED)
    )
    outputs["full_copilot"] = full_copilot.run(
        experiment_input, profile=user, run_id="r1", execution_metadata=_execution_metadata(ConfigurationName.FULL_COPILOT)
    )
    return outputs


# 1. all configurations satisfy the same input contract ---------------------------

def test_build_experiment_input_is_identical_regardless_of_target_configuration(scenario):
    """The same Scenario always produces the same ExperimentInput -- there is no
    per-configuration variant."""
    a = build_experiment_input(scenario)
    b = build_experiment_input(scenario)
    assert a == b
    assert isinstance(a, ExperimentInput)


def test_every_agent_run_accepts_the_common_experiment_input(scenario, user):
    experiment_input = build_experiment_input(scenario)
    outputs = _run_all_configurations(experiment_input, user)
    assert len(outputs) == 4


# 2. all configurations satisfy the same output contract ---------------------------

def test_every_agent_returns_a_valid_experiment_output(scenario, user):
    experiment_input = build_experiment_input(scenario)
    for name, output in _run_all_configurations(experiment_input, user).items():
        assert isinstance(output, ExperimentOutput), name
        # round-trips through the schema cleanly
        assert ExperimentOutput.model_validate_json(output.model_dump_json()) == output


# 3. scenario/user IDs are preserved ------------------------------------------------

def test_scenario_and_user_ids_are_preserved_across_every_configuration(scenario, user):
    experiment_input = build_experiment_input(scenario)
    for name, output in _run_all_configurations(experiment_input, user).items():
        assert output.scenario_id == scenario.scenario_id, name
        assert output.user_id == scenario.user_id, name


# 4. no configuration mutates source datasets ---------------------------------------

def test_no_agent_mutates_the_experiment_input_or_profile(scenario, user):
    experiment_input = build_experiment_input(scenario)
    input_before = experiment_input.model_copy(deep=True)
    user_before = user.model_copy(deep=True)

    _run_all_configurations(experiment_input, user)

    assert experiment_input == input_before
    assert user == user_before


def test_build_experiment_input_does_not_share_mutable_state_with_the_scenario(scenario):
    experiment_input = build_experiment_input(scenario)
    experiment_input.relevant_user_attributes["injected"] = "should not leak back"
    assert "injected" not in scenario.relevant_user_attributes


# 5. baseline cannot access hidden user profile fields -------------------------------

def test_baseline_and_rag_have_no_profile_parameter_in_their_signature():
    for name, module in NO_PROFILE_AGENTS.items():
        params = inspect.signature(module.run, eval_str=True).parameters
        assert "profile" not in params, f"{name}.run() must not accept a profile parameter"
        assert not any(p.annotation is User for p in params.values()), name


def test_baseline_rejects_a_profile_argument_if_one_is_attempted(scenario, user):
    experiment_input = build_experiment_input(scenario)
    with pytest.raises(TypeError):
        baseline.run(  # type: ignore[call-arg]
            experiment_input, profile=user, run_id="r1", execution_metadata=_execution_metadata(ConfigurationName.BASELINE)
        )


# 6. personalized/full configurations can access explicitly permitted profile fields --

def test_personalized_and_full_copilot_require_an_explicit_profile_parameter():
    for name, module in PROFILE_AGENTS.items():
        params = inspect.signature(module.run, eval_str=True).parameters
        assert "profile" in params, f"{name}.run() must accept a profile parameter"
        assert params["profile"].annotation is User, name


def test_personalized_and_full_copilot_actually_receive_the_given_profile(scenario, user):
    experiment_input = build_experiment_input(scenario)
    for name, module in PROFILE_AGENTS.items():
        output = module.run(
            experiment_input, profile=user, run_id="r1",
            execution_metadata=_execution_metadata(ConfigurationName[name.upper()]),
        )
        provenance = output.artifacts[0].provenance
        assert provenance.get("profile_user_id") == user.user_id, name


# 7. artifacts have valid schemas ----------------------------------------------------

def test_every_artifact_has_the_required_fields(scenario, user):
    experiment_input = build_experiment_input(scenario)
    for name, output in _run_all_configurations(experiment_input, user).items():
        assert output.artifacts, name
        for artifact in output.artifacts:
            assert artifact.artifact_type
            assert artifact.source
            assert artifact.execution_id


def test_artifacts_contain_no_chain_of_thought_marker(scenario, user):
    """A cheap but real guard: nothing in the stub output claims to carry
    reasoning -- the explanation is explicit that no reasoning was performed."""
    experiment_input = build_experiment_input(scenario)
    for name, output in _run_all_configurations(experiment_input, user).items():
        assert "chain" not in output.explanation.lower() or "no reasoning" in output.explanation.lower()


# 8. abstention reasons are valid ----------------------------------------------------

def test_abstention_reason_is_always_a_valid_enum_member(scenario, user):
    experiment_input = build_experiment_input(scenario)
    for name, output in _run_all_configurations(experiment_input, user).items():
        if output.abstention:
            assert output.abstention_reason in set(AbstentionReason), name
        else:
            assert output.abstention_reason is None, name


def test_experiment_output_rejects_inconsistent_abstention_state(scenario, user):
    experiment_input = build_experiment_input(scenario)
    valid = full_copilot.run(
        experiment_input, profile=user, run_id="r1", execution_metadata=_execution_metadata(ConfigurationName.FULL_COPILOT)
    )
    payload = valid.model_dump()
    payload["abstention"] = False  # but abstention_reason is still set -> must fail validation
    with pytest.raises(Exception):
        ExperimentOutput.model_validate(payload)


# 9. confidence schema is valid --------------------------------------------------------

def test_confidence_available_false_has_no_value(scenario, user):
    experiment_input = build_experiment_input(scenario)
    for name, output in _run_all_configurations(experiment_input, user).items():
        confidence = output.confidence
        if not confidence.available:
            assert confidence.value is None, name
            assert confidence.reason, name
        else:
            assert confidence.value is not None, name


def test_confidence_model_rejects_a_value_without_availability():
    with pytest.raises(Exception):
        Confidence(available=False, value=0.9, method="invented")


def test_confidence_model_rejects_availability_without_a_value():
    with pytest.raises(Exception):
        Confidence(available=True, value=None, method="deterministic_margin")


# 10. configuration metadata is complete -------------------------------------------------

def test_execution_metadata_configuration_matches_the_agent(scenario, user):
    experiment_input = build_experiment_input(scenario)
    outputs = _run_all_configurations(experiment_input, user)
    assert outputs["baseline"].execution_metadata.configuration == ConfigurationName.BASELINE
    assert outputs["rag"].execution_metadata.configuration == ConfigurationName.RAG
    assert outputs["personalized"].execution_metadata.configuration == ConfigurationName.PERSONALIZED
    assert outputs["full_copilot"].execution_metadata.configuration == ConfigurationName.FULL_COPILOT


def test_execution_metadata_never_carries_a_key_like_field():
    forbidden_substrings = ("api_key", "apikey", "secret", "token", "password")
    fields = set(ExecutionMetadata.model_fields.keys())
    for field in fields:
        for bad in forbidden_substrings:
            assert bad not in field.lower(), field


# Deterministic experiment IDs (requirement 13) --------------------------------------------

def test_experiment_id_is_deterministic_given_the_same_inputs():
    a = make_experiment_id(ConfigurationName.BASELINE, "S000001", "run-1")
    b = make_experiment_id(ConfigurationName.BASELINE, "S000001", "run-1")
    assert a == b


def test_experiment_id_differs_when_any_component_differs():
    base = make_experiment_id(ConfigurationName.BASELINE, "S000001", "run-1")
    assert make_experiment_id(ConfigurationName.RAG, "S000001", "run-1") != base
    assert make_experiment_id(ConfigurationName.BASELINE, "S000002", "run-1") != base
    assert make_experiment_id(ConfigurationName.BASELINE, "S000001", "run-2") != base


def test_experiment_ids_are_consistent_across_configurations_for_the_same_scenario(scenario, user):
    experiment_input = build_experiment_input(scenario)
    outputs = _run_all_configurations(experiment_input, user)
    for name, output in outputs.items():
        assert output.experiment_id == make_experiment_id(
            ConfigurationName(name), scenario.scenario_id, "r1"
        )


# 11. configuration YAML files are valid ------------------------------------------------

@pytest.mark.parametrize("filename", LADDER_FILES)
def test_each_configuration_yaml_is_valid(filename):
    config = load_config(CONFIGS_DIR / filename)
    assert isinstance(config, ExperimentConfig)
    assert config.prompt_version != ""
    assert isinstance(config.retrieval, dict)
    assert isinstance(config.tool_config, dict)


def test_configuration_yaml_does_not_hard_code_secrets():
    forbidden = ("api_key", "apikey", "secret", "password", "token")
    for filename in LADDER_FILES:
        text = (CONFIGS_DIR / filename).read_text(encoding="utf-8").lower()
        for bad in forbidden:
            assert bad not in text, f"{filename} appears to contain a secret-like key: {bad}"


def test_baseline_and_rag_yaml_disable_retrieval_or_tools_as_documented():
    baseline_cfg = load_config(CONFIGS_DIR / "baseline.yaml")
    assert baseline_cfg.retrieval.get("enabled") is False
    assert baseline_cfg.tool_config.get("enabled") is False

    rag_cfg = load_config(CONFIGS_DIR / "rag.yaml")
    assert rag_cfg.retrieval.get("enabled") is True
    assert rag_cfg.tool_config.get("enabled") is False


def test_full_copilot_yaml_enables_every_module():
    full_cfg = load_config(CONFIGS_DIR / "full_copilot.yaml")
    assert all(full_cfg.modules.model_dump().values())
    assert full_cfg.retrieval.get("enabled") is True
    assert full_cfg.tool_config.get("enabled") is True


# Fairness: identical scenario text across all four configurations -------------------------

def test_all_four_configurations_receive_the_exact_same_question_text(scenario, user):
    experiment_input = build_experiment_input(scenario)
    for name, module in {**NO_PROFILE_AGENTS, **PROFILE_AGENTS}.items():
        artifact_input = None
        if name in NO_PROFILE_AGENTS:
            output = module.run(experiment_input, run_id="r1", execution_metadata=_execution_metadata(ConfigurationName(name)))
        else:
            output = module.run(
                experiment_input, profile=user, run_id="r1", execution_metadata=_execution_metadata(ConfigurationName(name))
            )
        artifact_input = output.artifacts[0].input
        assert artifact_input.get("question") == scenario.question, name
