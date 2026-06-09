"""T2.2 — regression diff vs baseline. See docs/implementation/design.md §3 (direction-awareness)."""

from gate.config import GateConfig, GateSpec, RegressionSpec
from gate.regression import diff


def _cfg(
    hard: list[GateSpec] | None = None,
    default_tol: float = 0.02,
    per_metric: dict[str, float] | None = None,
) -> GateConfig:
    return GateConfig(
        hard_gates=hard or [],
        soft_gates=[],
        regression=RegressionSpec(default_tolerance=default_tol, per_metric=per_metric or {}),
    )


def test_ge_metric_drop_beyond_tolerance_regresses() -> None:
    cfg = _cfg([GateSpec("answer_relevance", 0.90, ">=")])
    results = diff(cfg, {"answer_relevance": 0.85}, {"answer_relevance": 0.90})
    r = results[0]
    assert r.regressed is True
    assert "dropped" in r.message


def test_ge_metric_drop_within_tolerance_ok() -> None:
    cfg = _cfg([GateSpec("answer_relevance", 0.90, ">=")], default_tol=0.05)
    results = diff(cfg, {"answer_relevance": 0.87}, {"answer_relevance": 0.90})
    assert results[0].regressed is False


def test_ge_metric_improvement_never_regresses() -> None:
    cfg = _cfg([GateSpec("answer_relevance", 0.90, ">=")])
    results = diff(cfg, {"answer_relevance": 0.99}, {"answer_relevance": 0.90})
    assert results[0].regressed is False


def test_le_metric_increase_beyond_tolerance_regresses() -> None:
    # hallucination_rate is lower-is-better: an INCREASE beyond tolerance is the regression.
    cfg = _cfg([GateSpec("hallucination_rate", 0.01, "<=")], per_metric={"hallucination_rate": 0.01})
    results = diff(cfg, {"hallucination_rate": 0.05}, {"hallucination_rate": 0.01})
    assert results[0].regressed is True
    assert "rose" in results[0].message


def test_le_metric_decrease_never_regresses() -> None:
    cfg = _cfg([GateSpec("hallucination_rate", 0.01, "<=")])
    results = diff(cfg, {"hallucination_rate": 0.00}, {"hallucination_rate": 0.05})
    assert results[0].regressed is False


def test_metric_without_gate_defaults_higher_is_better() -> None:
    cfg = _cfg([])  # no gate -> default direction ">=", a drop is adverse
    results = diff(cfg, {"some_metric": 0.5}, {"some_metric": 0.9})
    assert results[0].regressed is True


def test_null_baseline_metric_skipped() -> None:
    cfg = _cfg([])
    results = diff(cfg, {"m": 0.5}, {"m": None})
    assert results == []


def test_null_current_metric_skipped() -> None:
    cfg = _cfg([])
    results = diff(cfg, {"m": None}, {"m": 0.9})
    assert results == []


def test_metric_absent_from_baseline_skipped() -> None:
    cfg = _cfg([])
    results = diff(cfg, {"new_metric": 0.5}, {})
    assert results == []


def test_zero_tolerance_blocks_any_drop() -> None:
    cfg = _cfg([GateSpec("advice_boundary", 1.0, ">=")], per_metric={"advice_boundary": 0.0})
    results = diff(cfg, {"advice_boundary": 0.99}, {"advice_boundary": 1.0})
    assert results[0].regressed is True


def test_drop_exactly_equal_to_tolerance_does_not_regress() -> None:
    # A drop of exactly the tolerance is allowed (regress only when it EXCEEDS tolerance),
    # and float subtraction noise must not flip this.
    cfg = _cfg([GateSpec("answer_relevance", 0.90, ">=")], default_tol=0.02)
    results = diff(cfg, {"answer_relevance": 0.88}, {"answer_relevance": 0.90})
    assert results[0].regressed is False


def test_drop_just_over_tolerance_regresses() -> None:
    cfg = _cfg([GateSpec("answer_relevance", 0.90, ">=")], default_tol=0.02)
    results = diff(cfg, {"answer_relevance": 0.8749}, {"answer_relevance": 0.90})
    assert results[0].regressed is True


def test_result_carries_values_and_tolerance() -> None:
    cfg = _cfg([GateSpec("answer_relevance", 0.90, ">=")], default_tol=0.02)
    r = diff(cfg, {"answer_relevance": 0.85}, {"answer_relevance": 0.90})[0]
    assert r.metric == "answer_relevance"
    assert r.current == 0.85
    assert r.baseline == 0.90
    assert r.tolerance == 0.02
