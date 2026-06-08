"""T2.1 — threshold evaluation over metric_summary. See docs/implementation/design.md §2."""

import pytest

from gate.config import GateConfig, GateSpec, RegressionSpec
from gate.thresholds import GateResult, evaluate


def _cfg(hard: list[GateSpec], soft: list[GateSpec] | None = None) -> GateConfig:
    return GateConfig(hard_gates=hard, soft_gates=soft or [], regression=RegressionSpec())


def test_hard_gate_pass() -> None:
    cfg = _cfg([GateSpec("faithfulness", 0.95, ">=")])
    hard, _soft = evaluate(cfg, {"faithfulness": 0.96})
    assert hard[0].status == "pass"


def test_hard_gate_fail() -> None:
    cfg = _cfg([GateSpec("faithfulness", 0.95, ">=")])
    hard, _soft = evaluate(cfg, {"faithfulness": 0.93})
    assert hard[0].status == "fail"
    assert hard[0].message == "faithfulness 0.93 < 0.95"


def test_le_metric_fails_when_above_max() -> None:
    cfg = _cfg([GateSpec("hallucination_rate", 0.01, "<=")])
    hard, _soft = evaluate(cfg, {"hallucination_rate": 0.19})
    assert hard[0].status == "fail"
    assert hard[0].message == "hallucination_rate 0.19 > 0.01"


def test_le_metric_passes_at_boundary() -> None:
    cfg = _cfg([GateSpec("hallucination_rate", 0.01, "<=")])
    hard, _soft = evaluate(cfg, {"hallucination_rate": 0.01})
    assert hard[0].status == "pass"


def test_ge_metric_passes_at_boundary() -> None:
    cfg = _cfg([GateSpec("faithfulness", 0.95, ">=")])
    hard, _soft = evaluate(cfg, {"faithfulness": 0.95})
    assert hard[0].status == "pass"


def test_null_metric_is_unevaluated() -> None:
    cfg = _cfg([GateSpec("consistency_passk", 0.90, ">=")])
    hard, _soft = evaluate(cfg, {"consistency_passk": None})
    assert hard[0].status == "unevaluated"


def test_soft_gate_evaluated_separately() -> None:
    cfg = _cfg([], [GateSpec("answer_relevance", 0.90, ">=")])
    hard, soft = evaluate(cfg, {"answer_relevance": 0.80})
    assert hard == []
    assert soft[0].status == "fail"


def test_metric_absent_from_summary_is_config_error() -> None:
    cfg = _cfg([GateSpec("faithfulness", 0.95, ">=")])
    from gate.config import ConfigError

    with pytest.raises(ConfigError, match="faithfulness"):
        evaluate(cfg, {"answer_relevance": 0.9})


def test_values_rounded_to_three_dp_in_message() -> None:
    cfg = _cfg([GateSpec("faithfulness", 0.95, ">=")])
    hard, _soft = evaluate(cfg, {"faithfulness": 0.9349})
    assert hard[0].message == "faithfulness 0.935 < 0.95"


def test_result_carries_metric_and_value() -> None:
    cfg = _cfg([GateSpec("faithfulness", 0.95, ">=")])
    hard, _soft = evaluate(cfg, {"faithfulness": 0.96})
    r: GateResult = hard[0]
    assert r.metric == "faithfulness"
    assert r.value == 0.96
    assert r.threshold == 0.95
