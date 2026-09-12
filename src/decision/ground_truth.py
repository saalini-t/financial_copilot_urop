"""Deterministic ground-truth generation: the orchestrator for Phase 5.

Reads the existing data/synthetic/users.json and data/synthetic/scenarios.json
(never modifies either), scores every scenario's candidates, ranks them, and
writes one GroundTruthRecord per scenario. No LLM, RAG, embeddings, external
API, or random-number call appears anywhere in this module or the ones it
imports -- every record is a pure function of the two input files.

Usage:
    python -m src.decision.ground_truth
    python -m src.decision.ground_truth --users-input data/synthetic/users.json \
        --scenarios-input data/synthetic/scenarios.json
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pydantic import BaseModel, Field

from src.decision.candidate_catalogue import ABSTAIN, CANDIDATE_CATALOGUE, CATALOGUE_VERSION
from src.decision.candidate_evaluator import HARD_CONSTRAINT_RULES, CandidateScore, evaluate_candidates
from src.decision.ranking import AbstentionReason, rank
from src.models.scenario import Scenario, ScenarioType
from src.models.user import User
from src.utils import load_json, save_json

DECISION_RULE_VERSION = "1.0.0"
DATASET_VERSION = "v1.0"
GENERATOR_VERSION = "v1.0"

DEFAULT_USERS_PATH = REPO_ROOT / "data" / "synthetic" / "users.json"
DEFAULT_SCENARIOS_PATH = REPO_ROOT / "data" / "synthetic" / "scenarios.json"
DEFAULT_OUTPUT_PATH = REPO_ROOT / "data" / "synthetic" / "ground_truth.json"
DEFAULT_SUMMARY_PATH = REPO_ROOT / "results" / "metrics" / "ground_truth_summary.json"


class GroundTruthRecord(BaseModel):
    scenario_id: str
    user_id: str
    scenario_type: ScenarioType
    ground_truth_decision: str
    candidate_scores: list[dict] = Field(default_factory=list)
    valid_candidates: list[str] = Field(default_factory=list)
    rejected_candidates: list[str] = Field(default_factory=list)
    hard_constraints_checked: list[str] = Field(default_factory=list)
    goal_alignment: float | None = None
    suitability_assessment: float | None = None
    financial_objective_score: float | None = None
    liquidity_score: float | None = None
    abstention: bool
    abstention_reason: str | None = None
    decision_rule_version: str = DECISION_RULE_VERSION
    provenance: dict = Field(default_factory=dict)


def load_users(path: str | Path = DEFAULT_USERS_PATH) -> list[User]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"{path} does not exist -- run generate_users.py first.")
    raw = load_json(path)
    records = raw.get("users") if isinstance(raw, dict) else raw
    if not records:
        raise ValueError(f"{path} contains no users.")
    return [User.model_validate(record) for record in records]


def load_scenarios(path: str | Path = DEFAULT_SCENARIOS_PATH) -> list[Scenario]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"{path} does not exist -- run generate_scenarios.py first.")
    raw = load_json(path)
    records = raw.get("scenarios") if isinstance(raw, dict) else raw
    if not records:
        raise ValueError(f"{path} contains no scenarios.")
    return [Scenario.model_validate(record) for record in records]


def _serialize_score(score: CandidateScore) -> dict:
    return {
        "candidate_id": score.candidate_id,
        "feasible": score.feasible,
        "hard_constraint_violations": list(score.hard_constraint_violations),
        "goal_alignment": round(score.goal_alignment, 6),
        "suitability_assessment": round(score.suitability_assessment, 6),
        "financial_objective_score": round(score.financial_objective_score, 6),
        "liquidity_score": round(score.liquidity_score, 6),
    }


def _provenance(user: User, scenario: Scenario) -> dict:
    """Independently re-derived from the live User record (not just trusted from
    the scenario file) -- `matches_scenario_snapshot` confirms the two agree,
    which they always should since neither input file is ever modified here."""
    live_dump = user.model_dump(mode="json")
    live_snapshot = {field: live_dump[field] for field in scenario.required_information if field in live_dump}
    return {
        "user_id": user.user_id,
        "scenario_id": scenario.scenario_id,
        "fields_used": list(scenario.required_information),
        "user_attribute_values": live_snapshot,
        "matches_scenario_snapshot": live_snapshot == scenario.relevant_user_attributes,
    }


def _abstain_record(
    scenario: Scenario, reason: AbstentionReason, provenance: dict, hard_constraints_checked: list[str] | None = None
) -> GroundTruthRecord:
    return GroundTruthRecord(
        scenario_id=scenario.scenario_id,
        user_id=scenario.user_id,
        scenario_type=scenario.scenario_type,
        ground_truth_decision=ABSTAIN,
        candidate_scores=[],
        valid_candidates=[],
        rejected_candidates=[],
        hard_constraints_checked=hard_constraints_checked or [],
        abstention=True,
        abstention_reason=reason.value,
        decision_rule_version=DECISION_RULE_VERSION,
        provenance=provenance,
    )


def evaluate_scenario(user: User, scenario: Scenario) -> GroundTruthRecord:
    """Produce exactly one deterministic ground-truth outcome for `scenario`."""
    provenance = _provenance(user, scenario)

    # Structural pre-check: does the scenario's own required_information actually
    # resolve against its relevant_user_attributes snapshot? Never invent a value
    # for a missing field -- abstain instead.
    missing_fields = [f for f in scenario.required_information if f not in scenario.relevant_user_attributes]
    if missing_fields:
        return _abstain_record(scenario, AbstentionReason.MISSING_REQUIRED_INFORMATION, provenance)

    if scenario.scenario_type not in CANDIDATE_CATALOGUE:
        # Unreachable while ScenarioType has exactly the five members every
        # scorer covers -- kept as an explicit, documented safety valve.
        return _abstain_record(scenario, AbstentionReason.UNSUPPORTED_SCENARIO, provenance)

    scores = evaluate_candidates(user, scenario.scenario_type)
    winner, valid_ids, rejected_ids, reason = rank(scores, scenario.scenario_type)
    hard_checked = HARD_CONSTRAINT_RULES.get(scenario.scenario_type, [])
    serialized_scores = [_serialize_score(s) for s in scores]

    if winner is None:
        assert reason is not None
        return GroundTruthRecord(
            scenario_id=scenario.scenario_id,
            user_id=scenario.user_id,
            scenario_type=scenario.scenario_type,
            ground_truth_decision=ABSTAIN,
            candidate_scores=serialized_scores,
            valid_candidates=valid_ids,
            rejected_candidates=rejected_ids,
            hard_constraints_checked=hard_checked,
            abstention=True,
            abstention_reason=reason.value,
            decision_rule_version=DECISION_RULE_VERSION,
            provenance=provenance,
        )

    winning_score = next(s for s in scores if s.candidate_id == winner)
    return GroundTruthRecord(
        scenario_id=scenario.scenario_id,
        user_id=scenario.user_id,
        scenario_type=scenario.scenario_type,
        ground_truth_decision=winner,
        candidate_scores=serialized_scores,
        valid_candidates=valid_ids,
        rejected_candidates=rejected_ids,
        hard_constraints_checked=hard_checked,
        goal_alignment=round(winning_score.goal_alignment, 6),
        suitability_assessment=round(winning_score.suitability_assessment, 6),
        financial_objective_score=round(winning_score.financial_objective_score, 6),
        liquidity_score=round(winning_score.liquidity_score, 6),
        abstention=False,
        abstention_reason=None,
        decision_rule_version=DECISION_RULE_VERSION,
        provenance=provenance,
    )


def generate_ground_truth(users: list[User], scenarios: list[Scenario]) -> list[GroundTruthRecord]:
    """Exactly one GroundTruthRecord per scenario, in scenario order. Pure
    function of its arguments -- no randomness, no I/O, no LLM calls."""
    users_by_id = {u.user_id: u for u in users}
    records: list[GroundTruthRecord] = []
    for scenario in scenarios:
        user = users_by_id.get(scenario.user_id)
        if user is None:
            raise ValueError(f"{scenario.scenario_id} references unknown user_id '{scenario.user_id}'")
        records.append(evaluate_scenario(user, scenario))
    return records


def build_dataset(
    records: list[GroundTruthRecord],
    *,
    users_path: Path,
    scenarios_path: Path,
) -> dict:
    users_meta = load_json(users_path).get("metadata", {}) if Path(users_path).exists() else {}
    scenarios_meta = load_json(scenarios_path).get("metadata", {}) if Path(scenarios_path).exists() else {}
    return {
        "metadata": {
            "dataset_version": DATASET_VERSION,
            "generator_version": GENERATOR_VERSION,
            "decision_rule_version": DECISION_RULE_VERSION,
            "catalogue_version": CATALOGUE_VERSION,
            "num_records": len(records),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_user_dataset_version": users_meta.get("dataset_version"),
            "source_user_dataset_seed": users_meta.get("random_seed"),
            "source_scenario_dataset_version": scenarios_meta.get("dataset_version"),
            "source_scenario_dataset_seed": scenarios_meta.get("random_seed"),
        },
        "ground_truth": [record.model_dump(mode="json") for record in records],
    }


def compute_summary(records: list[GroundTruthRecord]) -> dict:
    total = len(records)
    decision_counts = Counter(r.ground_truth_decision for r in records)
    by_type: dict[str, Counter] = {}
    abstention_by_type: Counter = Counter()
    scenarios_by_type: Counter = Counter()
    for r in records:
        t = r.scenario_type.value
        by_type.setdefault(t, Counter())[r.ground_truth_decision] += 1
        scenarios_by_type[t] += 1
        if r.abstention:
            abstention_by_type[t] += 1

    abstained = [r for r in records if r.abstention]
    abstention_reason_counts = Counter(r.abstention_reason for r in abstained)
    total_rejected = sum(len(r.rejected_candidates) for r in records)
    total_valid = sum(len(r.valid_candidates) for r in records)

    return {
        "total_scenarios": total,
        "decision_distribution": dict(decision_counts),
        "decision_distribution_by_scenario_type": {t: dict(c) for t, c in by_type.items()},
        "abstention_count": len(abstained),
        "abstention_percentage": round(100 * len(abstained) / total, 2) if total else 0.0,
        "abstention_distribution_by_scenario_type": {
            t: {
                "count": abstention_by_type.get(t, 0),
                "percentage": round(100 * abstention_by_type.get(t, 0) / scenarios_by_type[t], 2),
            }
            for t in scenarios_by_type
        },
        "abstention_reason_distribution": dict(abstention_reason_counts),
        "num_hard_constraint_rejections": total_rejected,
        "average_valid_candidates": round(total_valid / total, 3) if total else 0.0,
        "average_rejected_candidates": round(total_rejected / total, 3) if total else 0.0,
    }


def print_summary(summary: dict) -> None:
    print(f"\nGround truth -- {summary['total_scenarios']} scenarios")
    print("-" * 50)
    print(f"decision_distribution: {summary['decision_distribution']}")
    print(f"abstention: {summary['abstention_count']} ({summary['abstention_percentage']}%)")
    print(f"abstention_by_scenario_type: {summary['abstention_distribution_by_scenario_type']}")
    print(f"abstention_reason_distribution: {summary['abstention_reason_distribution']}")
    print(f"hard-constraint rejections: {summary['num_hard_constraint_rejections']}")
    print(f"avg valid candidates: {summary['average_valid_candidates']}")
    print(f"avg rejected candidates: {summary['average_rejected_candidates']}")
    print()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--users-input", type=Path, default=DEFAULT_USERS_PATH)
    parser.add_argument("--scenarios-input", type=Path, default=DEFAULT_SCENARIOS_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--summary-output", type=Path, default=DEFAULT_SUMMARY_PATH)
    args = parser.parse_args(argv)

    users = load_users(args.users_input)
    scenarios = load_scenarios(args.scenarios_input)
    records = generate_ground_truth(users, scenarios)
    dataset = build_dataset(records, users_path=args.users_input, scenarios_path=args.scenarios_input)
    save_json(dataset, args.output)

    summary = compute_summary(records)
    save_json(summary, args.summary_output)
    print_summary(summary)

    print(f"Wrote {len(records)} ground-truth records to {args.output}")
    print(f"Wrote summary to {args.summary_output}")


if __name__ == "__main__":
    main()
