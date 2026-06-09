"""T2.3 — verdict precedence. See docs/implementation/design.md §2.

Precedence (highest wins): hard_gate > regression > incomplete > pass.
(Contract failure is rung 1 but is produced upstream in the CLI; see test_cli.)
Soft-gate failures are warnings only and never change the status.
"""

from gate.decide import decide
from gate.regression import RegressionResult
from gate.thresholds import GateResult


def _hard(metric: str, status: str) -> GateResult:
    return GateResult(metric, ">=", 0.95, 0.9 if status == "fail" else 0.99, status)  # type: ignore[arg-type]


def _reg(metric: str, regressed: bool) -> RegressionResult:
    return RegressionResult(metric, ">=", 0.85, 0.90, 0.02, 0.05 if regressed else 0.0, regressed)


def test_all_pass_is_pass_exit_0() -> None:
    v = decide([_hard("faithfulness", "pass")], [], [])
    assert v.status == "PASS"
    assert v.exit_code == 0
    assert v.headline == "Eval gate passed"


def test_hard_fail_blocks_exit_1() -> None:
    v = decide([_hard("faithfulness", "fail")], [], [])
    assert v.status == "BLOCKED"
    assert v.exit_code == 1
    assert v.reason == "hard_gate"
    assert v.headline == "Eval gate failed: faithfulness 0.9 < 0.95 (hard gate)"


def test_regression_blocks_exit_1() -> None:
    v = decide([_hard("faithfulness", "pass")], [], [_reg("answer_relevance", True)])
    assert v.status == "BLOCKED"
    assert v.exit_code == 1
    assert v.reason == "regression"
    assert "regression" in v.headline


def test_hard_fail_takes_precedence_over_regression() -> None:
    v = decide([_hard("faithfulness", "fail")], [], [_reg("answer_relevance", True)])
    assert v.reason == "hard_gate"


def test_unevaluated_hard_is_incomplete_exit_2() -> None:
    v = decide([_hard("consistency_passk", "unevaluated")], [], [])
    assert v.status == "INCOMPLETE"
    assert v.exit_code == 2
    assert v.reason == "incomplete"


def test_incomplete_never_upgraded_by_soft_pass() -> None:
    soft = [_hard("answer_relevance", "pass")]  # a passing soft gate
    v = decide([_hard("consistency_passk", "unevaluated")], soft, [])
    assert v.status == "INCOMPLETE"


def test_regression_takes_precedence_over_incomplete() -> None:
    v = decide(
        [_hard("consistency_passk", "unevaluated")], [], [_reg("answer_relevance", True)]
    )
    assert v.reason == "regression"


def test_soft_failures_are_warnings_not_blocking() -> None:
    v = decide([_hard("faithfulness", "pass")], [_hard("answer_relevance", "fail")], [])
    assert v.status == "PASS"
    assert len(v.warnings) == 1


def test_verdict_collects_regressed_only() -> None:
    v = decide(
        [_hard("faithfulness", "pass")],
        [],
        [_reg("a", True), _reg("b", False)],
    )
    assert [r.metric for r in v.regressions] == ["a"]
