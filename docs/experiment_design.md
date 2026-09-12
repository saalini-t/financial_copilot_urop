# Experiment Design

Frozen prior to implementation. Changes to anything below require a version bump
(`catalogue_version`, `ground_truth_engine_version` in `configs/base.yaml`), not a
silent edit.

## Candidate catalogue (`src/models/candidate.py`, version `1.0.0`)

| Scenario | Candidates (fixed order) | Liquidity-relevant |
|---|---|---|
| BUDGETING | maintain_current_budget, reduce_discretionary_spending, increase_monthly_savings, reduce_savings_target | No |
| DEBT_PRIORITIZATION | repay_high_interest_debt, repay_low_interest_debt, split_between_debt_and_savings, maintain_cash, invest_surplus | Yes |
| EMERGENCY_FUND | build_to_3_months, build_to_6_months, maintain_current_level, increase_monthly_contribution | Yes |
| INVESTMENT_ALLOCATION | conservative_allocation, moderate_allocation, growth_allocation, preserve_liquidity, debt_first | Yes |
| RETIREMENT | increase_retirement_contribution, maintain_contribution, delay_retirement, reduce_retirement_target, increase_current_savings | No |

The LLM may interpret the user's question into a scenario type, select/refer to
candidates by ID, and phrase the final explanation. It may not invent a candidate
outside the catalogue, invent a numerical calculation, or override a suitability
constraint — an unrecognized candidate ID fails schema validation before it reaches
the decision engine.

## Tie-breaking hierarchy (ground-truth engine)

1. Eliminate candidates with `feasibility_score < 1` (required inputs unavailable).
2. Eliminate candidates violating hard constraints (`suitability_status = rejected`).
3. Among remaining candidates, maximize `goal_alignment_score`.
4. Then minimize risk (maximize `suitability_score`).
5. Then maximize `financial_objective_score`.
6. Then maximize `liquidity_score`, only for scenarios marked liquidity-relevant above.
7. If still tied, use fixed catalogue order (`catalogue_order`, ascending).

Floats are tied when `abs(a - b) < tie_epsilon` (`1e-6`, configurable). No random
tie-breaking anywhere in the pipeline. Ground truth never depends on an LLM output.

## Configuration ladder

| Config | Pipeline | RAG | Tools | Personalization | Constraints | Explanation |
|---|---|---|---|---|---|---|
| 1 — baseline | query → LLM → recommendation → free-form explanation | — | — | — | — | free_form |
| 2 — rag | query → retrieval → LLM → recommendation → citation explanation | Yes | — | — | — | citation_based |
| 3 — personalized | profile → retrieval → tools → personalization → candidate evaluation → recommendation | Yes | Yes | Yes | partial | narrative |
| 4 — full_copilot | profile+query → intent classification → catalogue → retrieval → tools → personalization → hard constraints → ranking → confidence/abstention → recommendation → artifact explanation → audit record | Yes | Yes | Yes | full | artifact_based |

Each config file in `configs/` sets `modules.*` to realize exactly one row above,
merged over the shared defaults in `configs/base.yaml`. Every configuration runs the
identical scenario ID set — synthetic users are never regenerated between
configurations. Because only Configurations 3–4 generate candidates from the
catalogue internally, Configurations 1–2 need their free-form output mapped onto a
catalogue ID by one fixed, measurement-only classifier before D1 accuracy can be
scored at all — that classifier is not part of the system under test.

## Confidence

```
composite_score(c) = w_goal * goal_alignment_score
                    + w_risk * suitability_score
                    + w_obj  * financial_objective_score
                    + w_liq  * (liquidity_score if liquidity-relevant else 0)
# weights in configs/base.yaml: scoring_weights, sum to 1.0

margin = composite_score(top-ranked) - composite_score(second-ranked)
confidence = margin                    if >= 2 valid candidates
           = composite_score(top)      if exactly 1 valid candidate
           = n/a -> hard abstain       if 0 valid candidates
```

`MIN_CONFIDENCE` (default `0.60`, `configs/base.yaml`) is a soft abstention
threshold, independent of the hard triggers (no valid candidate, missing required
information, tool computation failure, no evidence available, unresolved tie,
unsupported scenario type).
