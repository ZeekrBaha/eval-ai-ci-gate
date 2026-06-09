"""T1.1 — scorecard contract (v1) validation. See docs/implementation/scorecard-contract.md."""

from typing import Any

import pytest

from gate.schema import ContractError, validate


def _valid() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "run_id": "run-1",
        "status": "PASS",
        "metric_summary": {"faithfulness": 0.96, "consistency_passk": None},
    }


def test_accepts_valid_v1_scorecard() -> None:
    validate(_valid())  # must not raise


def test_rejects_missing_metric_summary() -> None:
    sc = _valid()
    del sc["metric_summary"]
    with pytest.raises(ContractError, match="metric_summary"):
        validate(sc)


def test_rejects_missing_status() -> None:
    sc = _valid()
    del sc["status"]
    with pytest.raises(ContractError, match="status"):
        validate(sc)


def test_rejects_missing_schema_version() -> None:
    sc = _valid()
    del sc["schema_version"]
    with pytest.raises(ContractError, match="schema_version"):
        validate(sc)


def test_rejects_metric_summary_wrong_type() -> None:
    sc = _valid()
    sc["metric_summary"] = ["faithfulness", 0.9]
    with pytest.raises(ContractError, match="metric_summary"):
        validate(sc)


def test_rejects_non_numeric_metric_value() -> None:
    sc = _valid()
    sc["metric_summary"] = {"faithfulness": "high"}
    with pytest.raises(ContractError, match="faithfulness"):
        validate(sc)


def test_allows_null_metric_value() -> None:
    sc = _valid()
    sc["metric_summary"] = {"faithfulness": None}
    validate(sc)  # null means "not evaluated" — legal


def test_rejects_unsupported_major_version() -> None:
    sc = _valid()
    sc["schema_version"] = "2.0"
    with pytest.raises(ContractError, match="version"):
        validate(sc)


def test_accepts_higher_minor_version() -> None:
    sc = _valid()
    sc["schema_version"] = "1.5"
    validate(sc)  # same major -> compatible


def test_rejects_non_dict() -> None:
    with pytest.raises(ContractError):
        validate(["not", "a", "dict"])


def test_rejects_non_string_run_id() -> None:
    sc = _valid()
    sc["run_id"] = 123
    with pytest.raises(ContractError, match="run_id"):
        validate(sc)


def test_rejects_unknown_status_value() -> None:
    sc = _valid()
    sc["status"] = "MAYBE"
    with pytest.raises(ContractError, match="status"):
        validate(sc)


def test_accepts_each_known_status() -> None:
    for s in ("PASS", "BLOCKED", "INCOMPLETE"):
        sc = _valid()
        sc["status"] = s
        validate(sc)


def test_rejects_non_string_metric_key() -> None:
    sc = _valid()
    sc["metric_summary"] = {1: 0.9}
    with pytest.raises(ContractError, match="metric name"):
        validate(sc)


def test_rejects_non_finite_metric_value() -> None:
    sc = _valid()
    sc["metric_summary"] = {"faithfulness": float("nan")}
    with pytest.raises(ContractError, match="finite"):
        validate(sc)
    sc["metric_summary"] = {"faithfulness": float("inf")}
    with pytest.raises(ContractError, match="finite"):
        validate(sc)


def test_rejects_schema_version_without_minor() -> None:
    sc = _valid()
    sc["schema_version"] = "1"
    with pytest.raises(ContractError, match="major.minor"):
        validate(sc)


def test_rejects_schema_version_with_three_parts() -> None:
    sc = _valid()
    sc["schema_version"] = "1.0.0"
    with pytest.raises(ContractError, match="major.minor"):
        validate(sc)
