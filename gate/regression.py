"""regression.py — direction-aware diff of current vs baseline metric_summary.

A metric "regresses" when it moves in the ADVERSE direction by more than its tolerance:
  - op ">=" (higher is better): a DROP beyond tolerance regresses.
  - op "<=" (lower is better):  an INCREASE beyond tolerance regresses.
Direction is read from the configured gate for that metric; metrics with no gate
default to higher-is-better. Null (unevaluated) or absent baseline/current values
are skipped — you cannot regress against what was not measured (contract rule 2).
"""

from __future__ import annotations

from dataclasses import dataclass

from gate.config import GateConfig
from gate.thresholds import MetricSummary

DEFAULT_OP = ">="  # metrics with no configured gate: assume higher is better.
# Decisions use the exact adverse delta, but a tiny epsilon absorbs float-subtraction
# noise so a drop of *exactly* the tolerance is not mis-flagged as a regression.
_DECISION_EPS = 1e-9


@dataclass(frozen=True)
class RegressionResult:
    metric: str
    op: str
    current: float
    baseline: float
    tolerance: float
    adverse_delta: float  # how far it moved the wrong way (>= 0 means worse than baseline)
    regressed: bool

    @property
    def message(self) -> str:
        verb = "dropped" if self.op == ">=" else "rose"
        return (
            f"{self.metric} {verb} {round(self.adverse_delta, 3)} vs baseline "
            f"{round(self.baseline, 3)} (tolerance {round(self.tolerance, 3)})"
        )


def diff(
    config: GateConfig, current: MetricSummary, baseline: MetricSummary
) -> list[RegressionResult]:
    """Return one RegressionResult per comparable metric (regressed or not)."""
    ops = _op_by_metric(config)
    results: list[RegressionResult] = []
    for metric, cur in current.items():
        base = baseline.get(metric)
        if cur is None or base is None or metric not in baseline:
            continue  # cannot compare unmeasured / absent values
        op = ops.get(metric, DEFAULT_OP)
        cur_f, base_f = float(cur), float(base)
        # Adverse movement: for ">=" a drop (base - cur); for "<=" an increase (cur - base).
        adverse_delta = base_f - cur_f if op == ">=" else cur_f - base_f
        tolerance = config.regression.tolerance_for(metric)
        # Regress only when the adverse move EXCEEDS the tolerance (exact, with an
        # epsilon for subtraction noise); a drop equal to tolerance is allowed.
        regressed = (adverse_delta - tolerance) > _DECISION_EPS
        results.append(
            RegressionResult(
                metric=metric,
                op=op,
                current=cur_f,
                baseline=base_f,
                tolerance=tolerance,
                adverse_delta=adverse_delta,
                regressed=regressed,
            )
        )
    return results


def _op_by_metric(config: GateConfig) -> dict[str, str]:
    ops: dict[str, str] = {}
    for spec in (*config.hard_gates, *config.soft_gates):
        ops[spec.metric] = spec.op
    return ops
