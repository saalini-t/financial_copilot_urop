"""Deterministic per-candidate scoring.

Every function here is pure arithmetic over `User` fields already present in
the synthetic profile (see docs/data_dictionary.md) -- nothing is looked up
externally, nothing is randomized, nothing is invented. Each scenario type
defines four independent, separately-reported components (never blended into
one opaque number):

- hard_constraint_violations : list[str]   -- rule IDs; non-empty means infeasible
- goal_alignment             : float [0,1] -- higher is better, maximized (Priority 2)
- suitability_assessment     : float [0,1] -- LOWER is better, minimized (Priority 3)
- financial_objective_score  : float [0,1] -- higher is better, maximized (Priority 4)
- liquidity_score            : float [0,1] -- higher is better, maximized (Priority 5)

All formulas below are simplified, explicitly documented heuristics chosen for
determinism and auditability -- they are a benchmarking device, not validated
financial advice. Documented assumption constants live at module level so they
are visible in one place.
"""

from dataclasses import dataclass, field

from src.decision.candidate_catalogue import substantive_candidates
from src.models.scenario import ScenarioType
from src.models.user import FinancialLiteracy, GoalType, RiskTolerance, User

# --- documented assumption constants -----------------------------------------

HEALTHY_SAVINGS_RATE = 0.20  # synthetic-benchmark rule-of-thumb, not financial advice
MIN_ACTIONABLE_AMOUNT = 1000.0  # INR floor below which a lump sum isn't meaningfully actionable
MAX_PLAUSIBLE_SAVINGS_RATE = 0.30  # share of income treated as the ceiling when normalizing a savings-capacity score to [0,1]
HIGH_APR_CEILING = 0.25  # APR treated as the ceiling when normalizing "how urgent is this debt" to [0,1]
EXPENSE_RATIO_CONCERN_THRESHOLD = 0.70  # expense/income ratio above which REDUCE_EXPENSES_FIRST starts to align
EXPENSE_RATIO_CONCERN_SPAN = 0.30  # ratio span from the threshold to full alignment at ratio 1.00
EMERGENCY_FUND_MAX_TARGET_MONTHS = 9.0  # largest BUILD_TO_X_MONTHS target in the catalogue; normalizes EF scores to [0,1]
GROWTH_REALIZATION_HORIZON_YEARS = 20.0  # horizon at which an allocation's growth objective is treated as fully realized
RETIREMENT_AGE_RISK_FLOOR = 40  # age below which extending the retirement horizon carries ~0 extra suitability risk
RETIREMENT_AGE_RISK_SPAN = 30  # age span over which that risk rises from 0 to 1 (reaches 1.0 at age 70)
RETIREMENT_HORIZON_EXTENSION_YEARS = 5.0  # assumed number of extra working years a user could plausibly add

# SYNTHETIC BENCHMARK ASSUMPTION, not financial advice and not sourced from any
# real market data: a fixed nominal, pre-inflation annual return used only to
# make the retirement future-value projection below deterministic and
# reproducible. Changing these values changes the benchmark, not "the truth".
ASSUMED_ANNUAL_RETURN = {
    RiskTolerance.LOW: 0.04,
    RiskTolerance.MODERATE: 0.07,
    RiskTolerance.HIGH: 0.10,
}
# SYNTHETIC BENCHMARK ASSUMPTION: when a user's profile has no explicit
# RETIREMENT goal, a target of 10x annual income stands in for one. This is a
# common personal-finance rule of thumb, used here purely so every user has a
# deterministic target -- it is not a recommendation and not derived from any
# external source.
RETIREMENT_TARGET_FALLBACK_MULTIPLE = 10
EQUITY_PCT = {  # nominal equity weight per allocation candidate, for scoring only
    "CONSERVATIVE": 0.2,
    "MODERATE": 0.4,
    "BALANCED": 0.6,
    "GROWTH": 0.8,
    "AGGRESSIVE": 1.0,
}
# Phase 5 audit finding: risk_tolerance and investment_horizon_years are
# strongly correlated by construction in the synthetic population (Phase 3's
# risk-tolerance formula is itself 50% driven by horizon), to the point that
# the (risk_tolerance, horizon) cells MODERATE/GROWTH's "ideal equity" zones
# depend on are near-empty (verified: 0/360 HIGH-risk users have horizon <15,
# 0/265 LOW-risk users have horizon >=15, 1/375 MODERATE-risk users have
# horizon <5). Horizon alone therefore cannot provide real within-band spread.
# financial_literacy is sampled independently of every other field in Phase 3
# (verified: roughly even 3-way split within each risk_tolerance level) and is
# a standard, independent suitability dimension in real investor
# questionnaires (investor sophistication), so it is used as a small secondary
# adjustment -- documented, and deliberately kept subordinate to risk_tolerance
# (half a bucket-width at most) rather than a rebalancing hack.
LITERACY_EQUITY_ADJUSTMENT = {
    FinancialLiteracy.LOW: -0.07,
    FinancialLiteracy.MEDIUM: 0.0,
    FinancialLiteracy.HIGH: 0.07,
}


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


# --- shared derived metrics ----------------------------------------------------

def net_cash_flow(user: User) -> float:
    return user.monthly_income - user.monthly_expenses


def savings_rate(user: User) -> float:
    return net_cash_flow(user) / user.monthly_income if user.monthly_income else 0.0


def expense_ratio(user: User) -> float:
    return user.monthly_expenses / user.monthly_income if user.monthly_income else 0.0


def emergency_fund_months(user: User) -> float:
    return user.savings / user.monthly_expenses if user.monthly_expenses > 0 else float("inf")


def emergency_fund_target_months(user: User) -> float:
    return user.emergency_fund_target / user.monthly_expenses if user.monthly_expenses > 0 else 3.0


def total_loan_balance(user: User) -> float:
    return sum(loan.balance for loan in user.loans)


def has_loans(user: User) -> bool:
    return len(user.loans) > 0


def retirement_goal_target(user: User) -> float:
    goal = next((g for g in user.financial_goals if g.goal_type == GoalType.RETIREMENT), None)
    if goal is not None:
        return goal.target_amount
    return user.monthly_income * 12 * RETIREMENT_TARGET_FALLBACK_MULTIPLE


def projected_retirement_value(user: User) -> float:
    """A simple deterministic future-value projection: current savings compounded,
    plus the future value of an annuity of positive net cash flow, both over the
    user's stated investment horizon at a return assumed from risk tolerance."""
    r = ASSUMED_ANNUAL_RETURN[user.risk_tolerance]
    n = user.investment_horizon_years
    annual_contribution = max(net_cash_flow(user), 0.0) * 12
    fv_principal = user.savings * (1 + r) ** n
    fv_contributions = annual_contribution * (((1 + r) ** n - 1) / r if r > 0 else n)
    return fv_principal + fv_contributions


@dataclass
class CandidateScore:
    candidate_id: str
    hard_constraint_violations: list[str] = field(default_factory=list)
    goal_alignment: float = 0.0
    suitability_assessment: float = 0.0
    financial_objective_score: float = 0.0
    liquidity_score: float = 0.0

    @property
    def feasible(self) -> bool:
        return not self.hard_constraint_violations


# --- BUDGETING ------------------------------------------------------------------
# Hard constraints:
#   B_HC1  INCREASE_SAVINGS requires net_cash_flow > 0
#   B_HC2  MAINTAIN_CURRENT_SAVINGS requires net_cash_flow >= 0
#   REDUCE_EXPENSES_FIRST has no hard constraint (always feasible fallback)

def _score_budgeting(user: User) -> dict[str, CandidateScore]:
    ncf = net_cash_flow(user)
    rate = savings_rate(user)
    ratio = expense_ratio(user)
    ef_months = emergency_fund_months(user)
    ef_target = emergency_fund_target_months(user)
    coverage = _clip01(ef_months / ef_target) if ef_target > 0 else 1.0

    scores: dict[str, CandidateScore] = {}

    violations = [] if ncf > 0 else ["B_HC1"]
    scores["INCREASE_SAVINGS"] = CandidateScore(
        "INCREASE_SAVINGS",
        violations,
        goal_alignment=_clip01(rate / HEALTHY_SAVINGS_RATE),
        # weight 0.5: an EF coverage gap makes committing to MORE savings only
        # moderately riskier -- the new savings could itself feed the EF
        suitability_assessment=_clip01(1 - coverage) * 0.5,
        financial_objective_score=_clip01(ncf / (MAX_PLAUSIBLE_SAVINGS_RATE * user.monthly_income))
        if user.monthly_income
        else 0.0,
        liquidity_score=0.6,  # flat: a fixed, documented relative ranking across the 3 budgeting candidates
    )

    violations = [] if ncf >= 0 else ["B_HC2"]
    scores["MAINTAIN_CURRENT_SAVINGS"] = CandidateScore(
        "MAINTAIN_CURRENT_SAVINGS",
        violations,
        goal_alignment=_clip01(1 - abs(rate - HEALTHY_SAVINGS_RATE) / HEALTHY_SAVINGS_RATE),
        suitability_assessment=_clip01(1 - coverage),  # full weight: staying put doesn't help close an EF gap
        # weight 0.3: "no change" earns only partial objective credit even when already healthy
        financial_objective_score=0.3 * _clip01(rate / HEALTHY_SAVINGS_RATE),
        liquidity_score=0.5,  # flat: a fixed, documented relative ranking across the 3 budgeting candidates
    )

    scores["REDUCE_EXPENSES_FIRST"] = CandidateScore(
        "REDUCE_EXPENSES_FIRST",
        [],
        goal_alignment=_clip01((ratio - EXPENSE_RATIO_CONCERN_THRESHOLD) / EXPENSE_RATIO_CONCERN_SPAN),
        # weight 0.3: the most protective option, so an EF gap barely reduces its suitability
        suitability_assessment=_clip01(1 - coverage) * 0.3,
        financial_objective_score=_clip01(ratio - 0.5),  # 0.5: expenses above half of income start counting
        liquidity_score=0.8,  # flat: a fixed, documented relative ranking across the 3 budgeting candidates
    )
    return scores


# --- DEBT_PRIORITIZATION ---------------------------------------------------------
# Hard constraints:
#   D_HC1  REPAY_LOAN requires has_loans and savings > MIN_ACTIONABLE_AMOUNT
#   D_HC2  SPLIT_DEBT_AND_INVESTMENT requires has_loans and savings > MIN_ACTIONABLE_AMOUNT
#   D_HC3  INVEST requires savings > MIN_ACTIONABLE_AMOUNT
#   D_HC4  BUILD_EMERGENCY_FUND_FIRST requires net_cash_flow > 0 or savings > MIN_ACTIONABLE_AMOUNT
# A user with no loans, negligible savings, and non-positive cash flow fails all
# four -- the honest answer is that this scenario doesn't apply to them (ABSTAIN).

def _score_debt(user: User) -> dict[str, CandidateScore]:
    ncf = net_cash_flow(user)
    loans_exist = has_loans(user)
    savings = user.savings
    actionable = savings > MIN_ACTIONABLE_AMOUNT
    max_apr = max((loan.interest_rate for loan in user.loans), default=0.0)
    ef_months = emergency_fund_months(user)
    ef_target = emergency_fund_target_months(user)
    ef_gap = _clip01(1 - ef_months / ef_target) if ef_target > 0 else 0.0

    scores: dict[str, CandidateScore] = {}

    violations = []
    if not loans_exist:
        violations.append("D_HC1_NO_LOANS")
    if not actionable:
        violations.append("D_HC1_INSUFFICIENT_SAVINGS")
    scores["REPAY_LOAN"] = CandidateScore(
        "REPAY_LOAN",
        violations,
        goal_alignment=_clip01(max_apr / HIGH_APR_CEILING),
        # weight 0.4: a high-APR loan makes repaying it LESS risky, not more --
        # dampened because "risk" here means opportunity cost, a secondary concern
        suitability_assessment=_clip01(1 - max_apr / HIGH_APR_CEILING) * 0.4,
        financial_objective_score=_clip01(max_apr / HIGH_APR_CEILING),
        liquidity_score=_clip01(1 - min(savings, total_loan_balance(user)) / savings) if savings > 0 else 0.0,
    )

    violations = [] if actionable else ["D_HC3_INSUFFICIENT_SAVINGS"]
    scores["INVEST"] = CandidateScore(
        "INVEST",
        violations,
        goal_alignment=_clip01(1 - max_apr / HIGH_APR_CEILING),
        # blend: EF gap (full weight) plus half-weight for "a high-APR loan left
        # unpaid while investing" -- both raise this candidate's risk
        suitability_assessment=_clip01(ef_gap + max_apr / HIGH_APR_CEILING * 0.5),
        financial_objective_score=_clip01(1 - max_apr / HIGH_APR_CEILING),
        liquidity_score=0.4,  # flat: a fixed, documented relative ranking across the 4 debt candidates
    )

    violations = []
    if not loans_exist:
        violations.append("D_HC2_NO_LOANS")
    if not actionable:
        violations.append("D_HC2_INSUFFICIENT_SAVINGS")
    scores["SPLIT_DEBT_AND_INVESTMENT"] = CandidateScore(
        "SPLIT_DEBT_AND_INVESTMENT",
        violations,
        goal_alignment=0.5,  # a compromise candidate: neither best- nor worst-aligned by definition
        # blend: half-weight EF gap, quarter-weight unpaid-high-APR-debt risk
        suitability_assessment=_clip01(ef_gap * 0.5 + (1 - max_apr / HIGH_APR_CEILING) * 0.25),
        financial_objective_score=0.5,
        liquidity_score=0.5,  # flat: a fixed, documented relative ranking across the 4 debt candidates
    )

    violations = [] if (ncf > 0 or actionable) else ["D_HC4_NO_CAPACITY"]
    scores["BUILD_EMERGENCY_FUND_FIRST"] = CandidateScore(
        "BUILD_EMERGENCY_FUND_FIRST",
        violations,
        goal_alignment=ef_gap,
        # weight 0.3: closing the EF gap is the safest lever available, so even a
        # large remaining gap only mildly raises this candidate's own risk
        suitability_assessment=_clip01(1 - ef_gap) * 0.3,
        financial_objective_score=ef_gap,
        liquidity_score=0.9,  # flat: a fixed, documented relative ranking across the 4 debt candidates
    )
    return scores


# --- EMERGENCY_FUND ---------------------------------------------------------------
# Hard constraints (each BUILD_TO_X only makes sense while coverage is still short
# of it; MAINTAIN_CURRENT only makes sense once a minimal 3-month floor is met):
#   E_HC1  BUILD_TO_3_MONTHS requires ef_months < 3
#   E_HC2  BUILD_TO_6_MONTHS requires ef_months < 6
#   E_HC3  BUILD_TO_9_MONTHS requires ef_months < 9
#   E_HC4  MAINTAIN_CURRENT requires ef_months >= 3
# These four conditions jointly cover every possible ef_months value, so this
# scenario type always has at least one valid candidate by construction.

_EF_TARGETS = {"BUILD_TO_3_MONTHS": 3.0, "BUILD_TO_6_MONTHS": 6.0, "BUILD_TO_9_MONTHS": 9.0}


def _score_emergency_fund(user: User) -> dict[str, CandidateScore]:
    ef_months = emergency_fund_months(user)
    user_target_months = emergency_fund_target_months(user)
    scores: dict[str, CandidateScore] = {}

    for candidate_id, threshold in _EF_TARGETS.items():
        violations = [] if ef_months < threshold else [f"E_HC_{candidate_id}_ALREADY_MET"]
        scores[candidate_id] = CandidateScore(
            candidate_id,
            violations,
            goal_alignment=_clip01(1 - abs(threshold - user_target_months) / EMERGENCY_FUND_MAX_TARGET_MONTHS),
            # lower target = lower protection = higher risk, hence "1 - threshold/max"
            suitability_assessment=_clip01(1 - threshold / EMERGENCY_FUND_MAX_TARGET_MONTHS),
            # the complementary "capital efficiency" framing of the same ratio --
            # a lower target frees more cash for other goals (see module docstring
            # in ground_truth_scoring docs for the risk/efficiency tradeoff note)
            financial_objective_score=_clip01(1 - threshold / EMERGENCY_FUND_MAX_TARGET_MONTHS),
            liquidity_score=_clip01(user.savings / (threshold * user.monthly_expenses))
            if user.monthly_expenses > 0
            else 1.0,
        )

    violations = [] if ef_months >= 3 else ["E_HC4_BELOW_FLOOR"]
    scores["MAINTAIN_CURRENT"] = CandidateScore(
        "MAINTAIN_CURRENT",
        violations,
        goal_alignment=_clip01(1 - abs(ef_months - user_target_months) / EMERGENCY_FUND_MAX_TARGET_MONTHS),
        suitability_assessment=_clip01(1 - min(ef_months, EMERGENCY_FUND_MAX_TARGET_MONTHS) / EMERGENCY_FUND_MAX_TARGET_MONTHS),
        financial_objective_score=_clip01(min(ef_months, EMERGENCY_FUND_MAX_TARGET_MONTHS) / EMERGENCY_FUND_MAX_TARGET_MONTHS),
        liquidity_score=_clip01(ef_months / user_target_months) if user_target_months > 0 else 1.0,
    )
    return scores


# --- INVESTMENT_ALLOCATION ---------------------------------------------------------
# Hard constraints (a suitability gate -- don't offer a higher-risk allocation than
# the user's stated risk tolerance and horizon support):
#   I_HC1  AGGRESSIVE requires risk_tolerance == HIGH and horizon >= 10
#   I_HC2  GROWTH requires risk_tolerance in {MODERATE, HIGH} and horizon >= 5
#   I_HC3  BALANCED requires horizon >= 3
#   MODERATE and CONSERVATIVE have no hard constraint (always appropriate defaults)

def _score_investment(user: User) -> dict[str, CandidateScore]:
    # risk_base is centered so every one of the five equity_pct buckets
    # (0.2/0.4/0.6/0.8/1.0) is the closest match for some combination of inputs
    # -- a base sitting exactly on a bucket boundary would make that bucket
    # unreachable (ties always resolving to its neighbor). horizon_adj alone
    # cannot supply that combination in practice (see LITERACY_EQUITY_ADJUSTMENT
    # above for why); literacy_adj is what actually makes MODERATE and GROWTH
    # reachable via realistic, non-edge-case users.
    risk_base = {RiskTolerance.LOW: 0.15, RiskTolerance.MODERATE: 0.45, RiskTolerance.HIGH: 0.75}[
        user.risk_tolerance
    ]
    horizon_adj = _clip01(user.investment_horizon_years / 30) * 0.3
    literacy_adj = LITERACY_EQUITY_ADJUSTMENT[user.financial_literacy]
    ideal_equity = _clip01(risk_base + horizon_adj + literacy_adj)
    liquidity_ratio = _clip01(user.liquidity_requirements / user.savings) if user.savings > 0 else 1.0

    scores: dict[str, CandidateScore] = {}
    for candidate_id, equity_pct in EQUITY_PCT.items():
        violations = []
        if candidate_id == "AGGRESSIVE" and not (
            user.risk_tolerance == RiskTolerance.HIGH and user.investment_horizon_years >= 10
        ):
            violations.append("I_HC1_RISK_HORIZON")
        if candidate_id == "GROWTH" and not (
            user.risk_tolerance in (RiskTolerance.MODERATE, RiskTolerance.HIGH)
            and user.investment_horizon_years >= 5
        ):
            violations.append("I_HC2_RISK_HORIZON")
        if candidate_id == "BALANCED" and user.investment_horizon_years < 3:
            violations.append("I_HC3_HORIZON")

        scores[candidate_id] = CandidateScore(
            candidate_id,
            violations,
            goal_alignment=_clip01(1 - abs(equity_pct - ideal_equity)),
            suitability_assessment=_clip01(equity_pct * liquidity_ratio),
            financial_objective_score=_clip01(
                equity_pct * _clip01(user.investment_horizon_years / GROWTH_REALIZATION_HORIZON_YEARS)
            ),
            # 0.5: even 100% equity retains a documented liquidity-score floor of
            # 0.5 -- this is a relative-preservation score, not an absolute one
            liquidity_score=_clip01(1 - equity_pct * 0.5),
        )
    return scores


# --- RETIREMENT ----------------------------------------------------------------------
# Hard constraints:
#   R_HC1  ON_TRACK requires on_track_ratio >= 1.0 (can't claim on-track if the math says short)
#   R_HC2  INCREASE_RETIREMENT_SAVING requires net_cash_flow > 0
#   R_HC3  EXTEND_RETIREMENT_HORIZON requires age < 65
#   REDUCE_RETIREMENT_SPENDING_TARGET has no hard constraint (always-available lever)

def _score_retirement(user: User) -> dict[str, CandidateScore]:
    target = retirement_goal_target(user)
    projected = projected_retirement_value(user)
    on_track_ratio = projected / target if target > 0 else 1.0
    gap = max(1 - on_track_ratio, 0.0)
    ncf = net_cash_flow(user)
    n = max(user.investment_horizon_years, 1)

    scores: dict[str, CandidateScore] = {}

    violations = [] if on_track_ratio >= 1.0 else ["R_HC1_SHORTFALL"]
    scores["ON_TRACK"] = CandidateScore(
        "ON_TRACK",
        violations,
        goal_alignment=_clip01(on_track_ratio),
        suitability_assessment=0.0,  # no action proposed, so no new risk introduced
        financial_objective_score=_clip01(on_track_ratio / 2),  # /2: ratio==1.0 (just on track) scores 0.5, not 1.0
        liquidity_score=1.0,
    )

    violations = [] if ncf > 0 else ["R_HC2_NO_SURPLUS"]
    scores["INCREASE_RETIREMENT_SAVING"] = CandidateScore(
        "INCREASE_RETIREMENT_SAVING",
        violations,
        goal_alignment=_clip01(gap),
        suitability_assessment=_clip01(1 - ncf / (MAX_PLAUSIBLE_SAVINGS_RATE * user.monthly_income))
        if user.monthly_income
        else 1.0,
        financial_objective_score=_clip01(ncf * 12 * n / target) if target > 0 else 0.0,
        liquidity_score=0.7,  # flat: a fixed, documented relative ranking across the 4 retirement candidates
    )

    scores["REDUCE_RETIREMENT_SPENDING_TARGET"] = CandidateScore(
        "REDUCE_RETIREMENT_SPENDING_TARGET",
        [],
        goal_alignment=_clip01(gap),
        suitability_assessment=0.2,  # flat: a "soft" lever (lowering an aspiration) carries little real risk
        financial_objective_score=_clip01(gap) if gap > 0 else 0.3,  # 0.3: baseline credit when already on track
        liquidity_score=1.0,
    )

    violations = [] if user.age < 65 else ["R_HC3_TOO_OLD_TO_EXTEND"]
    scores["EXTEND_RETIREMENT_HORIZON"] = CandidateScore(
        "EXTEND_RETIREMENT_HORIZON",
        violations,
        goal_alignment=_clip01(gap),
        suitability_assessment=_clip01((user.age - RETIREMENT_AGE_RISK_FLOOR) / RETIREMENT_AGE_RISK_SPAN),
        financial_objective_score=_clip01(RETIREMENT_HORIZON_EXTENSION_YEARS / n),
        liquidity_score=1.0,
    )
    return scores


#: Every hard-constraint rule ID that is *evaluated* for a scenario type,
#: regardless of whether any particular user's candidates end up violating it.
#: This is what `hard_constraints_checked` in a ground-truth record reports --
#: distinct from `hard_constraint_violations`, which is per-candidate and only
#: lists the rules that actually failed for that specific user.
HARD_CONSTRAINT_RULES: dict[ScenarioType, list[str]] = {
    ScenarioType.BUDGETING: ["B_HC1", "B_HC2"],
    ScenarioType.DEBT_PRIORITIZATION: [
        "D_HC1_NO_LOANS",
        "D_HC1_INSUFFICIENT_SAVINGS",
        "D_HC2_NO_LOANS",
        "D_HC2_INSUFFICIENT_SAVINGS",
        "D_HC3_INSUFFICIENT_SAVINGS",
        "D_HC4_NO_CAPACITY",
    ],
    ScenarioType.EMERGENCY_FUND: [
        "E_HC_BUILD_TO_3_MONTHS_ALREADY_MET",
        "E_HC_BUILD_TO_6_MONTHS_ALREADY_MET",
        "E_HC_BUILD_TO_9_MONTHS_ALREADY_MET",
        "E_HC4_BELOW_FLOOR",
    ],
    ScenarioType.INVESTMENT_ALLOCATION: ["I_HC1_RISK_HORIZON", "I_HC2_RISK_HORIZON", "I_HC3_HORIZON"],
    ScenarioType.RETIREMENT: ["R_HC1_SHORTFALL", "R_HC2_NO_SURPLUS", "R_HC3_TOO_OLD_TO_EXTEND"],
}


_SCORERS = {
    ScenarioType.BUDGETING: _score_budgeting,
    ScenarioType.DEBT_PRIORITIZATION: _score_debt,
    ScenarioType.EMERGENCY_FUND: _score_emergency_fund,
    ScenarioType.INVESTMENT_ALLOCATION: _score_investment,
    ScenarioType.RETIREMENT: _score_retirement,
}


def evaluate_candidates(user: User, scenario_type: ScenarioType) -> list[CandidateScore]:
    """Score every substantive candidate in `scenario_type`'s catalogue against `user`.

    Returns them in fixed catalogue order. Raises KeyError if `scenario_type` has
    no registered scorer (defensive -- unreachable while ScenarioType only has the
    five members every scorer above covers)."""
    scorer = _SCORERS[scenario_type]
    scored = scorer(user)
    return [scored[candidate_id] for candidate_id in substantive_candidates(scenario_type)]
