# Explainable Financial Copilot

A research prototype and reproducible benchmark for **Explainable Generative AI-Based Financial Copilot for Personalized and Automated Financial Decision Support**. This is a research testbed, **not** a production system, and not financial advice — every user, scenario, and decision rule in this repository is synthetic.

## What this is

Fluent financial advice from an LLM isn't the same thing as *correct*, *suitable*, or *faithfully explained* advice. This project investigates that gap experimentally: a five-layer architecture (generative substrate → grounding → personalization → reasoning/action → explanation/governance) built around one core principle — **the user-facing explanation is assembled from inspectable artifacts** (retrieved evidence, deterministic tool output, constraint checks, rejected alternatives), never generated as an independent, unverifiable narrative.

Before any language model is called, this repository builds the pieces needed to evaluate one fairly:

- a **synthetic household-finance benchmark** (1,000 users, 5,000 decision scenarios across budgeting, debt prioritization, emergency-fund planning, investment allocation, and retirement)
- a **deterministic ground-truth engine** — an independent reference decision for every scenario, with bounded candidate catalogues, hard constraints, transparent scoring, and honest abstention
- a **frozen experiment contract** — one input/output schema all four planned configurations (baseline LLM, RAG, personalized, full copilot) must satisfy identically, with fairness guarantees enforced at the type level, not just by convention

## Current status

| Component | Status |
|---|---|
| Synthetic user generator & dataset (1,000 users) | ✅ Complete |
| Synthetic scenario generator & benchmark (5,000 scenarios) | ✅ Complete |
| Deterministic ground-truth engine (5,000 records) + audit | ✅ Complete |
| Experiment input/output contract, fairness rules | ✅ Complete |
| Experiment manifest + orchestration/runner | ✅ Complete |
| Dataset visualizations + research report | ✅ Complete |
| Real LLM calls, RAG retrieval, financial tools | ⬜ Not yet implemented |
| Candidate ranking inside an LLM configuration, evaluation metrics | ⬜ Not yet implemented |

**133/133 automated tests passing.** Every configuration currently returns a clearly-labeled placeholder — see [`src/agents/`](src/agents/) — so the contract and orchestration layer can be validated before any model, retrieval index, or tool is wired in.

## Repository structure

```
configs/                 Experiment configs: base.yaml + baseline/rag/personalized/full_copilot.yaml
data/synthetic/           users.json, scenarios.json, ground_truth.json, experiment_manifest.json
simulations/               generate_users.py, generate_scenarios.py
src/
  models/                 Pydantic schemas: User, Scenario, ExperimentInput/Output, Artifact, Evidence, ...
  config.py                ExperimentConfig loading (configs/*.yaml)
  utils.py                  Logging, seeding, JSON I/O
  decision/                 The deterministic ground-truth engine (catalogue, evaluator, ranking)
  agents/                    baseline / rag / personalized / full_copilot -- frozen-contract stubs
  tools/ personalization/ constraints/ retrieval/ explanation/ audit/ evaluation/
                            Placeholder packages reserved for later phases
experiments/                run_experiment.py, manifest.py -- orchestration layer
visualizations/              generate_user_plots.py -- dataset-visualization figures
results/                    raw/ (per-configuration outputs), metrics/, figures/
report/                     LaTeX research report (main.tex) + figures
tests/                      133 tests covering every module above
docs/                       Architecture, experiment design, evaluation protocol, data dictionary, reproducibility
```

## Setup

```bash
pip install -r requirements.txt
```

Python 3.10+. Copy `.env.example` to `.env` before a later phase that calls a real model (nothing reads it yet).

## Reproducing the benchmark

Run in order — each step reads the previous one's output read-only and never modifies it:

```bash
# 1. 1,000 synthetic users, seed 42
python simulations/generate_users.py

# 2. 5,000 scenarios (5 per user), grounded in the users above
python simulations/generate_scenarios.py

# 3. 5,000 deterministic ground-truth decisions, independent of any LLM
python -m src.decision.ground_truth

# 4. Experiment manifest: dataset versions, seed, the exact 5,000 scenario IDs
python -m experiments.manifest

# 5. Dataset visualizations (5 PNGs into visualizations/figures/)
python visualizations/generate_user_plots.py
```

Every step is deterministic: re-running any of them from the same seed reproduces byte-identical records (only a `generated_at` metadata timestamp differs). See [`docs/reproducibility.md`](docs/reproducibility.md).

### Running one scenario through a configuration (pilot / development only)

```bash
python -m experiments.run_experiment --configuration full_copilot --scenario-id S000001
```

Writes a schema-validated result to `results/raw/full_copilot/`. There is no flag to run all 5,000 scenarios yet — that's deliberately gated until a configuration does real reasoning instead of returning a placeholder.

## Running tests

```bash
python -m pytest
```

`pyproject.toml` sets `pythonpath = ["."]`, so `import src...` resolves regardless of how pytest is invoked.

## Documentation

- [`docs/architecture.md`](docs/architecture.md) — five-layer architecture and module map
- [`docs/experiment_design.md`](docs/experiment_design.md) — candidate catalogue, tie-break hierarchy, configuration ladder
- [`docs/experiment_protocol.md`](docs/experiment_protocol.md) — the frozen ExperimentInput/ExperimentOutput contract, fairness constraints, and access rules for the four configurations
- [`docs/evaluation_protocol.md`](docs/evaluation_protocol.md) — D1–D5 metrics and faithfulness tests A–E
- [`docs/data_dictionary.md`](docs/data_dictionary.md) — every model field, by file, including generation logic
- [`docs/ground_truth_scoring.md`](docs/ground_truth_scoring.md) — every hard constraint, soft-score formula, and constant in the ground-truth engine, audited for hidden constants and independence from any LLM/RAG/copilot
- [`docs/reproducibility.md`](docs/reproducibility.md) — what's recorded per run, determinism notes

## Research report

A full LaTeX writeup — motivation, literature review, architecture, dataset design, ground-truth methodology, experiment protocol, and reproducibility evidence — is in [`report/main.tex`](report/main.tex) (figures in `report/figures/`).

## Design principles

- **No invented facts.** Every value a scenario or a ground-truth decision cites is copied from the actual generated user record — never fabricated, checked by dedicated tests.
- **Deterministic where determinism is possible.** No random-number call anywhere in the ground-truth engine; it's a pure function of its two input files.
- **Explanations are assembled, not generated independently.** The design deliberately excludes any path where a model is asked to narrate its own reasoning as if that were proof of the decision process.
- **Fairness enforced structurally.** The baseline and RAG configurations have no `profile` parameter in their function signature at all — not filtered out by convention, absent from the type signature, so passing one raises a `TypeError`.

## Quick check

```python
from src.models import User, RiskTolerance, FinancialLiteracy
from src.config import load_config

user = User(
    user_id="U000001", age=34, monthly_income=72000, monthly_expenses=32000,
    savings=40000, assets=120000, liabilities=0,
    risk_tolerance=RiskTolerance.LOW, investment_horizon_years=25,
    emergency_fund_target=96000, liquidity_requirements=32000,
    financial_literacy=FinancialLiteracy.MEDIUM,
)
config = load_config("configs/full_copilot.yaml")
print(config.modules)
```

## Author

Saalini T — Department of Computing Technologies, SRM Institute of Science and Technology.
