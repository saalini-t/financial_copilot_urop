"""Unit tests for src/agents/baseline.py's real inference logic -- entirely
offline. Every test injects a fake client via the `llm_client` parameter;
none of these ever touches a real network socket or a running Ollama server
(that's tests/test_baseline_llm_smoke.py's job).
"""

from __future__ import annotations

import pytest

from src.agents import baseline
from src.agents._llm_client import LLMClientError, LLMResponse
from src.models.experiment import ConfigurationName, ExecutionMetadata, ExperimentInput
from src.models.response import AbstentionReason
from src.models.scenario import ScenarioType


class _FakeClient:
    def __init__(self, raw_text=None, error=None):
        self._raw_text = raw_text
        self._error = error
        self.calls = []

    def generate(self, prompt, temperature=0.0):
        self.calls.append((prompt, temperature))
        if self._error is not None:
            raise self._error
        return LLMResponse(raw_text=self._raw_text, model="qwen2.5:3b")


@pytest.fixture
def experiment_input():
    return ExperimentInput(
        user_id="U000001",
        scenario_id="S000001",
        scenario_type=ScenarioType.BUDGETING,
        question="Can I increase my monthly savings without creating a cash-flow problem?",
        relevant_user_attributes={"monthly_income": 50000.0, "monthly_expenses": 30000.0},
        required_information=["monthly_income", "monthly_expenses"],
    )


@pytest.fixture
def execution_metadata():
    return ExecutionMetadata(configuration=ConfigurationName.BASELINE, model_identifier="qwen2.5:3b")


def test_valid_decision_json_produces_a_non_abstaining_output(experiment_input, execution_metadata):
    client = _FakeClient(raw_text='{"decision": "Increase savings", "explanation": "You have surplus.", "abstain": false, "abstention_reason": null}')
    output = baseline.run(experiment_input, run_id="r1", execution_metadata=execution_metadata, llm_client=client)

    assert output.abstention is False
    assert output.abstention_reason is None
    assert output.decision == "Increase savings"
    assert output.explanation == "You have surplus."
    assert output.confidence.available is False
    assert output.confidence.value is None
    assert output.evidence == []
    assert len(client.calls) == 1


def test_prompt_only_contains_the_question_never_relevant_user_attributes(experiment_input, execution_metadata):
    client = _FakeClient(raw_text='{"decision": "x", "explanation": "y", "abstain": false, "abstention_reason": null}')
    baseline.run(experiment_input, run_id="r1", execution_metadata=execution_metadata, llm_client=client)

    sent_prompt = client.calls[0][0]
    assert experiment_input.question in sent_prompt
    assert "50000" not in sent_prompt
    assert "monthly_income" not in sent_prompt


def test_model_reported_abstain_is_honored(experiment_input, execution_metadata):
    client = _FakeClient(
        raw_text='{"decision": "", "explanation": "Not enough information.", '
        '"abstain": true, "abstention_reason": "MISSING_REQUIRED_INFORMATION"}'
    )
    output = baseline.run(experiment_input, run_id="r1", execution_metadata=execution_metadata, llm_client=client)

    assert output.abstention is True
    assert output.abstention_reason == AbstentionReason.MISSING_REQUIRED_INFORMATION
    assert output.decision == ""


def test_model_reported_abstain_with_unrecognized_reason_falls_back_to_other(experiment_input, execution_metadata):
    client = _FakeClient(
        raw_text='{"decision": "", "explanation": "I refuse.", "abstain": true, "abstention_reason": "I_FEEL_LIKE_IT"}'
    )
    output = baseline.run(experiment_input, run_id="r1", execution_metadata=execution_metadata, llm_client=client)

    assert output.abstention is True
    assert output.abstention_reason == AbstentionReason.OTHER


def test_json_wrapped_in_markdown_fence_is_handled(experiment_input, execution_metadata):
    client = _FakeClient(
        raw_text='```json\n{"decision": "Save more", "explanation": "ok", "abstain": false, "abstention_reason": null}\n```'
    )
    output = baseline.run(experiment_input, run_id="r1", execution_metadata=execution_metadata, llm_client=client)

    assert output.abstention is False
    assert output.decision == "Save more"


def test_malformed_non_json_output_abstains_with_other_and_keeps_the_raw_text(experiment_input, execution_metadata):
    client = _FakeClient(raw_text="I think you should save more money, but I won't give you JSON.")
    output = baseline.run(experiment_input, run_id="r1", execution_metadata=execution_metadata, llm_client=client)

    assert output.abstention is True
    assert output.abstention_reason == AbstentionReason.OTHER
    assert output.artifacts[0].output["raw_response"].startswith("I think you should save more money")


def test_missing_required_json_key_abstains_with_other(experiment_input, execution_metadata):
    client = _FakeClient(raw_text='{"decision": "Save more", "abstain": false}')  # no "explanation"
    output = baseline.run(experiment_input, run_id="r1", execution_metadata=execution_metadata, llm_client=client)

    assert output.abstention is True
    assert output.abstention_reason == AbstentionReason.OTHER


def test_llm_client_error_abstains_with_tool_failure(experiment_input, execution_metadata):
    client = _FakeClient(error=LLMClientError("could not reach Ollama"))
    output = baseline.run(experiment_input, run_id="r1", execution_metadata=execution_metadata, llm_client=client)

    assert output.abstention is True
    assert output.abstention_reason == AbstentionReason.TOOL_FAILURE
    assert "could not reach Ollama" in output.explanation
    # no raw text exists for an infra failure -- the artifact output stays empty, not fabricated
    assert output.artifacts[0].output == {}


def test_output_always_validates_against_the_frozen_schema(experiment_input, execution_metadata):
    from src.models.response import ExperimentOutput

    cases = [
        _FakeClient(raw_text='{"decision": "d", "explanation": "e", "abstain": false, "abstention_reason": null}'),
        _FakeClient(raw_text='{"decision": "", "explanation": "e", "abstain": true, "abstention_reason": "OTHER"}'),
        _FakeClient(raw_text="not json"),
        _FakeClient(error=LLMClientError("boom")),
    ]
    for client in cases:
        output = baseline.run(experiment_input, run_id="r1", execution_metadata=execution_metadata, llm_client=client)
        assert ExperimentOutput.model_validate_json(output.model_dump_json()) == output
        assert output.confidence.available is False


def test_experiment_id_is_still_deterministic_with_real_logic(experiment_input, execution_metadata):
    client_a = _FakeClient(raw_text='{"decision": "d", "explanation": "e", "abstain": false, "abstention_reason": null}')
    client_b = _FakeClient(raw_text='{"decision": "different", "explanation": "e2", "abstain": false, "abstention_reason": null}')
    out_a = baseline.run(experiment_input, run_id="run-x", execution_metadata=execution_metadata, llm_client=client_a)
    out_b = baseline.run(experiment_input, run_id="run-x", execution_metadata=execution_metadata, llm_client=client_b)
    # experiment_id depends only on configuration + scenario_id + run_id, never on model content
    assert out_a.experiment_id == out_b.experiment_id == "baseline__S000001__run-x"
