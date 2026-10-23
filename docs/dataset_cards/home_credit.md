# Dataset Card: Home Credit Default Risk

Status: **accepted for narrow external validation only** — not merged into
`data/synthetic/`, not used as a personalization ground truth, not used as
financial advice.

## Source

- Kaggle competition: `home-credit-default-risk`
  (<https://www.kaggle.com/competitions/home-credit-default-risk>)
- Downloaded via `kaggle competitions download -c home-credit-default-risk`
- Original archive: `home-credit-default-risk.zip`, 721,616,255 bytes,
  kept untouched at `C:\Users\shalu\Downloads\home-credit-default-risk.zip`
- Extracted (read-only copy) to `data/external/home_credit/` on 2026-10-19,
  2.50 GB uncompressed, 10 files — **gitignored**, never committed to this
  repository

## Licence

**Not verified.** An automated fetch of the competition's Rules page returned
no usable content (the page requires a logged-in Kaggle session / renders via
JavaScript, neither of which an automated fetch can get through). Kaggle
competition datasets commonly carry competition-specific usage terms rather
than an open licence (e.g. restrictions on redistribution or use outside the
competition) — **check the "Rules" tab on the competition page directly,
logged in, before any publication, redistribution, or use beyond local
research exploration.** Until that's confirmed, treat this dataset as
local-only and do not redistribute any part of it (including derived
statistics that could reconstruct rows) outside this machine.

## Structure (from direct inspection of the real files, 2026-10-19)

| File | Rows | Columns | Role |
|---|---:|---:|---|
| `application_train.csv` | 307,511 | 122 | Primary table, one row per loan application, has `TARGET` |
| `application_test.csv` | 48,744 | 121 | Same schema, no `TARGET` (competition holdout) |
| `bureau.csv` | 1,716,428 | 17 | Prior credit-bureau records per applicant |
| `bureau_balance.csv` | 27,299,925 | 3 | Monthly balance history per bureau record |
| `previous_application.csv` | 1,670,214 | 37 | Prior Home Credit applications per applicant |
| `POS_CASH_balance.csv` | 10,001,358 | 8 | Monthly POS/cash loan balance history |
| `credit_card_balance.csv` | 3,840,312 | 23 | Monthly credit-card balance history |
| `installments_payments.csv` | 13,605,401 | 8 | Installment payment history |
| `HomeCredit_columns_description.csv` | 219 | 5 | The dataset's own data dictionary |
| `sample_submission.csv` | 48,744 | 2 | Competition submission format, not research-relevant |

Unit of observation: one loan application (`SK_ID_CURR`). Six child tables
join on `SK_ID_CURR` / `SK_ID_PREV` / `SK_ID_BUREAU`.

**Target:** `TARGET` — binary, 0 = repaid without difficulty (282,686 rows),
1 = had payment difficulty (24,825 rows). No missing target values, no
duplicate `SK_ID_CURR` in the primary table.

**Known data-quality facts, from direct inspection:**
- 263,491 / 307,511 `application_train` rows have a matching `bureau.csv`
  record (join is not total).
- Heaviest missingness is entirely in building/apartment attributes
  (`COMMONAREA_*`, `LIVINGAPARTMENTS_*`, `FLOORSMIN_*`: 66–70% missing) — not
  in the income/credit fields most relevant to any validation use.
- No leakage audit has been run (that needs a modeling pass, not a desk
  audit) — treat as unchecked, not clean.

## What it can support

Narrow, out-of-sample sanity-checking of the debt-related hard constraints in
`src/decision/candidate_evaluator.py` (e.g. whether the synthetic benchmark's
debt-to-income and APR thresholds are wildly out of step with a real
population's income/credit-exposure distribution) — **`DEBT_PRIORITIZATION`
scenario type only.**

## What it cannot support — confirmed, not assumed

All 122 `application_train.csv` columns were searched for risk tolerance,
investment horizon, financial goals, liquidity, emergency fund, financial
literacy, or retirement concepts. The only substring hit was
`EMERGENCYSTATE_MODE` — its real description in
`HomeCredit_columns_description.csv` is about whether the applicant's
*apartment building* has an emergency-exit designation, a housing attribute,
**not a financial emergency fund**. There is no field in this dataset that
can stand in for any of the five user-profile dimensions the synthetic
benchmark's personalization claims depend on (goals, risk tolerance,
investment horizon, emergency-fund target, liquidity requirements).

## Preprocessing (proposed, not yet implemented — awaiting approval)

Not built yet. The intended scope, for approval before any code is written:
read-only extraction of income/credit/repayment-history features from
`application_train.csv` + `bureau.csv` only (the two tables relevant to debt
validation), computing summary distributions to compare against the
synthetic benchmark's debt-scenario population — never joining this data
into `data/synthetic/`, never training a model on `TARGET` for use inside
this project, never treating `TARGET` as a stand-in for the ground-truth
engine's `REPAY_LOAN`/`INVEST`/etc. decisions (a credit-default label is not
a personalized-advice label).

## Evaluation role

External validation signal for D1 (correctness) on the `DEBT_PRIORITIZATION`
scenario type only — a secondary, supporting check, not a primary dataset
and not a source of additional scenarios or ground truth.
