"""The experiment manifest: dataset versions, seed, and the exact scenario ID
set every configuration must be run against.

Read-only over data/synthetic/{users,scenarios,ground_truth}.json -- this
module only reads their `metadata` blocks and the scenario ID list; it never
writes to any of the three frozen datasets. The manifest itself is the one
new artifact this module produces (data/synthetic/experiment_manifest.json).

Usage:
    python -m experiments.manifest
"""

from __future__ import annotations

import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.utils import load_json, save_json

MANIFEST_VERSION = "1.1.0"  # 1.1.0 adds `checksums` (Research Upgrade Plan, Phase 2)

DEFAULT_USERS_PATH = REPO_ROOT / "data" / "synthetic" / "users.json"
DEFAULT_SCENARIOS_PATH = REPO_ROOT / "data" / "synthetic" / "scenarios.json"
DEFAULT_GROUND_TRUTH_PATH = REPO_ROOT / "data" / "synthetic" / "ground_truth.json"
DEFAULT_MANIFEST_PATH = REPO_ROOT / "data" / "synthetic" / "experiment_manifest.json"


def _sha256_of_file(path: Path) -> str:
    """Hash the file's exact bytes on disk -- not the parsed JSON -- so the
    checksum also catches whitespace/encoding drift, not just content drift."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_manifest(
    users_path: Path = DEFAULT_USERS_PATH,
    scenarios_path: Path = DEFAULT_SCENARIOS_PATH,
    ground_truth_path: Path = DEFAULT_GROUND_TRUTH_PATH,
) -> dict:
    """Read the three frozen datasets' own metadata and scenario IDs -- never
    their content beyond that. The scenario_ids list preserves file order
    (S000001, S000002, ... ), which is itself deterministic (Phase 4).

    Also records a SHA-256 checksum of each frozen dataset file as it exists
    on disk right now (Research Upgrade Plan, Phase 2) -- a fast, independent
    way to confirm later that none of the three has been altered, without
    re-parsing or re-validating their full contents."""
    users_raw = load_json(users_path)
    scenarios_raw = load_json(scenarios_path)
    ground_truth_raw = load_json(ground_truth_path)

    users_meta = users_raw.get("metadata", {})
    scenarios_meta = scenarios_raw.get("metadata", {})
    ground_truth_meta = ground_truth_raw.get("metadata", {})

    scenario_ids = [s["scenario_id"] for s in scenarios_raw["scenarios"]]

    return {
        "manifest_version": MANIFEST_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset_version": users_meta.get("dataset_version"),
        "scenario_dataset_version": scenarios_meta.get("dataset_version"),
        "ground_truth_dataset_version": ground_truth_meta.get("dataset_version"),
        "ground_truth_version": ground_truth_meta.get("decision_rule_version"),
        "random_seed": users_meta.get("random_seed"),
        "scenario_random_seed": scenarios_meta.get("random_seed"),
        "user_count": users_meta.get("num_users"),
        "scenario_count": len(scenario_ids),
        "scenario_ids": scenario_ids,
        "checksums": {
            "algorithm": "sha256",
            "users_json": _sha256_of_file(users_path),
            "scenarios_json": _sha256_of_file(scenarios_path),
            "ground_truth_json": _sha256_of_file(ground_truth_path),
        },
    }


def save_manifest(manifest: dict, path: Path = DEFAULT_MANIFEST_PATH) -> None:
    save_json(manifest, path)


def load_manifest(path: Path = DEFAULT_MANIFEST_PATH) -> dict:
    return load_json(path)


def main() -> None:
    manifest = build_manifest()
    save_manifest(manifest)
    print(f"Wrote manifest for {manifest['scenario_count']} scenarios to {DEFAULT_MANIFEST_PATH}")


if __name__ == "__main__":
    main()
