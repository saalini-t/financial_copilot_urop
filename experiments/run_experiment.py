"""The experiment execution/orchestration layer -- Phase 6B.

Dispatches an ExperimentInput to exactly one of the four frozen Phase 6A agent
interfaces (src/agents/), re-validates the result against the frozen
ExperimentOutput schema, and persists it under results/raw/<configuration>/.

No LLM call, retrieval, tool, ranking, or evaluation logic lives here -- every
agent invoked is still the Phase 6A placeholder stub (src/agents/_stub.py).
This module only proves the plumbing: identical input construction, identical
output validation, and a configuration-specific persistence path, for all
four configurations alike.

Usage (single or a few scenarios only -- this phase never runs all 5000):
    python -m experiments.run_experiment --configuration baseline --scenario-id S000001
    python -m experiments.run_experiment --configuration full_copilot --scenario-id S000001 S000002
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.manifest import build_manifest
from src.agents import baseline, full_copilot, personalized, rag
from src.config import ExperimentConfig, load_config
from src.models.experiment import ConfigurationName, ExecutionMetadata, build_experiment_input
from src.models.response import ExperimentOutput
from src.models.scenario import Scenario
from src.models.user import User
from src.utils import load_json, save_json

DEFAULT_USERS_PATH = REPO_ROOT / "data" / "synthetic" / "users.json"
DEFAULT_SCENARIOS_PATH = REPO_ROOT / "data" / "synthetic" / "scenarios.json"
DEFAULT_RESULTS_DIR = REPO_ROOT / "results" / "raw"
CONFIGS_DIR = REPO_ROOT / "configs"

_AGENT_MODULES = {
    ConfigurationName.BASELINE: baseline,
    ConfigurationName.RAG: rag,
    ConfigurationName.PERSONALIZED: personalized,
    ConfigurationName.FULL_COPILOT: full_copilot,
}

# The only two configurations whose run() accepts a profile at all -- see
# src/agents/*.py signatures. This set exists so the dispatch below asks each
# agent for exactly what its own signature demands, never more.
_PROFILE_CONFIGURATIONS = {ConfigurationName.PERSONALIZED, ConfigurationName.FULL_COPILOT}


def load_users(path: Path = DEFAULT_USERS_PATH) -> dict[str, User]:
    """Read-only: returns a fresh dict of typed User records, never a handle
    that could write back to the source file."""
    raw = load_json(path)
    return {u["user_id"]: User.model_validate(u) for u in raw["users"]}


def load_scenarios(path: Path = DEFAULT_SCENARIOS_PATH) -> dict[str, Scenario]:
    raw = load_json(path)
    return {s["scenario_id"]: Scenario.model_validate(s) for s in raw["scenarios"]}


def _execution_metadata(
    configuration: ConfigurationName, config: ExperimentConfig, manifest: dict
) -> ExecutionMetadata:
    """Every field here comes from configs/*.yaml or the manifest -- never
    hard-coded, and never a credential (ExecutionMetadata's schema has no
    field for one)."""
    return ExecutionMetadata(
        configuration=configuration,
        model_identifier=config.model_id,
        prompt_version=config.prompt_version,
        dataset_version=manifest.get("dataset_version"),
        scenario_dataset_version=manifest.get("scenario_dataset_version"),
        ground_truth_version=manifest.get("ground_truth_version"),
        experiment_seed=manifest.get("random_seed"),
        retrieval_configuration=dict(config.retrieval),
        tool_configuration=dict(config.tool_config),
    )


def run_scenario(
    configuration: ConfigurationName,
    scenario: Scenario,
    users_by_id: dict[str, User],
    run_id: str,
    config: ExperimentConfig,
    manifest: dict,
) -> ExperimentOutput:
    """Build the common input, dispatch to exactly one frozen agent interface,
    and return a schema-validated ExperimentOutput. Never mutates `scenario`
    or any User record -- `build_experiment_input` copies values out, and
    nothing here writes back to either."""
    experiment_input = build_experiment_input(scenario)
    execution_metadata = _execution_metadata(configuration, config, manifest)
    agent = _AGENT_MODULES[configuration]

    if configuration in _PROFILE_CONFIGURATIONS:
        user = users_by_id.get(scenario.user_id)
        if user is None:
            raise ValueError(f"{scenario.scenario_id} references unknown user_id '{scenario.user_id}'")
        raw_output = agent.run(experiment_input, profile=user, run_id=run_id, execution_metadata=execution_metadata)
    else:
        raw_output = agent.run(experiment_input, run_id=run_id, execution_metadata=execution_metadata)

    # Explicit re-validation before persistence -- never trust an agent's
    # return value implicitly, even a stub's. A future real implementation
    # that returns something malformed must fail here, not silently persist.
    return ExperimentOutput.model_validate(raw_output.model_dump(mode="json"))


def result_path(
    configuration: ConfigurationName, experiment_id: str, results_dir: Path = DEFAULT_RESULTS_DIR
) -> Path:
    return results_dir / configuration.value / f"{experiment_id}.json"


def persist_result(output: ExperimentOutput, results_dir: Path = DEFAULT_RESULTS_DIR) -> Path:
    path = result_path(output.configuration, output.experiment_id, results_dir)
    save_json(output, path)
    return path


def run_scenarios(
    configuration: ConfigurationName,
    scenario_ids: list[str],
    run_id: str,
    *,
    users_path: Path = DEFAULT_USERS_PATH,
    scenarios_path: Path = DEFAULT_SCENARIOS_PATH,
    configs_dir: Path = CONFIGS_DIR,
    manifest: dict | None = None,
    results_dir: Path = DEFAULT_RESULTS_DIR,
) -> list[ExperimentOutput]:
    """Run and persist `configuration` over exactly the given `scenario_ids` --
    never a default-to-everything path. Callers wanting the full 5000-scenario
    benchmark must pass every ID explicitly; this phase provides no shortcut
    for that (see module docstring)."""
    if not scenario_ids:
        raise ValueError("scenario_ids must be non-empty -- there is no implicit 'run everything' mode")

    users_by_id = load_users(users_path)
    scenarios_by_id = load_scenarios(scenarios_path)
    config = load_config(configs_dir / f"{configuration.value}.yaml")
    manifest = manifest if manifest is not None else build_manifest()

    outputs = []
    for scenario_id in scenario_ids:
        scenario = scenarios_by_id.get(scenario_id)
        if scenario is None:
            raise ValueError(f"Unknown scenario_id '{scenario_id}'")
        output = run_scenario(configuration, scenario, users_by_id, run_id, config, manifest)
        persist_result(output, results_dir)
        outputs.append(output)
    return outputs


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--configuration", required=True, choices=[c.value for c in ConfigurationName])
    parser.add_argument(
        "--scenario-id",
        required=True,
        nargs="+",
        help="One or more scenario IDs. There is no flag to run all 5000 in this phase.",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Defaults to a deterministic ID derived from the manifest's recorded seed.",
    )
    args = parser.parse_args(argv)

    manifest = build_manifest()
    run_id = args.run_id or f"seed{manifest['random_seed']}"
    configuration = ConfigurationName(args.configuration)

    outputs = run_scenarios(configuration, args.scenario_id, run_id, manifest=manifest)
    for output in outputs:
        path = result_path(output.configuration, output.experiment_id)
        print(f"{output.experiment_id} -> {path}")


if __name__ == "__main__":
    main()
