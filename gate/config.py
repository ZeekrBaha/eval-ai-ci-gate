"""config.py — load and validate eval-gates.yaml into typed specs.

Mirrors Project 1's GateSpec shape ({metric, threshold, op}) so migrating a repo's
Python thresholds into YAML is mechanical, and adds a per-metric regression tolerance.
See docs/implementation/design.md §3.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

VALID_OPS = (">=", "<=")
KNOWN_TOP_LEVEL = {"schema_version", "hard_gates", "soft_gates", "regression"}
DEFAULT_TOLERANCE = 0.02
DEFAULT_BASELINE_MAX_AGE_DAYS = 30


class ConfigError(ValueError):
    """Raised when eval-gates.yaml is missing, malformed, or has an invalid value."""


@dataclass(frozen=True)
class GateSpec:
    """A single threshold gate: *metric* must satisfy *op* *threshold*."""

    metric: str
    threshold: float
    op: str  # ">=" | "<="


@dataclass(frozen=True)
class RegressionSpec:
    """Regression tolerances. tolerance = max allowed adverse change vs baseline."""

    default_tolerance: float = DEFAULT_TOLERANCE
    per_metric: dict[str, float] = field(default_factory=dict)
    baseline_max_age_days: int = DEFAULT_BASELINE_MAX_AGE_DAYS

    def tolerance_for(self, metric: str) -> float:
        """Per-metric tolerance if set, else the default tolerance."""
        return self.per_metric.get(metric, self.default_tolerance)


@dataclass(frozen=True)
class GateConfig:
    hard_gates: list[GateSpec]
    soft_gates: list[GateSpec]
    regression: RegressionSpec


def load_config(path: Path) -> GateConfig:
    """Load *path* (eval-gates.yaml) into a validated GateConfig. Raise ConfigError on any problem."""
    if not Path(path).exists():
        raise ConfigError(f"eval-gates config not found: {path}")

    try:
        raw = yaml.safe_load(Path(path).read_text()) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"could not parse YAML in {path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigError(f"eval-gates config must be a mapping, got {type(raw).__name__}")

    unknown = set(raw) - KNOWN_TOP_LEVEL
    if unknown:
        raise ConfigError(f"unknown top-level key(s) in eval-gates config: {sorted(unknown)}")

    hard = _parse_gates(raw.get("hard_gates", []), "hard_gates")
    soft = _parse_gates(raw.get("soft_gates", []), "soft_gates")
    regression = _parse_regression(raw.get("regression", {}))
    return GateConfig(hard_gates=hard, soft_gates=soft, regression=regression)


def _parse_gates(items: Any, where: str) -> list[GateSpec]:
    if not isinstance(items, list):
        raise ConfigError(f"{where} must be a list, got {type(items).__name__}")
    specs: list[GateSpec] = []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            raise ConfigError(f"{where}[{i}] must be a mapping, got {type(item).__name__}")
        for key in ("metric", "threshold", "op"):
            if key not in item:
                raise ConfigError(f"{where}[{i}] missing required key '{key}'")
        op = item["op"]
        if op not in VALID_OPS:
            raise ConfigError(f"{where}[{i}] invalid op '{op}'; must be one of {list(VALID_OPS)}")
        threshold = item["threshold"]
        if isinstance(threshold, bool) or not isinstance(threshold, (int, float)):
            raise ConfigError(f"{where}[{i}] threshold must be a number, got {threshold!r}")
        specs.append(GateSpec(metric=str(item["metric"]), threshold=float(threshold), op=op))
    return specs


def _parse_regression(raw: Any) -> RegressionSpec:
    if not isinstance(raw, dict):
        raise ConfigError(f"regression must be a mapping, got {type(raw).__name__}")
    unknown = set(raw) - {"default_tolerance", "per_metric", "baseline_max_age_days"}
    if unknown:
        raise ConfigError(f"unknown key(s) in regression: {sorted(unknown)}")

    default_tol = raw.get("default_tolerance", DEFAULT_TOLERANCE)
    if isinstance(default_tol, bool) or not isinstance(default_tol, (int, float)):
        raise ConfigError(f"regression.default_tolerance must be a number, got {default_tol!r}")

    per_metric_raw = raw.get("per_metric", {}) or {}
    if not isinstance(per_metric_raw, dict):
        raise ConfigError("regression.per_metric must be a mapping")
    per_metric: dict[str, float] = {}
    for metric, tol in per_metric_raw.items():
        if isinstance(tol, bool) or not isinstance(tol, (int, float)):
            raise ConfigError(f"regression.per_metric['{metric}'] must be a number, got {tol!r}")
        per_metric[str(metric)] = float(tol)

    max_age = raw.get("baseline_max_age_days", DEFAULT_BASELINE_MAX_AGE_DAYS)
    if isinstance(max_age, bool) or not isinstance(max_age, int):
        raise ConfigError(f"regression.baseline_max_age_days must be an integer, got {max_age!r}")

    return RegressionSpec(
        default_tolerance=float(default_tol),
        per_metric=per_metric,
        baseline_max_age_days=max_age,
    )
