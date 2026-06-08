"""T4.1 — CLI entry points: run-gate, accept-baseline, validate-scorecard."""

import json
from pathlib import Path

import pytest

from gate.cli import accept_baseline_main, run_gate_main, validate_scorecard_main

FIX = Path(__file__).parent / "fixtures"
GATES = str(FIX / "eval-gates.yaml")


def _run(tmp_path: Path, scorecard: str, baseline: str | None = None) -> tuple[int, Path]:
    report = tmp_path / "report.html"
    argv = ["--scorecard", str(FIX / scorecard), "--gates", GATES, "--report-out", str(report)]
    if baseline is not None:
        argv += ["--baseline", str(FIX / baseline)]
    code = run_gate_main(argv)
    return code, report


def test_pass_exits_0(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, report = _run(tmp_path, "pass.json", "baseline.json")
    assert code == 0
    assert "Eval gate passed" in capsys.readouterr().out
    assert report.exists()


def test_hard_fail_exits_1_with_money_shot(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, _ = _run(tmp_path, "fail.json", "baseline.json")
    assert code == 1
    out = capsys.readouterr().out
    assert "Eval gate failed: faithfulness 0.93 < 0.95 (hard gate)" in out


def test_incomplete_exits_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, _ = _run(tmp_path, "incomplete.json", "baseline.json")
    assert code == 2
    assert "incomplete" in capsys.readouterr().out.lower()


def test_regression_exits_1(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, _ = _run(tmp_path, "regressed.json", "baseline.json")
    assert code == 1
    assert "regression" in capsys.readouterr().out.lower()


def test_bad_contract_exits_1_and_still_writes_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, report = _run(tmp_path, "no_metric_summary.json")
    assert code == 1
    assert "metric_summary" in capsys.readouterr().out
    assert report.exists()  # report renders even on contract failure


def test_report_written_on_every_run(tmp_path: Path) -> None:
    _, report = _run(tmp_path, "pass.json", "baseline.json")
    assert report.read_text().lower().startswith("<!doctype html>")


def test_run_gate_is_deterministic(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code1, _ = _run(tmp_path, "fail.json", "baseline.json")
    out1 = capsys.readouterr().out
    code2, _ = _run(tmp_path, "fail.json", "baseline.json")
    out2 = capsys.readouterr().out
    assert code1 == code2 == 1
    assert out1 == out2


# --- accept-baseline ---------------------------------------------------------


def test_accept_baseline_writes_stamped_file(tmp_path: Path) -> None:
    out = tmp_path / "baseline" / "scorecard.json"
    code = accept_baseline_main(["--scorecard", str(FIX / "pass.json"), "--baseline-out", str(out)])
    assert code == 0
    data = json.loads(out.read_text())
    assert data["baseline_run_id"] == "run-pass"
    assert "accepted_at" in data
    assert data["metric_summary"]["faithfulness"] == 0.96


def test_run_gate_never_mutates_baseline(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    baseline.write_text((FIX / "baseline.json").read_text())
    before = baseline.read_text()
    run_gate_main(
        [
            "--scorecard", str(FIX / "pass.json"),
            "--gates", GATES,
            "--baseline", str(baseline),
            "--report-out", str(tmp_path / "r.html"),
        ]
    )
    assert baseline.read_text() == before  # a normal gate run is read-only on the baseline


# --- validate-scorecard ------------------------------------------------------


def test_validate_scorecard_ok(tmp_path: Path) -> None:
    assert validate_scorecard_main(["--scorecard", str(FIX / "pass.json")]) == 0


def test_validate_scorecard_bad(tmp_path: Path) -> None:
    assert validate_scorecard_main(["--scorecard", str(FIX / "no_metric_summary.json")]) == 1


# --- notifier glue -----------------------------------------------------------


def test_no_notify_output_when_unconfigured(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    for var in ("SLACK_WEBHOOK_URL", "GITHUB_TOKEN", "GITHUB_REPOSITORY", "GITHUB_REF"):
        monkeypatch.delenv(var, raising=False)
    _run(tmp_path, "pass.json", "baseline.json")
    out = capsys.readouterr().out
    assert "Slack:" not in out
    assert "PR comment:" not in out


def test_slack_fired_when_webhook_env_set(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/x")
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    captured: list[str] = []

    def fake_slack(summary: str, url: str | None) -> str:
        captured.append(summary)
        return "sent"

    monkeypatch.setattr("gate.cli.notify_slack", fake_slack)
    _run(tmp_path, "fail.json", "baseline.json")
    assert "Slack: sent" in capsys.readouterr().out
    assert captured  # summary was passed through
