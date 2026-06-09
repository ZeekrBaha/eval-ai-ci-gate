"""T1.2 — eval-gates.yaml loading + validation. See docs/implementation/design.md §3."""

from pathlib import Path

import pytest

from gate.config import ConfigError, GateConfig, load_config

VALID_YAML = """
schema_version: "1.0"
hard_gates:
  - { metric: faithfulness,       threshold: 0.95, op: ">=" }
  - { metric: hallucination_rate, threshold: 0.01, op: "<=" }
soft_gates:
  - { metric: answer_relevance,   threshold: 0.90, op: ">=" }
regression:
  default_tolerance: 0.02
  per_metric:
    hallucination_rate: 0.01
    advice_boundary: 0.00
  baseline_max_age_days: 30
"""


def _write(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "eval-gates.yaml"
    p.write_text(text)
    return p


def test_loads_valid_config(tmp_path: Path) -> None:
    cfg = load_config(_write(tmp_path, VALID_YAML))
    assert isinstance(cfg, GateConfig)
    assert len(cfg.hard_gates) == 2
    assert len(cfg.soft_gates) == 1
    assert cfg.regression.default_tolerance == 0.02
    assert cfg.regression.per_metric["hallucination_rate"] == 0.01
    assert cfg.regression.baseline_max_age_days == 30


def test_hard_gate_fields_parsed(tmp_path: Path) -> None:
    cfg = load_config(_write(tmp_path, VALID_YAML))
    g = cfg.hard_gates[0]
    assert g.metric == "faithfulness"
    assert g.threshold == 0.95
    assert g.op == ">="


def test_rejects_bad_op(tmp_path: Path) -> None:
    bad = VALID_YAML.replace('op: ">="', 'op: "=="', 1)
    with pytest.raises(ConfigError, match="op"):
        load_config(_write(tmp_path, bad))


def test_rejects_missing_threshold(tmp_path: Path) -> None:
    bad = "hard_gates:\n  - { metric: faithfulness, op: \">=\" }\n"
    with pytest.raises(ConfigError, match="threshold"):
        load_config(_write(tmp_path, bad))


def test_rejects_unknown_top_level_key(tmp_path: Path) -> None:
    bad = VALID_YAML + "\nbogus_key: true\n"
    with pytest.raises(ConfigError, match="bogus_key"):
        load_config(_write(tmp_path, bad))


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "nope.yaml")


def test_defaults_when_regression_absent(tmp_path: Path) -> None:
    minimal = 'hard_gates:\n  - { metric: faithfulness, threshold: 0.95, op: ">=" }\n'
    cfg = load_config(_write(tmp_path, minimal))
    assert cfg.soft_gates == []
    assert cfg.regression.per_metric == {}
    assert cfg.regression.default_tolerance >= 0.0


def test_tolerance_for_returns_per_metric_then_default(tmp_path: Path) -> None:
    cfg = load_config(_write(tmp_path, VALID_YAML))
    assert cfg.regression.tolerance_for("hallucination_rate") == 0.01
    assert cfg.regression.tolerance_for("faithfulness") == 0.02  # falls back to default


def test_require_baseline_defaults_true(tmp_path: Path) -> None:
    cfg = load_config(_write(tmp_path, VALID_YAML))
    assert cfg.regression.require_baseline is True


def test_require_baseline_can_be_disabled(tmp_path: Path) -> None:
    yaml_text = VALID_YAML + "  require_baseline: false\n"
    cfg = load_config(_write(tmp_path, yaml_text))
    assert cfg.regression.require_baseline is False


def test_require_baseline_must_be_bool(tmp_path: Path) -> None:
    yaml_text = VALID_YAML + "  require_baseline: maybe\n"
    with pytest.raises(ConfigError, match="require_baseline"):
        load_config(_write(tmp_path, yaml_text))
