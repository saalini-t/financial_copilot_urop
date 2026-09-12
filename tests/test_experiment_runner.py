"""Tests for the Phase 6B experiment execution/orchestration layer.

Manifest-integrity tests (scenario count/uniqueness) run against the real,
frozen data/synthetic/ files. Runner-behavior tests build a small synthetic
population in tmp_path via the existing Phase 3/4 generators, so they stay
fast and isolated from the large real dataset while still exercising the full
load -> build_experiment_input -> dispatch -> validate -> persist pipeline.
"""

from pathlib import Path

import pytest

from experiments.manifest import DEFAULT_GROUND_TRUTH_PATH, DEFAULT_SCENARIOS_PATH, DEFAULT_USERS_PATH, build_manifest
from experiments.run_experiment import (
    load_scenarios,
    load_users,
    persist_result,
    result_path,
    run_scenario,
    run_scenarios,
)
from simulations.generate_scenarios import build_dataset as build_scenarios_dataset
from simulations.generate_scenarios import generate_scenarios
from simulations.generate_users import build_dataset as build_users_dataset
from simulations.generate_users import generate_users
from src.config import load_config
from src.models.experiment import ConfigurationName, build_experiment_input
from src.models.response import ExperimentOutput
from src.utils import load_json, save_json

CONFIGS_DIR = Path(__file__).resolve().parent.parent / "configs"
ALL_CONFIGS = list(ConfigurationName)


# ---------------------------------------------------------------------------
# Manifest tests (against the real, frozen datasets)
# ---------------------------------------------------------------------------

def test_manifest_contains_exactly_5000_scenario_ids():
    manifest = build_manifest()
    assert manifest["scenario_count"] == 5000
    assert len(manifest["scenario_ids"]) == 5000


def test_manifest_scenario_ids_are_unique():
    manifest = build_manifest()
    assert len(set(manifest["scenario_ids"])) == len(manifest["scenario_ids"])


def test_manifest_records_dataset_versions_and_seed():
    manifest = build_manifest()
    for field in (
        "dataset_version",
        "scenario_dataset_version",
        "ground_truth_dataset_version",
        "ground_truth_version",
        "random_seed",
        "user_count",
        "scenario_count",
    ):
        assert manifest[field] is not None, field


def test_manifest_does_not_modify_source_datasets():
    before = {
        p: p.read_text(encoding="utf-8")
        for p in (DEFAULT_USERS_PATH, DEFAULT_SCENARIOS_PATH, DEFAULT_GROUND_TRUTH_PATH)
    }
    build_manifest()
    for path, content in before.items():
        assert path.read_text(encoding="utf-8") == content, path


# ---------------------------------------------------------------------------
# Small in-process fixture population, isolated from the real 5000-scenario dataset
# ---------------------------------------------------------------------------

TEST_NUM_USERS = 12
TEST_SCENARIOS_PER_USER = 5
TEST_SEED = 42


@pytest.fixture
def fixture_paths(tmp_path):
    users = generate_users(num_users=TEST_NUM_USERS, seed=TEST_SEED)
    scenarios = generate_scenarios(users, num_scenarios_per_user=TEST_SCENARIOS_PER_USER, seed=TEST_SEED)

    users_path = tmp_path / "users.json"
    scenarios_path = tmp_path / "scenarios.json"
    save_json(build_users_dataset(users, num_users=TEST_NUM_USERS, seed=TEST_SEED), users_path)
    save_json(
        build_scenarios_dataset(
            scenarios,
            num_users=TEST_NUM_USERS,
            num_scenarios_per_user=TEST_SCENARIOS_PER_USER,
            seed=TEST_SEED,
            source_users_path=users_path,
        ),
        scenarios_path,
    )
    return users_path, scenarios_path


@pytest.fixture
def fixture_manifest(fixture_paths):
    users_path, scenarios_path = fixture_paths
    users_raw = load_json(users_path)
    scenarios_raw = load_json(scenarios_path)
    return {
        "manifest_version": "1.0.0",
        "dataset_version": users_raw["metadata"]["dataset_version"],
        "scenario_dataset_version": scenarios_raw["metadata"]["dataset_version"],
        "ground_truth_version": "1.0.0",
        "random_seed": users_raw["metadata"]["random_seed"],
        "user_count": users_raw["metadata"]["num_users"],
        "scenario_count": scenarios_raw["metadata"]["num_scenarios"],
        "scenario_ids": [s["scenario_id"] for s in scenarios_raw["scenarios"]],
    }


def _run_one(configuration, scenario_id, fixture_paths, fixture_manifest, results_dir, run_id="test-run"):
    users_path, scenarios_path = fixture_paths
    return run_scenarios(
        configuration,
        [scenario_id],
        run_id,
        users_path=users_path,
        scenarios_path=scenarios_path,
        configs_dir=CONFIGS_DIR,
        manifest=fixture_manifest,
        results_dir=results_dir,
    )[0]


# 3. all four configurations use the same scenario ----------------------------------

def test_all_four_configurations_receive_the_same_scenario(fixture_paths, fixture_manifest, tmp_path):
    users_path, scenarios_path = fixture_paths
    scenario_id = fixture_manifest["scenario_ids"][0]
    scenarios = load_scenarios(scenarios_path)
    expected_question = scenarios[scenario_id].question

    results_dir = tmp_path / "results"
    for configuration in ALL_CONFIGS:
        output = _run_one(configuration, scenario_id, fixture_paths, fixture_manifest, results_dir)
        assert output.artifacts[0].input.get("question") == expected_question, configuration


# 4. input construction is identical --------------------------------------------------

def test_build_experiment_input_is_identical_for_every_configuration(fixture_paths, fixture_manifest):
    _, scenarios_path = fixture_paths
    scenario_id = fixture_manifest["scenario_ids"][0]
    scenario = load_scenarios(scenarios_path)[scenario_id]

    inputs = [build_experiment_input(scenario) for _ in ALL_CONFIGS]
    assert all(i == inputs[0] for i in inputs)


# 5. output schema validation ----------------------------------------------------------

def test_run_scenario_returns_a_schema_valid_output(fixture_paths, fixture_manifest):
    users_path, scenarios_path = fixture_paths
    users_by_id = load_users(users_path)
    scenarios_by_id = load_scenarios(scenarios_path)
    scenario_id = fixture_manifest["scenario_ids"][0]
    config = load_config(CONFIGS_DIR / "baseline.yaml")

    output = run_scenario(
        ConfigurationName.BASELINE, scenarios_by_id[scenario_id], users_by_id, "test-run", config, fixture_manifest
    )
    assert isinstance(output, ExperimentOutput)
    assert ExperimentOutput.model_validate_json(output.model_dump_json()) == output


def test_run_scenario_rejects_unknown_scenario_id(fixture_paths, fixture_manifest, tmp_path):
    with pytest.raises(ValueError):
        _run_one(
            ConfigurationName.BASELINE, "S_DOES_NOT_EXIST", fixture_paths, fixture_manifest, tmp_path / "results"
        )


# 6. deterministic experiment IDs -------------------------------------------------------

def test_experiment_ids_are_deterministic_across_repeated_runs(fixture_paths, fixture_manifest, tmp_path):
    scenario_id = fixture_manifest["scenario_ids"][0]
    first = _run_one(ConfigurationName.BASELINE, scenario_id, fixture_paths, fixture_manifest, tmp_path / "r1")
    second = _run_one(ConfigurationName.BASELINE, scenario_id, fixture_paths, fixture_manifest, tmp_path / "r2")
    assert first.experiment_id == second.experiment_id
    assert first.model_dump() == second.model_dump()


# 7. result paths are configuration-specific ---------------------------------------------

def test_result_path_differs_by_configuration():
    paths = {c: result_path(c, "same-experiment-id") for c in ALL_CONFIGS}
    assert len(set(paths.values())) == len(ALL_CONFIGS)
    for configuration, path in paths.items():
        assert path.parent.name == configuration.value


def test_persisted_results_land_in_the_correct_configuration_directory(fixture_paths, fixture_manifest, tmp_path):
    scenario_id = fixture_manifest["scenario_ids"][0]
    results_dir = tmp_path / "results"
    for configuration in ALL_CONFIGS:
        output = _run_one(configuration, scenario_id, fixture_paths, fixture_manifest, results_dir)
        expected = results_dir / configuration.value / f"{output.experiment_id}.json"
        assert expected.exists()
        persisted = load_json(expected)
        assert persisted["configuration"] == configuration.value


# 8. source datasets remain unchanged ----------------------------------------------------

def test_running_scenarios_does_not_modify_source_datasets(fixture_paths, fixture_manifest, tmp_path):
    users_path, scenarios_path = fixture_paths
    before_users = users_path.read_text(encoding="utf-8")
    before_scenarios = scenarios_path.read_text(encoding="utf-8")

    for configuration in ALL_CONFIGS:
        _run_one(configuration, fixture_manifest["scenario_ids"][0], fixture_paths, fixture_manifest, tmp_path / "results")

    assert users_path.read_text(encoding="utf-8") == before_users
    assert scenarios_path.read_text(encoding="utf-8") == before_scenarios


# 9. baseline profile isolation -----------------------------------------------------------

def test_baseline_and_rag_results_carry_no_profile_provenance(fixture_paths, fixture_manifest, tmp_path):
    scenario_id = fixture_manifest["scenario_ids"][0]
    results_dir = tmp_path / "results"
    for configuration in (ConfigurationName.BASELINE, ConfigurationName.RAG):
        output = _run_one(configuration, scenario_id, fixture_paths, fixture_manifest, results_dir)
        assert "profile_user_id" not in output.artifacts[0].provenance, configuration


# 10. personalized/full profile access -----------------------------------------------------

def test_personalized_and_full_copilot_results_carry_the_correct_profile_provenance(
    fixture_paths, fixture_manifest, tmp_path
):
    users_path, scenarios_path = fixture_paths
    scenario_id = fixture_manifest["scenario_ids"][0]
    expected_user_id = load_scenarios(scenarios_path)[scenario_id].user_id
    results_dir = tmp_path / "results"
    for configuration in (ConfigurationName.PERSONALIZED, ConfigurationName.FULL_COPILOT):
        output = _run_one(configuration, scenario_id, fixture_paths, fixture_manifest, results_dir)
        assert output.artifacts[0].provenance.get("profile_user_id") == expected_user_id, configuration


def test_run_scenario_raises_for_unknown_user_reference(fixture_paths, fixture_manifest):
    users_path, scenarios_path = fixture_paths
    scenarios_by_id = load_scenarios(scenarios_path)
    scenario_id = fixture_manifest["scenario_ids"][0]
    bogus_scenario = scenarios_by_id[scenario_id].model_copy(update={"user_id": "U_NOT_A_REAL_USER"})
    config = load_config(CONFIGS_DIR / "personalized.yaml")

    with pytest.raises(ValueError):
        run_scenario(ConfigurationName.PERSONALIZED, bogus_scenario, {}, "test-run", config, fixture_manifest)


# 11. execution metadata completeness --------------------------------------------------------

def test_execution_metadata_is_complete_for_every_configuration(fixture_paths, fixture_manifest, tmp_path):
    scenario_id = fixture_manifest["scenario_ids"][0]
    results_dir = tmp_path / "results"
    for configuration in ALL_CONFIGS:
        output = _run_one(configuration, scenario_id, fixture_paths, fixture_manifest, results_dir)
        meta = output.execution_metadata
        assert meta.configuration == configuration
        assert meta.model_identifier
        assert meta.prompt_version
        assert meta.dataset_version == fixture_manifest["dataset_version"]
        assert meta.scenario_dataset_version == fixture_manifest["scenario_dataset_version"]
        assert meta.ground_truth_version == fixture_manifest["ground_truth_version"]
        assert meta.experiment_seed == fixture_manifest["random_seed"]


# 12. single-scenario execution -----------------------------------------------------------------

def test_run_scenarios_executes_exactly_one_scenario_when_given_one_id(fixture_paths, fixture_manifest, tmp_path):
    scenario_id = fixture_manifest["scenario_ids"][0]
    outputs = run_scenarios(
        ConfigurationName.BASELINE,
        [scenario_id],
        "test-run",
        users_path=fixture_paths[0],
        scenarios_path=fixture_paths[1],
        configs_dir=CONFIGS_DIR,
        manifest=fixture_manifest,
        results_dir=tmp_path / "results",
    )
    assert len(outputs) == 1
    assert outputs[0].scenario_id == scenario_id


def test_run_scenarios_rejects_an_empty_scenario_list(fixture_paths, fixture_manifest, tmp_path):
    with pytest.raises(ValueError):
        run_scenarios(
            ConfigurationName.BASELINE,
            [],
            "test-run",
            users_path=fixture_paths[0],
            scenarios_path=fixture_paths[1],
            configs_dir=CONFIGS_DIR,
            manifest=fixture_manifest,
            results_dir=tmp_path / "results",
        )


def test_cli_has_no_flag_that_defaults_to_running_everything():
    """The CLI requires --scenario-id explicitly; there is no --run-all-5000
    flag implemented in this phase (by design -- see module docstring)."""
    from experiments.run_experiment import main

    with pytest.raises(SystemExit):
        main(["--configuration", "baseline"])  # missing required --scenario-id
