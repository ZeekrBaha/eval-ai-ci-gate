"""decide.py — apply verdict precedence to threshold + regression results.

Precedence (highest wins), per docs/implementation/design.md §2:
  1. contract   -> BLOCKED  (exit 1)   [produced upstream in cli.py]
  2. hard_gate  -> BLOCKED  (exit 1)
  3. regression -> BLOCKED  (exit 1)
  4. incomplete -> INCOMPLETE (exit 2)
  5. pass       -> PASS     (exit 0)
Soft-gate failures are warnings only and never change the status.
Exit codes preserve Project 1's contract: PASS=0, BLOCKED=1, INCOMPLETE=2.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from gate.regression import RegressionResult
from gate.thresholds import GateResult

Status = Literal["PASS", "BLOCKED", "INCOMPLETE"]
Reason = Literal[
    "contract",
    "error",
    "hard_gate",
    "regression",
    "baseline_missing",
    "baseline_invalid",
    "incomplete",
    "pass",
]

EXIT_PASS = 0
EXIT_BLOCKED = 1
EXIT_INCOMPLETE = 2


@dataclass(frozen=True)
class Verdict:
    status: Status
    exit_code: int
    reason: Reason
    headline: str
    hard: list[GateResult] = field(default_factory=list)
    soft: list[GateResult] = field(default_factory=list)
    regressions: list[RegressionResult] = field(default_factory=list)
    warnings: list[GateResult] = field(default_factory=list)
    # Non-blocking notices (e.g. stale-baseline warning). Surfaced in the report, never change status.
    notes: list[str] = field(default_factory=list)


def decide(
    hard: list[GateResult],
    soft: list[GateResult],
    regression: list[RegressionResult],
) -> Verdict:
    """Combine results into a single Verdict per the precedence above."""
    hard_failures = [r for r in hard if r.status == "fail"]
    unevaluated = [r for r in hard if r.status == "unevaluated"]
    regressed = [r for r in regression if r.regressed]
    warnings = [r for r in soft if r.status == "fail"]

    if hard_failures:
        return Verdict(
            status="BLOCKED",
            exit_code=EXIT_BLOCKED,
            reason="hard_gate",
            headline=f"Eval gate failed: {hard_failures[0].message} (hard gate)",
            hard=hard,
            soft=soft,
            regressions=regressed,
            warnings=warnings,
        )
    if regressed:
        return Verdict(
            status="BLOCKED",
            exit_code=EXIT_BLOCKED,
            reason="regression",
            headline=f"Eval gate failed: {regressed[0].message} (regression)",
            hard=hard,
            soft=soft,
            regressions=regressed,
            warnings=warnings,
        )
    if unevaluated:
        return Verdict(
            status="INCOMPLETE",
            exit_code=EXIT_INCOMPLETE,
            reason="incomplete",
            headline=f"Eval gate incomplete: {unevaluated[0].metric} not evaluated",
            hard=hard,
            soft=soft,
            regressions=regressed,
            warnings=warnings,
        )
    return Verdict(
        status="PASS",
        exit_code=EXIT_PASS,
        reason="pass",
        headline="Eval gate passed",
        hard=hard,
        soft=soft,
        regressions=regressed,
        warnings=warnings,
    )
