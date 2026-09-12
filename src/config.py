"""Experiment configuration loading.

Every configs/*.yaml file (other than base.yaml) is merged over configs/base.yaml,
so shared defaults -- catalogue version, seed, confidence threshold, scoring weights --
live in one place and each configuration only states what it overrides.
"""

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

DEFAULT_BASE_CONFIG = Path(__file__).resolve().parent.parent / "configs" / "base.yaml"


class ModuleToggles(BaseModel):
    """Which architecture layers are switched on -- this is the experiment ladder switch."""

    use_rag: bool = False
    use_tools: bool = False
    use_personalization: bool = False
    use_constraints: bool = False
    use_candidate_catalogue: bool = False


class ScoringWeights(BaseModel):
    """Composite-score weights used only for confidence estimation, never for ranking."""

    w_goal: float = 0.4
    w_risk: float = 0.3
    w_obj: float = 0.2
    w_liq: float = 0.1


class ExperimentConfig(BaseModel):
    """Experimental settings only -- never API keys, credentials, or other
    secrets. Model name, temperature, prompt version, retrieval parameters, and
    tool settings all live here so no agent implementation under src/agents/
    hard-codes them (Phase 6A requirement)."""

    config_name: str
    description: str = ""
    catalogue_version: str = "1.0.0"
    ground_truth_engine_version: str = "1.0.0"
    random_seed: int = 42
    min_confidence: float = Field(default=0.60, ge=0, le=1)
    tie_epsilon: float = Field(default=1e-6, gt=0)
    scoring_weights: ScoringWeights = Field(default_factory=ScoringWeights)
    modules: ModuleToggles = Field(default_factory=ModuleToggles)
    explanation_type: str = "free_form"
    model_id: str = "mock-llm"
    temperature: float = 0.0
    prompt_version: str = "unversioned"
    retrieval: dict = Field(default_factory=dict, description="Retrieval parameters, e.g. top_k, index_version")
    tool_config: dict = Field(default_factory=dict, description="Deterministic-tool settings, e.g. tool_versions")


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(config_path: str | Path, base_path: str | Path = DEFAULT_BASE_CONFIG) -> ExperimentConfig:
    """Load one experiment configuration, merged over the shared base config."""
    base_path = Path(base_path)
    config_path = Path(config_path)

    base_data: dict[str, Any] = {}
    if base_path.exists():
        base_data = yaml.safe_load(base_path.read_text()) or {}

    override_data = yaml.safe_load(config_path.read_text()) or {}
    if "config_name" not in override_data:
        raise ValueError(f"{config_path} must define 'config_name'")

    return ExperimentConfig(**_deep_merge(base_data, override_data))
