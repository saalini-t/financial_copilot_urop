"""Configuration 1 -- Baseline.

Allowed inputs: the scenario's question only (via ExperimentInput). No
retrieval, no persistent user profile, no deterministic financial tools, free-
form explanation. `run()` has no profile parameter in its signature at all --
there is no way to pass a User object to it even by mistake; this is a
structural fairness guarantee, not just a documented convention (see
tests/test_experiment_contracts.py::test_baseline_and_rag_have_no_profile_parameter).

Phase 5: real inference via a local Ollama model (default `qwen2.5:3b`,
configurable through `configs/baseline.yaml`'s `model_id`). The prompt
(`src/agents/prompts/baseline_v1.txt`) is built from `experiment_input.question`
only -- `relevant_user_attributes` stays unread here, exactly as the frozen
contract requires. `confidence` is always reported as unavailable: baseline
has no deterministic scoring mechanism to take a margin over, and the prompt
never asks the model for a confidence number, so there is nothing calibrated
to report. A model-reported `abstain`/`abstention_reason` is honored but is
the model's own self-assessment, not a verified judgment -- the same caveat
this project already applies to any self-reported confidence.

`llm_client` is an injection point for tests; production callers (including
`experiments/run_experiment.py`, unmodified) simply omit it, which
constructs a real `OllamaLLMClient` using the model named in
`execution_metadata.model_identifier`.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.agents._llm_client import LLMClientError, OllamaLLMClient
from src.models.artifacts import Artifact
from src.models.experiment import ConfigurationName, ExecutionMetadata, ExperimentInput, make_experiment_id
from src.models.response import AbstentionReason, Confidence, ExperimentOutput

PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "baseline_v1.txt"
PROMPT_TEMPLATE = PROMPT_PATH.read_text(encoding="utf-8")

_RAW_TEXT_PREVIEW_CHARS = 2000  # cap how much of a malformed response we store, not truncate silently to nothing


def _strip_markdown_fence(text: str) -> str:
    """Small local models frequently wrap JSON in ```json ... ``` even when
    told not to. Strip one such fence if present; leave everything else as-is."""
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    return stripped


def _parse_model_json(raw_text: str) -> dict:
    """Raises ValueError (with a clear message) if the text isn't the expected shape."""
    candidate = _strip_markdown_fence(raw_text)
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise ValueError(f"model output was not valid JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError(f"model output was valid JSON but not an object: {type(payload).__name__}")

    required = {"decision": str, "explanation": str, "abstain": bool}
    for key, expected_type in required.items():
        if key not in payload:
            raise ValueError(f"model output JSON is missing required key '{key}'")
        if not isinstance(payload[key], expected_type):
            raise ValueError(
                f"model output JSON key '{key}' should be {expected_type.__name__}, "
                f"got {type(payload[key]).__name__}"
            )

    reason = payload.get("abstention_reason")
    if reason is not None and not isinstance(reason, str):
        raise ValueError("model output JSON key 'abstention_reason' should be a string or null")

    return payload


def _map_model_abstention_reason(model_reason: str | None) -> AbstentionReason:
    """The model's own stated reason is honored only when it names one of the
    7 frozen values exactly (case-insensitive); anything else -- including a
    genuinely sensible-sounding free-text reason -- falls back to OTHER
    rather than silently inventing a new category."""
    if model_reason:
        upper = model_reason.strip().upper()
        for member in AbstentionReason:
            if member.value == upper:
                return member
    return AbstentionReason.OTHER


def _abstain_output(
    experiment_input: ExperimentInput,
    run_id: str,
    execution_metadata: ExecutionMetadata,
    *,
    reason: AbstentionReason,
    explanation: str,
    raw_text: str | None,
) -> ExperimentOutput:
    experiment_id = make_experiment_id(ConfigurationName.BASELINE, experiment_input.scenario_id, run_id)
    artifact_output = {"raw_response": raw_text[:_RAW_TEXT_PREVIEW_CHARS]} if raw_text else {}
    return ExperimentOutput(
        experiment_id=experiment_id,
        configuration=ConfigurationName.BASELINE,
        scenario_id=experiment_input.scenario_id,
        user_id=experiment_input.user_id,
        decision="",
        abstention=True,
        abstention_reason=reason,
        explanation=explanation,
        evidence=[],
        confidence=Confidence(
            available=False,
            method="not_applicable",
            reason="BASELINE has no deterministic scoring mechanism to compute a calibrated confidence from",
        ),
        artifacts=[
            Artifact(
                artifact_type="llm_inference",
                source="src.agents.baseline",
                input={"question": experiment_input.question},
                output=artifact_output,
                execution_id=experiment_id,
                provenance={"scenario_id": experiment_input.scenario_id, "user_id": experiment_input.user_id},
            )
        ],
        execution_metadata=execution_metadata,
    )


def run(
    experiment_input: ExperimentInput,
    run_id: str,
    execution_metadata: ExecutionMetadata,
    llm_client: OllamaLLMClient | None = None,
) -> ExperimentOutput:
    if llm_client is None:
        llm_client = OllamaLLMClient(model=execution_metadata.model_identifier or "qwen2.5:3b")

    prompt = PROMPT_TEMPLATE.format(question=experiment_input.question)

    try:
        response = llm_client.generate(prompt, temperature=0.0)
    except LLMClientError as exc:
        return _abstain_output(
            experiment_input,
            run_id,
            execution_metadata,
            reason=AbstentionReason.TOOL_FAILURE,
            explanation=f"The language model backend could not be reached or failed: {exc}",
            raw_text=None,
        )

    try:
        payload = _parse_model_json(response.raw_text)
    except ValueError as exc:
        return _abstain_output(
            experiment_input,
            run_id,
            execution_metadata,
            reason=AbstentionReason.OTHER,
            explanation=f"The model responded, but its output could not be parsed as the expected structured answer: {exc}",
            raw_text=response.raw_text,
        )

    experiment_id = make_experiment_id(ConfigurationName.BASELINE, experiment_input.scenario_id, run_id)
    artifact = Artifact(
        artifact_type="llm_inference",
        source="src.agents.baseline",
        input={"question": experiment_input.question},
        output={"raw_response": response.raw_text[:_RAW_TEXT_PREVIEW_CHARS]},
        execution_id=experiment_id,
        provenance={
            "scenario_id": experiment_input.scenario_id,
            "user_id": experiment_input.user_id,
            "model": response.model,
        },
    )
    confidence = Confidence(
        available=False,
        method="not_applicable",
        reason="BASELINE has no deterministic scoring mechanism to compute a calibrated confidence from",
    )

    if payload["abstain"]:
        return ExperimentOutput(
            experiment_id=experiment_id,
            configuration=ConfigurationName.BASELINE,
            scenario_id=experiment_input.scenario_id,
            user_id=experiment_input.user_id,
            decision="",
            abstention=True,
            abstention_reason=_map_model_abstention_reason(payload.get("abstention_reason")),
            explanation=payload["explanation"],
            evidence=[],
            confidence=confidence,
            artifacts=[artifact],
            execution_metadata=execution_metadata,
        )

    return ExperimentOutput(
        experiment_id=experiment_id,
        configuration=ConfigurationName.BASELINE,
        scenario_id=experiment_input.scenario_id,
        user_id=experiment_input.user_id,
        decision=payload["decision"],
        abstention=False,
        abstention_reason=None,
        explanation=payload["explanation"],
        evidence=[],
        confidence=confidence,
        artifacts=[artifact],
        execution_metadata=execution_metadata,
    )
