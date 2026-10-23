# Dataset Card — NCFE Financial Corpus (RAG Pilot Candidate Set)

## Status

**Candidate corpus under content review — not yet approved as the final RAG
corpus.** Originally 8 documents were downloaded and audited (round 1,
2026-10-20); a 9th, `debt_fl_loans.pdf`, was added in a follow-up
verification round (round 2, 2026-10-21) specifically to resolve the
unresolved DEBT_PRIORITIZATION source. Both rounds' findings are preserved
below, in order. This card records what was actually found by inspection,
not what was assumed when a candidate was first named. **No chunking,
indexing, embedding, or RAG code exists yet. No frozen dataset or
experiment configuration was touched.**

## Source

All 8 files come from NCFE's (National Centre for Financial Education)
public e-library at <https://ncfe.org.in/e-library/>. NCFE is jointly
promoted by RBI, SEBI, IRDAI, and PFRDA, but — as the content audit below
shows — not every document hosted on its e-library is itself NCFE-authored;
several are hosted student-competition submissions from individual schools.

Retrieved: 2026-10-20, via direct HTTPS download (`curl`), stored unmodified
under `data/external/financial_corpus/raw/` (gitignored, same as
`data/external/home_credit/`). Extracted text (via PyMuPDF, for inspection
only, not yet a RAG input) is under `data/external/financial_corpus/extracted_text/`.

## Per-document provenance and content audit

### 1. `budgeting_how_to_plan_your_budget.pdf` — candidate for BUDGETING

- **Source URL**: https://ncfe.org.in/wp-content/uploads/2024/02/how-to-plan-your-budget.pdf
- **Size / SHA-256**: 229,064 bytes / `6490815d58a3db747e7c1171a694e4001d68535d94a219c10ea778f58d925904`
- **Pages**: 7. **PDF metadata creation date**: 2015-01-20 (author field: "sandeep")
- **Publisher**: Not explicitly credited on the document itself. Carries NCFE's
  known tagline ("A financially aware and empowered India") on the last
  slide, suggesting an NCFE-produced piece, but no letterhead/address like
  document 4 below.
- **Extraction quality**: Good — all 7 short slides yielded genuine prose
  (~950-1,200 characters total).
- **Scenario relevance — confirmed by reading**: Genuine, generic 4-step
  monthly budgeting method (categorize essentials vs. extras, estimate
  monthly spend, track prior-month quantities, subtract essentials then
  extras from income to find savings).
- **Flags**: Very thin (under 1,000 words total). No India-specific figures,
  no dated claims, nothing scheme- or product-specific. Content is sound
  but shallow — a single retrieval chunk's worth of material at most.
- **Licence/reuse**: UNVERIFIED — no terms stated on the document or the
  e-library page.

### 2. `debt_credit_score.pdf` — candidate for DEBT_PRIORITIZATION

- **Source URL**: https://ncfe.org.in/wp-content/uploads/2023/12/Credit-Score.pdf
- **Size / SHA-256**: 1,002,974 bytes / `b1378517c77812ce991cc493da48ecb0f6362afe7e0dc5ca27b76937625a656e`
- **Pages**: 11. **Creation date**: 2022-12-19
- **Publisher — important finding**: NOT NCFE. The document's own
  acknowledgement page credits "Delhi Public School, Jaipur" (Patron,
  Director, Principal, HOD Commerce, PGT Economics all named) — this is a
  **school student-competition project**, hosted in NCFE's e-library, not
  an NCFE/RBI/SEBI-authored document.
- **Extraction quality**: Partial — 4,169 real characters recovered; the
  rest of the 1MB file is illustration/decoration without a text layer.
- **Scenario relevance — confirmed by reading**: Delivered as a fictional
  dialogue ("Anuj and Umar"). Content is factually unremarkable and
  generically correct: credit score range 300-900, factors (utilization
  <50%, on-time bill payment, dispute report errors, loan repayment
  history).
- **Flags**: **Authority concern** — pedagogical/competition content, not
  an institutional statement, despite being hosted on NCFE's official site.
  No alternative debt-focused document was found among the 8 downloaded;
  NCFE's own `fl-loans.pdf` (seen in the e-library listing but not
  downloaded) may be a better-sourced replacement — flagged as a follow-up
  option below, not yet fetched.
- **Licence/reuse**: UNVERIFIED.

### 3. `debt_types_of_loans_and_accounts.pdf` — candidate for DEBT_PRIORITIZATION

- **Source URL**: https://ncfe.org.in/wp-content/uploads/2023/12/Types-of-Loans-and-Accounts.pdf
- **Size / SHA-256**: 1,980,730 bytes / `386dc224dfe41b593d13a92151dcca1a5d61c9464c07d8ba8da9096b5a8b360d`
- **Pages**: 7. **Creation date**: 2022-11-30 (producer: "PDFCreator Free" —
  consistent with a scanned/image export)
- **Extraction quality**: **FAILED.** Only literal "Page No. 1" … "Page No.
  7" placeholder strings were recoverable (98 characters total across the
  whole document) — this is a pure image/infographic PDF with no real text
  layer.
- **Scenario relevance**: **Cannot be assessed.** I did not attempt OCR (no
  OCR tooling was part of this inspection, and guessing content from a
  filename would be inventing, not verifying).
- **Flags**: **Unusable in its current form** for a text-based RAG corpus.
- **Licence/reuse**: UNVERIFIED.

### 4. `emergency_savings.pdf` — candidate for EMERGENCY_FUND

- **Source URL**: https://ncfe.org.in/wp-content/uploads/2023/12/fl-savings.pdf
- **Size / SHA-256**: 1,837,452 bytes / `db5f857ddb5bec64cb81da9605bd89dbf1bd59e16c3466fa0a263c890a28a3da`
- **Pages**: 5. **Creation date**: 2017-01-13
- **Publisher — confirmed**: Genuinely NCFE. Carries full letterhead
  ("NATIONAL CENTRE FOR FINANCIAL EDUCATION", address "NISM Bhavan, Plot
  No. 82, Sector 17, Vashi, Navi Mumbai 400 703", email ncfe@nism.ac.in) on
  both the first and last page.
- **Extraction quality**: Good — 3,431 real characters across 5 pages.
- **Scenario relevance — explicitly verified, not assumed**: Page 3 carries
  a section literally titled **"Always have an 'Emergency Fund'"**:
  *"Savings are very helpful in addressing unexpected or unforeseen
  problems such as illness, accidents, unemployment, robbery, drought,
  funerals... Make sure that you keep money for emergencies. If you ever
  have to use part of your emergency fund, top it up again as soon as you
  can."* This directly answers the requested check: the document is not
  being labeled EMERGENCY_FUND merely because it discusses savings in
  general — it contains an explicit, named emergency-fund section.
- **Flags**: None significant. Generic, evergreen guidance; no scheme- or
  product-specific claims; no stale statistics.
- **Licence/reuse**: UNVERIFIED (no terms stated, despite the clear
  institutional authorship).

### 5. `investment_investor_guide.pdf` ("Making Mutual Funds Work For You") — candidate for INVESTMENT_ALLOCATION

- **Source URL**: https://ncfe.org.in/wp-content/uploads/2023/12/Investor-Guide.pdf
- **Size / SHA-256**: 3,180,989 bytes / `f1bdd3c364eb63d84888d64eba8d4c256821c64439da256cbf7c1164d441de0f`
- **Pages**: 20. **Creation date (metadata)**: 2008-07-07
- **Publisher — confirmed, most authoritative document in the set**:
  **AMFI (Association of Mutual Funds in India)** — the SEBI-recognized
  self-regulatory umbrella body for the Indian mutual fund industry.
  Signed preface by A. P. Kurian, Chairman, dated June 19, 2008, stating
  this is the **third edition** (first published April 1997, produced with
  Price Waterhouse / a USAID-funded project).
- **Extraction quality**: Excellent — 25,962 real characters, substantial
  genuine prose across nearly all 20 pages.
- **Scenario relevance — confirmed by reading**: Explains what a mutual
  fund is, fund structures (open/close-ended), scheme categories
  (growth/income/interval), and explicit suitability-by-life-stage guidance
  — e.g. growth schemes "Ideal for: Investors in their prime earning
  years," income schemes "Ideal for: Retired people... needing capital
  stability." This maps directly onto allocation-by-profile reasoning.
- **Flags**:
  - **Stale statistics** — AUM figures, scheme counts, and the asset-growth
    chart are as of March 2008 (18 years old as of this audit). The
    structural/conceptual content (what fund types exist, who they suit)
    appears durable; the numbers are not and must not be cited as current.
  - Explicitly self-limits its own authority: *"does not solicit investment
    in any specific Mutual Fund... is not a legal or regulatory document...
    consult your investment advisor before making an investment
    decision."* This is a point in its favor (non-promotional framing), not
    a concern.
  - SEBI mutual fund regulation references are as of 2008 and may be
    outdated.
- **Licence/reuse**: UNVERIFIED.

### 6. `investment_basics_of_mutual_funds.pdf` — candidate for INVESTMENT_ALLOCATION

- **Source URL**: https://ncfe.org.in/wp-content/uploads/2023/12/Basics-of-Mutual-Funds.pdf
- **Size / SHA-256**: 1,971,318 bytes / `eb7b17385d54d6d6871c5ff8372ec8026d2334f4badda5bcf8e04908dadd09c5`
- **Pages**: 15. **Creation date**: 2022-12-19
- **Publisher**: NOT NCFE — same "Delhi Public School, Jaipur" acknowledgement
  template and staff names as document 2.
- **Extraction quality**: Partial — 5,179 real characters of narrative dialogue.
- **Scenario relevance — confirmed by reading**: Fictional dialogue ("Varun
  and Raman") contrasting a conservative FD/PPF investor with an equity
  mutual fund investor, including specific comparative-return claims
  ("Equity Mutual Funds have created almost 3 times more wealth than FD...
  nearly 1.5 times more than Sensex and Gold" over "the last 5 years," i.e.
  roughly 2017-2022, stated without that date qualifier being prominent).
- **Flags**: Same authority concern as document 2 (school-competition
  project, not institutional content). Additionally, the comparative-return
  claim is a historical, point-in-time statistic presented with the same
  confidence as general advice — risk of being read as a timeless truth.
  **Redundant with document 5**, which covers the same ground (fund types,
  suitability) with institutional authority and without the dated
  performance claim.
- **Licence/reuse**: UNVERIFIED.

### 7. `retirement_atal_pension_yojna.pdf` — candidate for RETIREMENT

- **Source URL**: https://ncfe.org.in/wp-content/uploads/2023/12/Atal-Pension-Yojna.pdf
- **Size / SHA-256**: 1,902,388 bytes / `e931bdbc392cb6be3e70cc618ad49dddfa33b40ed0c7c584d7a19daf5f7698cd`
- **Pages**: 12. **Creation date**: 2022-12-19
- **Publisher**: NOT NCFE — "The Palace School" acknowledgement/narrative template.
- **Extraction quality**: Good — 2,062 real characters, genuine dialogue.
- **Scenario relevance — confirmed, and confirmed scheme-specific as
  suspected**: The entire content is about enrolling in the **Atal Pension
  Yojna (APY)** specifically — contribution tiers (Rs. 1,000/2,000/3,000/
  4,000/5,000 target monthly pension), enrollment at age 25, required
  documents. There is **no general retirement-planning methodology** in
  this document at all.
- **Flags**: Exactly the concern raised before downloading — this is
  **scheme-specific evidence about one government product**, not general
  retirement-planning guidance, and must not be used interchangeably with
  document 8. Also carries the school-project authority caveat.
- **Licence/reuse**: UNVERIFIED.

### 8. `retirement_retirement_planning.pdf` — candidate for RETIREMENT (primary)

- **Source URL**: https://ncfe.org.in/wp-content/uploads/2023/12/Retirement-Planning.pdf
- **Size / SHA-256**: 3,187,526 bytes / `68981665173cc306aa880ab684cab71eecb2fd3ec4db5436e78d79582976610b`
- **Pages**: 22. **Creation date**: 2022-12-19
- **Publisher**: "The Palace School" narrative template (same authority
  caveat as document 7), but the content itself is markedly more general.
- **Extraction quality**: Good — 4,498 real characters.
- **Scenario relevance — confirmed, and confirmed to be the stronger
  general candidate as expected**: Covers actual retirement-planning
  *methodology*: estimating a post-retirement corpus from current monthly
  expenses, applying an inflation adjustment (7% illustrative rate),
  accounting for life expectancy, and a fully worked numeric example
  (Rs. 35,000/month expense -> Rs. 84,00,000 unadjusted 20-year corpus ->
  Rs. 3.03 crore inflation-adjusted at 7% over 22 years), with a generic
  mention of PPF/NPS as example instruments (not scheme enrollment
  mechanics).
- **Flags**: The worked example's 7% inflation rate and specific ages are
  illustrative assumptions, not an official or current rate, and must be
  presented as a worked-example method, not an endorsed government figure.
  Same non-institutional authorship caveat as document 7.
- **Licence/reuse**: UNVERIFIED.

### 9. `debt_fl_loans.pdf` — candidate for DEBT_PRIORITIZATION (round 2, 2026-10-21)

- **Source URL**: https://ncfe.org.in/wp-content/uploads/2023/12/fl-loans.pdf
- **Retrieved**: 2026-10-21, same method as round 1 (direct HTTPS download,
  original stored unmodified in `raw/`, never edited).
- **Size / SHA-256**: 1,617,612 bytes / `4fa4922974c134faf36ebf1ac4b8e727303eb7a69b964f1ca1cde9bb99cb90c3`
- **Pages**: 6. **PDF metadata creation date**: 2017-01-12. Metadata
  `author` field: "National Centre for Financial Education" — but per your
  instruction, authorship is not accepted on metadata or hosting-location
  grounds alone; see body-text confirmation below.
- **Publisher — confirmed by in-body letterhead, not inferred from hosting**:
  Page 1 opens with "NATIONAL CENTRE FOR FINANCIAL EDUCATION / Financial
  Literacy / Loans / Fundamental messages in," and page 6 closes with the
  full institutional footer: "NATIONAL CENTRE FOR FINANCIAL EDUCATION,
  NISM Bhavan, Plot No. 82, Sector 17, Vashi, Navi Mumbai 400 703, Email:
  ncfe@nism.ac.in, Website: www.ncfeindia.org." This is the identical
  letterhead/footer template already confirmed genuine for document 4
  (`emergency_savings.pdf` / `fl-savings.pdf`) — same "Financial Literacy"
  series, same publisher, confirmed by reading the document itself, not by
  its URL.
- **Extraction quality**: Good — 5,121 real characters across 6 pages, all
  genuine prose (no OCR/placeholder artifacts).
- **Scenario relevance — confirmed by reading**: Directly supports
  responsible borrowing, repayment obligations, and debt-prioritization
  reasoning: loans always carry a cost (interest + fees, with a worked
  12%-interest example); shop around and compare total repayment cost
  before borrowing; plan repayment capacity in advance; prefer saving over
  borrowing, take a loan "only as a last resort"; collateral/security risk
  on default; and an explicit **"Don't dig a hole to fill up another
  hole"** warning against taking a new loan to cover existing debt — this
  maps directly onto the kind of trade-off `DEBT_PRIORITIZATION` scenarios
  pose (repay vs. take on more debt vs. split with savings). It also notes
  that RBI-regulated lenders record repayment history, which affects future
  loan terms — the same underlying concept `debt_credit_score.pdf`
  addressed, but stated by the institutional source rather than a school
  dialogue.
- **Flags**: None significant. No scheme-specific scoping (unlike the APY
  document), no stale statistics, no promotional framing — purely
  behavioral/conceptual guidance on borrowing and repayment.
- **Licence/reuse**: UNVERIFIED — no explicit licence or reuse terms found
  on the document or the e-library page, same as every other document in
  this corpus. Not claiming otherwise.

**Comparison against the existing debt candidates**: `debt_fl_loans.pdf`
is confirmed-institutional (letterhead in the body), evergreen (no dated
statistics or scheme scoping), and topically on-point for
`DEBT_PRIORITIZATION` specifically (the repay-vs-borrow-more trade-off).
`debt_credit_score.pdf` is a Delhi Public School, Jaipur student-competition
narrative (confirmed non-institutional) whose content, while not wrong, is
delivered as fiction rather than guidance. `debt_types_of_loans_and_accounts.pdf`
remains unusable (no extractable text). `fl-loans.pdf` is strictly stronger
than both on every axis checked: authorship, dating, scope, and extraction
quality.

**Recommendation: accept `debt_fl_loans.pdf` as the primary DEBT_PRIORITIZATION
source**, replacing `debt_credit_score.pdf`'s prior conditional/provisional
status. `fl-pension.pdf` was not inspected, per your instruction, since the
retirement slot (`retirement_retirement_planning.pdf`) was already judged
adequate.

## Proposed final corpus (smallest set that covers all 5 scenario types)

**Updated after round 2 (2026-10-21).** The DEBT_PRIORITIZATION slot is now
resolved in favor of `debt_fl_loans.pdf`.

| Scenario type | Proposed document | Status |
|---|---|---|
| BUDGETING | `budgeting_how_to_plan_your_budget.pdf` | Keep — only candidate, thin but genuine |
| DEBT_PRIORITIZATION | `debt_fl_loans.pdf` | **Resolved in round 2** — confirmed NCFE-authored (in-body letterhead), evergreen, directly on-topic for repay-vs-borrow-more reasoning |
| EMERGENCY_FUND | `emergency_savings.pdf` | Keep — strongest document in the set: genuinely NCFE-authored, explicit emergency-fund section confirmed |
| INVESTMENT_ALLOCATION | `investment_investor_guide.pdf` | Keep — most authoritative document in the set (AMFI); use structural content only, exclude the 2008 statistics |
| RETIREMENT | `retirement_retirement_planning.pdf` | Keep as primary, per your instruction — confirmed general methodology, not scheme-specific |

**Dropped from the final corpus:**
- `debt_credit_score.pdf` — superseded by `debt_fl_loans.pdf` (round 2):
  confirmed non-institutional (Delhi Public School, Jaipur competition
  entry) where `fl-loans.pdf` is confirmed institutional, and delivered as
  fiction rather than guidance.
- `debt_types_of_loans_and_accounts.pdf` — unusable, no extractable text.
- `investment_basics_of_mutual_funds.pdf` — redundant with the stronger,
  institutionally-authored `investment_investor_guide.pdf`, and carries an
  unflagged historical performance claim.
- `retirement_atal_pension_yojna.pdf` — demoted out of the *primary* corpus
  per your instruction, since inspection confirmed it is scheme-specific
  (APY mechanics only), not general retirement guidance. Kept on disk as a
  secondary, explicitly-scoped "APY scheme mechanics" document if a future
  scenario needs it — not wired into anything by default.

**Net result: 5 primary documents** (one per scenario type), all content-
verified by direct reading rather than assumed from filename, hosting
location, or metadata alone. All 5 slots now have a confirmed-institutional
source; no slot remains on a merely "conditional" or provisional document.
`fl-pension.pdf` was deliberately not inspected — the retirement slot was
already adequate, per your instruction to only check it if the retirement
document proved inadequate.

## Explicitly out of scope at this stage

No chunking, no BM25/embedding index, no RAG agent code, no change to any
`configs/*.yaml`, and no change to any frozen dataset or its checksums.
This card is a provenance and content record only, per your instruction to
present the audit and proposed final corpus for approval first.

## Retrieval index build (round 3, 2026-10-21)

A BM25-only retrieval index was built over exactly the 5 approved documents
(`budgeting_how_to_plan_your_budget`, `debt_fl_loans`, `emergency_savings`,
`investment_investor_guide`, `retirement_retirement_planning`) listed above
as "the proposed final corpus." This is a retrieval index only -- no
chunking/BM25 answer generation, embeddings, or RAG agent integration.

- **Code**: `src/retrieval/corpus.py` (PyMuPDF extraction + per-page
  chunking), `src/retrieval/bm25_index.py` (`BM25Okapi` wrapper),
  `experiments/build_retrieval_index.py` (build script).
- **Artifacts**: `data/external/financial_corpus/index/chunks.json` (60
  chunks, one per PDF page across the 5 documents) and
  `.../index/corpus_manifest.json` (source SHA-256 per document, extraction
  tool/version, chunking parameters, BM25 package/version/parameters).
  Gitignored, same as `raw/` and `extracted_text/`.
- **Dependencies added**: `pymupdf==1.27.2`, `rank-bm25==0.2.2` (both
  already installed and validated against this exact corpus during the
  content audit; pinned in `requirements.txt`).
- **Chunking**: one chunk per PDF page (`chunk_id = f"{doc_id}__p{page:03d}"`).
  Justified by the corpus's own structure: every page in these 5 documents
  is already a self-contained unit (checked -- the largest page is 1,941
  characters), so page boundaries don't split a warning or rule from its
  context. All 60 pages across the 5 documents produced a chunk; none was
  dropped by the (defensive, currently-inert) minimum-length filter.
- **Tokenization**: lowercase + `[a-z0-9]+` regex split, no stemming, no
  stopword removal -- shared identically by indexing and querying.
- **Measured retrieval-quality limitation** (found by the manually reviewed
  test set, not hidden from it): a natural-language budgeting query ranked
  its single best-matching page 4th instead of in the top 3, because the
  query's singular "essential"/"extra" don't token-match the source page's
  plural "Essentials"/"extras" -- a direct consequence of having no
  stemming. The correct *document* was still returned in all cases tested;
  see `tests/test_retrieval_bm25.py` for the full, documented query set and
  this specific finding.
- **Tests**: `tests/test_retrieval_corpus.py` (12 tests: extraction/chunking
  determinism, stable IDs, source/frozen-dataset preservation, failure
  handling) and `tests/test_retrieval_bm25.py` (14 tests: the 5-query manual
  relevance set above, provenance, ranking order, empty/invalid-input
  handling, tie-breaking). All pass; full project suite is 177 passed, 1
  skipped (the pre-existing opt-in Ollama smoke test).
