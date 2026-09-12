# Ground-Truth Scoring Reference

The complete, audited rule set behind `src/decision/`. This document exists so
every constant and formula in the deterministic ground-truth engine is
traceable without reading the source — produced by the Phase 5 scientific
audit (see `docs/reproducibility.md` for the audit's determinism results).

## Independence (audited)

The ground-truth engine reads only `data/synthetic/users.json` and
`data/synthetic/scenarios.json` and writes only `data/synthetic/ground_truth.json`
and `results/metrics/ground_truth_summary.json` — it never modifies its inputs.
It contains **no LLM call, no RAG/retrieval, no embeddings, no external API,
and no random-number generation** anywhere in `src/decision/`. Nothing in this
engine reads a copilot's generated explanation, confidence value, or candidate
set — it is a standalone oracle, built to evaluate those systems, not to
depend on them. Verified by grep audit and by the reproducibility tests in
`tests/test_ground_truth.py`.

## Benchmark-assumption disclaimer

Every numeric constant below (return rates, ratios, thresholds, weights) is a
**synthetic benchmark assumption** chosen for determinism and internal
consistency — none are sourced from real market data, and none are a claim of
correct or licensed financial advice. Changing a constant changes the
benchmark; it does not make the benchmark "more correct." This applies in
particular to `ASSUMED_ANNUAL_RETURN` (4% / 7% / 10% by risk tolerance) and
`RETIREMENT_TARGET_FALLBACK_MULTIPLE` (10× annual income) in the retirement
projection — both are explicitly labeled as such in `candidate_evaluator.py`.

## Shared pipeline (every scenario type)

1. **Structural pre-check** — if any field in `Scenario.required_information`
   is absent from `Scenario.relevant_user_attributes`, abstain immediately
   with `MISSING_REQUIRED_INFORMATION`. No value is ever invented to fill a
   gap.
2. **Priority 1 — hard constraints.** Each candidate is checked against its
   scenario type's rules (below). A violation is final: a candidate that
   fails any hard constraint is removed before ranking and can never win,
   regardless of its soft scores (`src/decision/ranking.py::rank`).
3. **Priority 2–5 — soft ranking**, applied only to candidates that passed
   step 2, as a single lexicographic sort key:
   `(-goal_alignment, suitability_assessment, -financial_objective_score, -liquidity_score)`
   — i.e. maximize goal alignment, then minimize suitability risk, then
   maximize the financial objective, then maximize liquidity preservation.
4. **Priority 6 — tie-break.** Fixed catalogue order (`catalogue_order`),
   ascending. Since catalogue order is a strict total order over a
   duplicate-free list, this always produces a winner among tied candidates —
   `UNRESOLVED_TIE` is defined in `AbstentionReason` but structurally
   unreachable in this implementation (documented, not hidden).
5. **Abstention** — `ABSTAIN` when: no candidate survives step 2
   (`NO_VALID_CANDIDATE`), required information is missing (step 1,
   `MISSING_REQUIRED_INFORMATION`), or two reserved-but-unreachable cases kept
   for schema completeness (`UNSUPPORTED_SCENARIO`, `TOOL_REQUIRED` — see
   `ranking.py` and `ground_truth.py` for exactly why each is unreachable
   today). Abstention is never forced when a valid candidate exists, and never
   suppressed when none does — both directions are covered by
   `tests/test_ground_truth.py`.

All four soft components are always in `[0,1]` by construction (every formula
is wrapped in `_clip01`).

## BUDGETING

| Candidate | Hard constraint |
|---|---|
| `INCREASE_SAVINGS` | `B_HC1`: net cash flow > 0 |
| `MAINTAIN_CURRENT_SAVINGS` | `B_HC2`: net cash flow ≥ 0 |
| `REDUCE_EXPENSES_FIRST` | none (universal fallback) |

`net_cash_flow = income − expenses`, `savings_rate = net_cash_flow / income`,
`expense_ratio = expenses / income`, `coverage = emergency_fund_months / emergency_fund_target_months`
(both derived from the user's own `savings`, `monthly_expenses`, and
`emergency_fund_target`).

- **Goal alignment** — `INCREASE_SAVINGS`: `savings_rate / HEALTHY_SAVINGS_RATE(0.20)`.
  `MAINTAIN_CURRENT_SAVINGS`: `1 − |savings_rate − 0.20| / 0.20` (best exactly at the 20% benchmark).
  `REDUCE_EXPENSES_FIRST`: `(expense_ratio − 0.70) / 0.30` (rises from ratio 0.70 to 1.00).
- **Suitability** — all three scale with `1 − coverage` (the user's own EF
  shortfall), weighted by how much each action helps or ignores that gap:
  ×0.5 for `INCREASE_SAVINGS`, ×1.0 for `MAINTAIN_CURRENT_SAVINGS`, ×0.3 for
  `REDUCE_EXPENSES_FIRST` (the most protective option).
- **Financial objective** — `INCREASE_SAVINGS`: surplus normalized against
  `MAX_PLAUSIBLE_SAVINGS_RATE (0.30)` of income. `MAINTAIN_CURRENT_SAVINGS`:
  0.3× the savings-rate score (partial credit for "no change"). `REDUCE_EXPENSES_FIRST`:
  `expense_ratio − 0.5`.
- **Liquidity** — fixed, documented relative ranking: 0.6 / 0.5 / 0.8.

## DEBT_PRIORITIZATION

| Candidate | Hard constraint |
|---|---|
| `REPAY_LOAN` | `D_HC1`: has a loan, and savings > `MIN_ACTIONABLE_AMOUNT (₹1000)` |
| `INVEST` | `D_HC3`: savings > `MIN_ACTIONABLE_AMOUNT` |
| `SPLIT_DEBT_AND_INVESTMENT` | `D_HC2`: has a loan, and savings > `MIN_ACTIONABLE_AMOUNT` |
| `BUILD_EMERGENCY_FUND_FIRST` | `D_HC4`: net cash flow > 0, or savings > `MIN_ACTIONABLE_AMOUNT` |

A user with no loan, negligible savings, and non-positive cash flow fails all
four — the honest answer is `ABSTAIN` (`NO_VALID_CANDIDATE`); this is the one
scenario type that reaches that reason on the real dataset (25/1000 debt
scenarios).

- **Goal alignment / financial objective** — both driven by `max_apr / HIGH_APR_CEILING (0.25)`:
  higher for `REPAY_LOAN` (repaying a high-APR loan is urgent), inverted for
  `INVEST` (low APR makes investing more attractive), flat 0.5 for the
  compromise `SPLIT_DEBT_AND_INVESTMENT`, and the user's own EF gap for
  `BUILD_EMERGENCY_FUND_FIRST`.
- **Suitability** — `REPAY_LOAN`: `(1 − max_apr/0.25) × 0.4` (repaying is
  rarely risky; the dampened weight reflects opportunity-cost as a secondary
  concern). `INVEST`: EF gap plus half-weight for leaving a high-APR loan
  unpaid. `SPLIT`: half-weight EF gap plus quarter-weight unpaid-debt risk.
  `BUILD_EMERGENCY_FUND_FIRST`: `(1 − ef_gap) × 0.3` (the safest lever).
- **Liquidity** — fixed relative ranking: `REPAY_LOAN` computed from how much
  of savings the repayment consumes; `INVEST` 0.4; `SPLIT` 0.5; `BUILD_EMERGENCY_FUND_FIRST` 0.9.

## EMERGENCY_FUND

| Candidate | Hard constraint |
|---|---|
| `BUILD_TO_3_MONTHS` | `E_HC1`: current coverage < 3 months |
| `BUILD_TO_6_MONTHS` | `E_HC2`: current coverage < 6 months |
| `BUILD_TO_9_MONTHS` | `E_HC3`: current coverage < 9 months |
| `MAINTAIN_CURRENT` | `E_HC4`: current coverage ≥ 3 months |

These four conditions jointly cover every possible coverage value, so this
scenario type always has at least one valid candidate by construction — it
never abstains via `NO_VALID_CANDIDATE` on real data (only the shared
`MISSING_REQUIRED_INFORMATION` pre-check could abstain it, and that's
unreached on real data since Phase 3 profiles are always fully populated).

- **Goal alignment** — `1 − |candidate_target − user's own emergency_fund_target_months| / EMERGENCY_FUND_MAX_TARGET_MONTHS (9)`,
  grounded in the user's own stated target, never an external benchmark.
- **Suitability vs. financial objective** — deliberately complementary
  (`1 − target/9` and `target/9` respectively): a lower target is less
  protective (higher risk) but frees more capital (higher "efficiency")
  — a real, documented risk/efficiency tradeoff, not duplicated code.
- **Liquidity** — current savings as a fraction of what the candidate's
  target would require in currency terms.

## INVESTMENT_ALLOCATION

| Candidate | Hard constraint |
|---|---|
| `AGGRESSIVE` | `I_HC1`: risk_tolerance == HIGH and horizon ≥ 10 |
| `GROWTH` | `I_HC2`: risk_tolerance ∈ {MODERATE, HIGH} and horizon ≥ 5 |
| `BALANCED` | `I_HC3`: horizon ≥ 3 |
| `MODERATE`, `CONSERVATIVE` | none (universal fallbacks) |

Each candidate maps to a nominal `EQUITY_PCT` (0.2/0.4/0.6/0.8/1.0, scoring
device only — no portfolio is constructed). `ideal_equity = risk_base(risk_tolerance) + horizon_adj + literacy_adj`,
clipped to [0,1]:

- `risk_base` = 0.15 / 0.45 / 0.75 for LOW / MODERATE / HIGH, centered so
  every `EQUITY_PCT` bucket is the closest match for *some* input combination.
- `horizon_adj = clip01(horizon/30) × 0.3`.
- `literacy_adj` = −0.07 / 0 / +0.07 for LOW / MEDIUM / HIGH financial
  literacy — **added by the Phase 5 audit**; see "Investment-distribution
  finding" below for why.

**Goal alignment** = `1 − |equity_pct − ideal_equity|`. **Suitability** =
`equity_pct × liquidity_ratio` (liquidity_requirements / savings — more
near-term liquidity need makes equity exposure riskier). **Financial
objective** = `equity_pct × clip01(horizon / GROWTH_REALIZATION_HORIZON_YEARS (20))`.
**Liquidity** = `1 − equity_pct × 0.5` (a relative-preservation score; even
100% equity retains a documented floor of 0.5, it is not an absolute
liquidity measure).

### Investment-distribution finding (Phase 5 audit)

Before the audit, `MODERATE` and `GROWTH` were selected in only 2 and 3 of
5000 scenarios. Diagnosis (see cross-tabs referenced in
`candidate_evaluator.py`): `risk_tolerance` and `investment_horizon_years` are
strongly correlated *by construction* in Phase 3 (the risk-tolerance formula
is itself 50% driven by horizon) — verified exactly: **0/360** HIGH-risk users
have horizon <15, **0/265** LOW-risk users have horizon ≥15, and **1/375**
MODERATE-risk users have horizon <5. The (risk_tolerance, horizon)
combinations `MODERATE` and `GROWTH`'s target zones depend on are not merely
rare — they are essentially absent from the population's support, so no
reweighting of the horizon term alone could fix it. `financial_literacy` is
the one User field Phase 3 generates independently of risk_tolerance and
horizon (verified: a roughly even 3-way split within every risk_tolerance
level) and is a standard, independent suitability dimension in real investor
questionnaires (investor sophistication) — so it was added as a small
(±0.07, at most a third of a bucket-width), clearly subordinate, documented
secondary adjustment. After the fix: `MODERATE` = 39, `GROWTH` = 31 (of 5000)
— all five candidates are now reachable via realistic, non-edge-case users,
without forcing uniformity (the distribution still reflects the population's
real skew toward "typical" risk/horizon pairings).

## RETIREMENT

| Candidate | Hard constraint |
|---|---|
| `ON_TRACK` | `R_HC1`: projected value ≥ target (can't claim on-track if the math says short) |
| `INCREASE_RETIREMENT_SAVING` | `R_HC2`: net cash flow > 0 |
| `EXTEND_RETIREMENT_HORIZON` | `R_HC3`: age < 65 |
| `REDUCE_RETIREMENT_SPENDING_TARGET` | none (universal fallback) |

`projected = savings × (1+r)^n + annual_contribution × [((1+r)^n − 1) / r]`
(a standard future-value-of-annuity formula), where `r = ASSUMED_ANNUAL_RETURN[risk_tolerance]`
(**synthetic benchmark, see disclaimer above**) and `n = investment_horizon_years`.
`target` = the user's own `RETIREMENT`-type goal amount if one exists, else
`RETIREMENT_TARGET_FALLBACK_MULTIPLE (10) × annual income` (**synthetic
benchmark fallback, see disclaimer above** — only used when the profile has no
explicit goal). `gap = max(1 − projected/target, 0)`.

- **Goal alignment** — `ON_TRACK`: the ratio itself. The other three all use
  `gap` (they're equally "aligned" with addressing a real shortfall;
  suitability and objective differentiate them).
- **Suitability** — `ON_TRACK`: 0 (no action, no new risk). `INCREASE_RETIREMENT_SAVING`:
  risk of squeezing an already-tight cash flow, normalized against
  `MAX_PLAUSIBLE_SAVINGS_RATE (0.30)` of income. `REDUCE_RETIREMENT_SPENDING_TARGET`:
  flat 0.2 (a "soft" lever, adjusting an aspiration carries little real risk).
  `EXTEND_RETIREMENT_HORIZON`: `(age − RETIREMENT_AGE_RISK_FLOOR(40)) / RETIREMENT_AGE_RISK_SPAN(30)`
  — reaches maximum risk at age 70, zero below 40.
- **Financial objective** — `ON_TRACK`: `ratio/2` (just-on-track scores 0.5,
  not 1.0, leaving room for genuine surplus to score higher).
  `INCREASE_RETIREMENT_SAVING`: how much of the target gap the extra
  contribution capacity could close over the horizon. `REDUCE_RETIREMENT_SPENDING_TARGET`:
  the gap itself (it closes the gap by definition), or 0.3 baseline when
  already on track. `EXTEND_RETIREMENT_HORIZON`: `RETIREMENT_HORIZON_EXTENSION_YEARS (5) / horizon`
  — a rough "extra years of compounding" proxy, more impactful for shorter horizons.
- **Liquidity** — `ON_TRACK`, `REDUCE_RETIREMENT_SPENDING_TARGET`, `EXTEND_RETIREMENT_HORIZON`:
  1.0 (no liquidity impact). `INCREASE_RETIREMENT_SAVING`: 0.7 (redirects
  future cash flow, not existing savings — a moderate, documented impact).

## Full constants reference

| Constant | Value | Meaning |
|---|---|---|
| `HEALTHY_SAVINGS_RATE` | 0.20 | Benchmark "healthy" savings rate |
| `MIN_ACTIONABLE_AMOUNT` | ₹1000 | Floor below which a lump sum isn't meaningfully actionable |
| `MAX_PLAUSIBLE_SAVINGS_RATE` | 0.30 | Ceiling used to normalize savings-capacity scores |
| `HIGH_APR_CEILING` | 0.25 | Ceiling used to normalize "how urgent is this debt" scores |
| `EXPENSE_RATIO_CONCERN_THRESHOLD` / `_SPAN` | 0.70 / 0.30 | Where REDUCE_EXPENSES_FIRST starts/reaches full alignment |
| `EMERGENCY_FUND_MAX_TARGET_MONTHS` | 9 | Normalizer = largest BUILD_TO_X target in the catalogue |
| `GROWTH_REALIZATION_HORIZON_YEARS` | 20 | Horizon at which an allocation's growth objective is "fully realized" |
| `RETIREMENT_AGE_RISK_FLOOR` / `_SPAN` | 40 / 30 | Age range over which extending horizon's risk rises 0→1 |
| `RETIREMENT_HORIZON_EXTENSION_YEARS` | 5 | Assumed plausible extra working years |
| `ASSUMED_ANNUAL_RETURN` | 4% / 7% / 10% | **Synthetic benchmark**, by risk tolerance |
| `RETIREMENT_TARGET_FALLBACK_MULTIPLE` | 10× | **Synthetic benchmark** fallback target (annual income multiple) |
| `LITERACY_EQUITY_ADJUSTMENT` | ±0.07 | Independent secondary suitability adjustment (audit fix, see above) |

Every constant lives in `src/decision/candidate_evaluator.py`, module level,
with an inline comment — nothing is hard-coded inline without a name and a
rationale.
