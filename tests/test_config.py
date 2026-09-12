"""Every configs/*.yaml must load and merge cleanly over base.yaml."""

from pathlib import Path

import pytest

from src.config import ExperimentConfig, load_config

CONFIGS_DIR = Path(__file__).resolve().parent.parent / "configs"

LADDER_CONFIGS = ["baseline.yaml", "rag.yaml", "personalized.yaml", "full_copilot.yaml"]


@pytest.mark.parametrize("filename", LADDER_CONFIGS)
def test_each_configuration_loads(filename):
    config = load_config(CONFIGS_DIR / filename)
    assert isinstance(config, ExperimentConfig)
    assert config.config_name == filename.removesuffix(".yaml")


def test_base_defaults_are_inherited():
    config = load_config(CONFIGS_DIR / "baseline.yaml")
    assert config.catalogue_version == "1.0.0"
    assert config.min_confidence == pytest.approx(0.60)
    assert config.scoring_weights.w_goal == pytest.approx(0.4)


def test_module_toggles_match_configuration_ladder():
    baseline = load_config(CONFIGS_DIR / "baseline.yaml")
    assert not any(baseline.modules.model_dump().values())

    full = load_config(CONFIGS_DIR / "full_copilot.yaml")
    assert all(full.modules.model_dump().values())

    personalized = load_config(CONFIGS_DIR / "personalized.yaml")
    assert personalized.modules.use_personalization is True
    assert personalized.modules.use_constraints is False


def test_missing_config_name_is_rejected(tmp_path):
    bad_config = tmp_path / "bad.yaml"
    bad_config.write_text("explanation_type: free_form\n")
    with pytest.raises(ValueError):
        load_config(bad_config)
