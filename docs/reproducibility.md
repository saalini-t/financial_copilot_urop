# Reproducibility

## What's implemented so far

**Phase 1** — typed data models (`src/models/`), configuration loading
(`src/config.py`), and reproducibility utilities (`src/utils.py`). `src/tools`,
`src/personalization`, `src/constraints`, `src/retrieval`, `src/agents`,
`src/explanation`, `src/audit`, and `src/evaluation` are empty placeholder packages
so later phases have somewhere to land; none of them contains logic, mocked or
otherwise.

**Phase 3** — the synthetic household dataset generator
(`simulations/generate_users.py`).

**Phase 4** — the synthetic scenario generator (`simulations/generate_scenarios.py`),
template-based, no LLM.

**Phase 5** — the deterministic ground-truth engine (`src/decision/`), audited
in place (no separate phase number) for scientific suitability as an
evaluation oracle — see `docs/ground_truth_scoring.md` for the full rule set
and the audit's findings. There is no LLM call anywhere in this repository yet.

## Dataset generation reproducibility

`python simulations/generate_users.py --num-users 1000 --seed 42` run twice
produces byte-identical `users` records. Internally: `set_seed(seed)` seeds both
`random` and `numpy` once at the start of `generate_users()`, every sampling call
after that draws from those seeded generators in a fixed order, and the only
non-deterministic value produced anywhere in the run — the `generated_at`
timestamp — is metadata attached after generation, never read back into a user
record. The same seed and `--num-users` always yields the same `metadata` block
too (`dataset_version`, `schema_version`, `random_seed`, `num_users`,
`num_edge_cases`), aside from that one timestamp field.

## Recorded per experiment run

- Random seed (`src/utils.set_seed`, seeds both `random` and `numpy`)
- Experiment ID (`src/utils.new_experiment_id`, format `<config_name>-<UTC timestamp>-<8 hex chars>`)
- Configuration (`config_name`, one of `configs/*.yaml`)
- Dataset version (synthetic users + scenarios — `data/synthetic/`)
- Candidate catalogue version (`catalogue_version`, `src/models/candidate.py`)
- Ground-truth engine version (`ground_truth_engine_version`, `configs/base.yaml`)
- Tool versions (`ToolTraceEntry.tool_version`, once the tool layer exists)
- Model identifier and parameters (`model_id`, `temperature`, `configs/base.yaml`)
- Confidence threshold and scoring weights version (`min_confidence`, `scoring_weights`)
- Timestamp (`AuditArtifact.timestamp`, UTC)

## Ground-truth generation reproducibility

`python -m src.decision.ground_truth` reads `data/synthetic/users.json` and
`data/synthetic/scenarios.json` (never modifying either — verified by a
dedicated test that hashes both files before and after a full run) and
contains no randomness at all: every `GroundTruthRecord` is a pure function of
its two inputs. Regenerating `ground_truth.json` from the same seed-42 source
datasets twice produces byte-identical `ground_truth` records and metadata
(aside from the `generated_at` timestamp) — reverified after the Phase 5 audit's
investment-scoring fix (see `docs/ground_truth_scoring.md`).

## Two invariants

The same scenario IDs are evaluated across all four configurations — synthetic
users are never regenerated per configuration. Ground truth never depends on an LLM
output, RAG, generated explanations, model confidence, or future copilot
candidate generation, under any configuration, at any point — audited
explicitly in the Phase 5 ground-truth review.

## Setup and tests

```bash
cd financial-copilot
pip install -r requirements.txt
python -m pytest
```

`pyproject.toml` sets `pythonpath = ["."]` for pytest, so `import src...` works from
the repository root regardless of how pytest is invoked.

## Determinism notes

- `ExperimentConfig` merges each `configs/*.yaml` over `configs/base.yaml` (deep
  merge, override wins) — see `src/config.load_config`.
- All model timestamps default to UTC `datetime.now`; pass an explicit value in
  tests that need determinism.
- `set_seed(seed)` must be called before any randomized step (synthetic data
  generation, sampling-based LLM calls in later phases) and the seed used must be
  logged, not assumed.
