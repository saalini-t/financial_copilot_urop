# Architecture

Explainable Generative AI-Based Financial Copilot for Personalized and Automated
Financial Decision Support — research prototype, not a production system.

## Five layers

| Layer | Name | Responsibility | Mechanism |
|---|---|---|---|
| L1 | Generative Substrate | Foundation/finance-adapted LLM; language in, language out | LLM inference |
| L2 | Grounding | Retrieval over financial documents and structured data | Retrieval + deterministic APIs |
| L3 | Personalization | User profile, goals, risk tolerance, constraints, persistent state | Structured profile store |
| L4 | Reasoning & Action | Planning, tool selection, deterministic calculation, candidate generation, suitability filtering, guardrails, abstention | Deterministic code + constrained LLM calls |
| L5 | Explanation & Governance | Evidence/tool/constraint traces, rejected alternatives, assumptions, explanation, audit logging | Deterministic assembly + templated NL |

## Core principle: explanations are assembled, not asked for

The Explanation Engine (L5) never prompts the LLM to introspect on its own reasoning.
It renders a **Communication Artifact** (short natural-language explanation shown to
the user) from an **Audit Artifact** (structured, machine-readable record of evidence,
tool traces, constraints, rejected candidates, assumptions, and the final decision).
The LLM appears in exactly three call sites in the full pipeline: intent
classification, candidate framing (wording only — see the candidate catalogue in
`experiment_design.md`), and explanation phrasing. It never computes a number a
deterministic tool could compute, and never decides which candidates exist.

## Twenty modules

User Interface/API, User Profile Manager, Intent/Decision Classifier, Retrieval/RAG
Engine, Financial Knowledge Base, Personalization Engine, Constraint and Suitability
Engine, Deterministic Financial Tool Layer, Decision/Recommendation Engine,
Abstention/Guardrail Module, Explanation Engine, Evidence Trace, Tool Trace,
Constraint Trace, Audit Logger, Evaluation Engine, Experiment Manager, Synthetic
Dataset Generator, Ground Truth Generator, Results/Metrics Store.

Their layer assignment and LLM/deterministic/hybrid classification live in
`data_dictionary.md` alongside the schemas each module produces or consumes; this
repository currently implements only the schemas (`src/models/`) and configuration
loading (`src/config.py`) — see `reproducibility.md` for what Phase 1 does and does
not include.

## Supported scenarios

Budgeting, debt repayment vs. investment, emergency-fund planning, investment
allocation, retirement planning — see `ScenarioType` in `src/models/scenario.py` and
the candidate catalogue in `experiment_design.md`.
