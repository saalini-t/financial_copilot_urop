# Experiment Protocol

Phase 6A: the frozen interface and access-control contract every configuration
must satisfy before any LLM, RAG, or tool logic is implemented. See
`docs/experiment_design.md` for the candidate catalogue and configuration
ladder, `docs/evaluation_protocol.md` for the D1–D5 metrics, and
`docs/ground_truth_scoring.md` for the independent oracle these configurations
will eventually be scored against. This document is about the *contract*, not
the metrics or the scoring rules.

## Research question

Does grounding a financial copilot's recommendation in retrieved evidence,
personalization, and a deterministic decision/constraint layer improve
decision correctness, faithfulness, personalization, calibrated abstention,
and governance over a conventional LLM advisor — and which of those layers is
responsible for the improvement?

## The four configurations

| Configuration | Module | Question access | Profile access | Retrieval | Tools | Constraints/abstention | Explanation |
|---|---|---|---|---|---|---|---|
| `baseline` | `src/agents/baseline.py` | question only | none | no | no | no | free-form |
| `rag` | `src/agents/rag.py` | question only | none | yes | no | no | citation-based |
| `personalized` | `src/agents/personalized.py` | question + profile | full `User` | yes | yes | no | narrative |
| `full_copilot` | `src/agents/full_copilot.py` | question + profile | full `User` | yes | yes | yes | artifact-based |

## Controlled variables (identical across all four)

- **The scenario itself.** Every configuration is built from the exact same
  `Scenario` record via `build_experiment_input()` (`src/models/experiment.py`)
  — same `question` text, same `scenario_id`, same `relevant_user_attributes`
  snapshot. No configuration receives a rephrased or enriched question.
- **The dataset.** All four configurations run on the same 5000 scenario IDs
  from `data/synthetic/scenarios.json` (Phase 4), referencing the same 1000
  users from `data/synthetic/users.json` (Phase 3). No scenario is added,
  removed, or altered between configurations — see "Common input dataset" below.
- **The ground-truth reference.** All four are evaluated against the same
  5000 `data/synthetic/ground_truth.json` records (Phase 5) — a deterministic
  oracle that never depends on any configuration's output.
- **The substrate**, once real LLM calls exist: model identifier and
  temperature come from `configs/base.yaml`, shared by all four unless a
  configuration explicitly overrides them — comparisons are meant to isolate
  architecture, not backbone-model differences.

## Independent variable

System configuration — one of `baseline`, `rag`, `personalized`, `full_copilot`
(`ConfigurationName` in `src/models/experiment.py`).

## Dependent variables

D1 Correctness, D2 Faithfulness, D3 Personalization, D4 Abstention, D5
Governance — defined in full in `docs/evaluation_protocol.md`. Phase 6A does
not implement any metric computation; it only guarantees every configuration's
output has the shape (`ExperimentOutput`) those metrics will later be computed
from.

## Common input dataset

`ExperimentInput` (`src/models/experiment.py`) is the only thing any
configuration's `run()` function receives that identifies the scenario:

```
user_id, scenario_id, scenario_type, question,
relevant_user_attributes, required_information
```

`build_experiment_input(scenario)` is the single factory that constructs it —
every configuration goes through this one function, so there is no second
code path that could produce a divergent view of the same scenario. The
source `Scenario` and `User` records are never modified: `build_experiment_input`
copies values out rather than holding a reference, and no `src/agents/*.py`
module has a code path that writes to `data/synthetic/`.

## Ground-truth reference

`data/synthetic/ground_truth.json` (Phase 5) is computed once, independently
of every configuration, and never recomputed per configuration. A
configuration's `decision` and `abstention_reason` are free to disagree with
the ground truth's — that disagreement is exactly what later evaluation
phases measure. The ground-truth engine (`src/decision/`) is not called from
any `src/agents/*.py` module and never will be; it is the oracle these
configurations are checked against, not a component they share.

## Fairness constraints

1. **Identical scenario, verbatim.** `build_experiment_input` is the only
   constructor; `question` and `relevant_user_attributes` are never edited
   per configuration (`tests/test_experiment_contracts.py::test_all_four_configurations_receive_the_exact_same_question_text`).
2. **No hidden profile access.** `baseline.run()` and `rag.run()` have no
   `profile` parameter in their function signature at all — this is enforced
   by Python itself (calling either with a `profile=` argument raises
   `TypeError`), not by convention or code review
   (`test_baseline_and_rag_have_no_profile_parameter_in_their_signature`,
   `test_baseline_rejects_a_profile_argument_if_one_is_attempted`).
3. **Explicit, symmetric profile access.** `personalized.run()` and
   `full_copilot.run()` both require a `profile: User` parameter — the full
   synthetic profile, passed once, explicitly, by the harness that calls
   them. Neither agent looks a user up internally by ID; there is no
   internal database handle for either to reach through.
4. **No configuration mutates its inputs.** Verified directly:
   `test_no_agent_mutates_the_experiment_input_or_profile` deep-copies the
   input and profile before calling every configuration and asserts equality
   after.
5. **Same scenario ID set, every run.** The evaluation protocol always
   targets the same 5000 scenario IDs; a partial or resampled run for one
   configuration and not another would break comparability and is out of
   scope for any harness built on this contract.

## What each configuration is allowed to access

- **`baseline`** — `question` only. No `relevant_user_attributes` should be
  read by the agent's own logic once real reasoning exists (they remain
  present on `ExperimentInput` for audit/bookkeeping parity — see
  `src/models/experiment.py`'s module docstring for why the field exists on
  every configuration's input regardless), no profile, no retrieval, no tools.
- **`rag`** — `question` plus retrieved evidence (once implemented). No
  profile. `relevant_user_attributes` unused for the same reason as baseline.
- **`personalized`** — `question` plus the full `profile: User` parameter,
  plus retrieval and deterministic tools (per the already-frozen
  Configuration 3 definition in `docs/experiment_design.md`). No hard-constraint
  or abstention pipeline.
- **`full_copilot`** — everything: `question`, `profile`, retrieval, bounded
  candidate catalogue, deterministic tools, hard constraints, ranking,
  deterministic confidence, abstention, artifact-based explanation, audit log.

## Reproducibility requirements

- **Deterministic experiment IDs** — `make_experiment_id(configuration, scenario_id, run_id)`
  (`src/models/experiment.py`) is a pure string join; the same three inputs
  always produce the same ID (`test_experiment_id_is_deterministic_given_the_same_inputs`).
- **No secrets in configuration.** `configs/*.yaml` and `ExecutionMetadata`
  hold experimental settings only (model identifier, prompt version, dataset
  versions, seed, retrieval/tool parameters) — never an API key or credential
  (`test_configuration_yaml_does_not_hard_code_secrets`,
  `test_execution_metadata_never_carries_a_key_like_field`).
- **No hard-coded settings in agent code.** Model name, temperature, prompt
  version, retrieval parameters, and thresholds live in `configs/*.yaml`
  (loaded via `src.config.load_config`), never inline in `src/agents/*.py`.
- **Confidence is never invented.** `Confidence.available=False` is a valid,
  expected state for configurations with no deterministic way to produce a
  number (`src/models/response.py`) — enforced by a validator that rejects a
  value being present without `available=True`, and vice versa.
- **Artifacts carry no chain-of-thought.** `Artifact.input`/`.output`
  (`src/models/artifacts.py`) are structured data only; nothing in this
  contract asks a model to expose hidden reasoning, and nothing in the schema
  has room for it.

## What Phase 6A does not do

No LLM call, no RAG retrieval, no external API, no financial-tool
implementation, no candidate ranking (that stays `src/decision/`'s job, per
Phase 5), and no evaluation-metric computation. Every `run()` function in
`src/agents/` returns a clearly-labeled placeholder
(`src/agents/_stub.py::build_stub_output`) that satisfies the schema above and
nothing more.
