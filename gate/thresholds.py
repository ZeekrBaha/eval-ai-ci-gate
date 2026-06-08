"""thresholds.py — evaluate hard/soft gates over a scorecard's metric_summary.

A faithful, YAML-fed port of Project 1's gates.py semantics:
  - "pass"        metric satisfies its op/threshold
  - "fail"        metric breaches it
  - "unevaluated" metric value is None (not measured) -> drives INCOMPLETE for hard gates
Values are rounded to 3 decimal places for deterministic messages (N-03).
"""

from __future__ import annotations

import operator
from dataclasses import dataclass
from typing import Callable, Literal

from gate.config import ConfigError, GateConfig, GateSpec

MetricSummary = dict[str, float | int | None]

Status = Literal["pass", "fail", "unevaluated"]

_OPS: dict[str, Callable[[float, float], bool]] = {">=": operator.ge, "<=": operator.le}
# Human-readable breach symbol: the relation that is TRUE when the gate FAILS.
_BREACH_SYMBOL = {">=": "<", "<=": ">"}


@dataclass(frozen=True)
class GateResult:
    metric: str
    op: str
    threshold: float
    value: float | None
    status: Status

    @property
    def message(self) -> str:
        """One-line human summary, e.g. 'faithfulness 0.93 < 0.95'."""
        if self.value is None:
            return f"{self.metric} not evaluated (threshold {self.op} {_r(self.threshold)})"
        if self.status == "pass":
            return f"{self.metric} {_r(self.value)} {self.op} {_r(self.threshold)}"
        return f"{self.metric} {_r(self.value)} {_BREACH_SYMBOL[self.op]} {_r(self.threshold)}"


def evaluate(
    config: GateConfig, metric_summary: MetricSummary
) -> tuple[list[GateResult], list[GateResult]]:
    """Return (hard_results, soft_results) for *config* against *metric_summary*."""
    hard = [_eval_one(spec, metric_summary) for spec in config.hard_gates]
    soft = [_eval_one(spec, metric_summary) for spec in config.soft_gates]
    return hard, soft


def _eval_one(spec: GateSpec, metric_summary: MetricSummary) -> GateResult:
    if spec.metric not in metric_summary:
        # A configured gate referencing a metric the scorecard never emits is a
        # config/contract mismatch — fail fast rather than silently skip (contract rule 3).
        raise ConfigError(
            f"gate references metric '{spec.metric}' not present in scorecard metric_summary"
        )
    value = metric_summary[spec.metric]
    if value is None:
        return GateResult(spec.metric, spec.op, spec.threshold, None, "unevaluated")
    rounded = round(float(value), 3)
    passed = _OPS[spec.op](rounded, round(spec.threshold, 3))
    return GateResult(
        metric=spec.metric,
        op=spec.op,
        threshold=spec.threshold,
        value=float(value),
        status="pass" if passed else "fail",
    )


def _r(x: float) -> float:
    return round(x, 3)
