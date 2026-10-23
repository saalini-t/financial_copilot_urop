"""Opt-in smoke test: one real call to the local Ollama server running
`qwen2.5:3b`. Skipped by default -- set RUN_OLLAMA_SMOKE_TEST=1 to run it.

This is the only test file in the suite that exercises the real network
path; tests/test_experiment_contracts.py and tests/test_experiment_runner.py
both mock the client, and tests/test_baseline_agent.py tests baseline's
parsing/error-handling logic with an injected fake client. This file proves
the real client + real model + real prompt actually produce something the
frozen schema accepts -- a claim this project does not make without having
actually run it.
"""

from __future__ import annotations

import os
import sys

import pytest

from src.agents import baseline
from src.models.experiment import ConfigurationName, ExecutionMetadata, build_experiment_input
from src.models.response import ExperimentOutput
from src.utils import load_json

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_OLLAMA_SMOKE_TEST") != "1",
    reason="Opt-in only: set RUN_OLLAMA_SMOKE_TEST=1 to run a real call against the local Ollama server",
)


def test_one_real_scenario_through_baseline_produces_a_valid_output():
    scenarios_raw = load_json("data/synthetic/scenarios.json")
    scenario_dict = scenarios_raw["scenarios"][0]
    from src.models.scenario import Scenario

    scenario = Scenario.model_validate(scenario_dict)
    experiment_input = build_experiment_input(scenario)

    execution_metadata = ExecutionMetadata(configuration=ConfigurationName.BASELINE, model_identifier="qwen2.5:3b")

    output = baseline.run(experiment_input, run_id="smoke-test", execution_metadata=execution_metadata)

    # Schema-level proof, not a claim about answer quality.
    assert ExperimentOutput.model_validate_json(output.model_dump_json()) == output
    assert output.scenario_id == scenario.scenario_id
    assert output.configuration == ConfigurationName.BASELINE
    assert output.confidence.available is False
    assert len(output.artifacts) == 1
    assert output.artifacts[0].output.get("raw_response") or output.abstention

    def _console_safe(text: str) -> str:
        # Windows' default console codepage (cp1252) can't encode the Unicode
        # rupee sign the synthetic scenarios use -- replace what it can't
        # print rather than let a debug print crash an otherwise-passing test.
        return text.encode(sys.stdout.encoding or "ascii", errors="backslashreplace").decode(
            sys.stdout.encoding or "ascii"
        )

    print(f"\nReal qwen2.5:3b response for {scenario.scenario_id}:")
    print(f"  question: {_console_safe(experiment_input.question)}")
    print(f"  abstention: {output.abstention} ({output.abstention_reason})")
    print(f"  decision: {_console_safe(output.decision)!r}")
    print(f"  explanation: {_console_safe(output.explanation)!r}")
