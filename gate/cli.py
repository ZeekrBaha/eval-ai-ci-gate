"""cli.py — entry points for the gate.

  run-gate            read scorecard -> validate -> threshold check -> regression diff
                      -> decide -> write report -> print headline -> exit 0/1/2
  accept-baseline     promote a scorecard to the new committed baseline (explicit, never automatic)
  validate-scorecard  contract check only (for consumers to self-test their emitter)

Console-script wrappers return an int; setuptools/uv use it as the process exit code.
The offline core (validate + threshold + regression + report) needs no network or secrets.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
from dataclasses import replace
from pathlib import Path
from typing import Any

from gate.config import ConfigError, load_config
from gate.decide import EXIT_BLOCKED, EXIT_INCOMPLETE, Verdict, decide
from gate.notify import notify_slack, upsert_pr_comment
from gate.regression import diff
from gate.report import render_html, render_markdown
from gate.schema import ContractError, validate
from gate.thresholds import evaluate


def run_gate_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="run-gate", description="Run the eval release gate.")
    parser.add_argument("--scorecard", required=True, type=Path)
    parser.add_argument("--gates", required=True, type=Path)
    parser.add_argument("--baseline", type=Path, default=None)
    parser.add_argument("--report-out", required=True, type=Path)
    parser.add_argument("--md-out", type=Path, default=None)
    args = parser.parse_args(argv)

    # Try to surface the scorecard's run_id even if later steps fail, for the report.
    run_id = "unknown"
    baseline_run_id: str | None = None
    baseline_age_days: int | None = None

    try:
        scorecard = _read_json(args.scorecard)
        if isinstance(scorecard, dict):
            run_id = str(scorecard.get("run_id", "unknown"))
        validate(scorecard)  # ContractError -> controlled report

        config = load_config(args.gates)  # ConfigError -> controlled report
        metric_summary = scorecard["metric_summary"]

        regressions = []
        notes: list[str] = []
        if args.baseline is not None:
            if not Path(args.baseline).exists():
                # A "regression-vs-baseline" gate cannot certify "no regression" with no
                # baseline. Missing baseline -> INCOMPLETE (unless explicitly optional).
                if config.regression.require_baseline:
                    verdict = Verdict(
                        status="INCOMPLETE",
                        exit_code=EXIT_INCOMPLETE,
                        reason="baseline_missing",
                        headline=f"Eval gate incomplete: baseline not found at {args.baseline}",
                    )
                    _emit(verdict, run_id, None, None, args.report_out, args.md_out)
                    return verdict.exit_code
                notes.append(f"baseline {args.baseline} not found; regression check skipped")
            else:
                baseline = _read_json(args.baseline)  # ConfigError on bad JSON
                regressions = diff(config, metric_summary, baseline.get("metric_summary", {}))
                baseline_run_id = baseline.get("baseline_run_id") or baseline.get("run_id")
                baseline_age_days = _baseline_age_days(baseline.get("accepted_at"))
                note = _stale_baseline_note(baseline_age_days, config.regression.baseline_max_age_days)
                if note:
                    notes.append(note)

        hard, soft = evaluate(config, metric_summary)  # ConfigError if a gate metric is absent
        verdict = decide(hard, soft, regressions)
        if notes:
            verdict = replace(verdict, notes=notes)
    except ContractError as exc:
        verdict = Verdict(
            status="BLOCKED", exit_code=EXIT_BLOCKED, reason="contract",
            headline=f"Eval gate error: {exc}",
        )
    except ConfigError as exc:
        verdict = Verdict(
            status="BLOCKED", exit_code=EXIT_BLOCKED, reason="error",
            headline=f"Eval gate error: {exc}",
        )

    _emit(verdict, run_id, baseline_run_id, baseline_age_days, args.report_out, args.md_out)
    return verdict.exit_code


def _stale_baseline_note(age_days: int | None, max_age_days: int) -> str | None:
    if age_days is not None and age_days > max_age_days:
        return (
            f"baseline is {age_days} days old (limit {max_age_days}); "
            f"re-accept it to keep regression detection meaningful"
        )
    return None


def accept_baseline_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="accept-baseline", description="Promote a scorecard to the new committed baseline."
    )
    parser.add_argument("--scorecard", required=True, type=Path)
    parser.add_argument("--baseline-out", required=True, type=Path)
    args = parser.parse_args(argv)

    try:
        scorecard = _read_json(args.scorecard)
        validate(scorecard)
    except (ConfigError, ContractError) as exc:
        # Controlled failure: never write a baseline from a bad/missing scorecard.
        print(f"accept-baseline error: {exc}")
        return 1

    stamped = dict(scorecard)
    stamped["baseline_run_id"] = scorecard.get("run_id", "unknown")
    stamped["accepted_at"] = datetime.date.today().isoformat()

    out = Path(args.baseline_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(stamped, indent=2, sort_keys=True) + "\n")
    print(f"Baseline accepted: {stamped['baseline_run_id']} -> {out}")
    return 0


def validate_scorecard_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="validate-scorecard", description="Validate a scorecard against the v1 contract."
    )
    parser.add_argument("--scorecard", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        validate(_read_json(args.scorecard))
    except (ConfigError, ContractError) as exc:
        print(f"Invalid scorecard: {exc}")
        return 1
    print("Scorecard is valid (contract v1).")
    return 0


# --- helpers -----------------------------------------------------------------


def _read_json(path: Path) -> Any:
    try:
        return json.loads(Path(path).read_text())
    except FileNotFoundError as exc:
        raise ConfigError(f"file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"invalid JSON in {path}: {exc}") from exc


def _baseline_age_days(accepted_at: Any) -> int | None:
    if not isinstance(accepted_at, str):
        return None
    try:
        accepted = datetime.date.fromisoformat(accepted_at)
    except ValueError:
        return None
    return (datetime.date.today() - accepted).days


def _emit(
    verdict: Verdict,
    run_id: str,
    baseline_run_id: str | None,
    baseline_age_days: int | None,
    report_out: Path,
    md_out: Path | None,
) -> None:
    html = render_html(
        verdict,
        scorecard_run_id=run_id,
        baseline_run_id=baseline_run_id,
        baseline_age_days=baseline_age_days,
    )
    Path(report_out).write_text(html)
    summary = render_markdown(
        verdict,
        scorecard_run_id=run_id,
        baseline_run_id=baseline_run_id,
        baseline_age_days=baseline_age_days,
    )
    if md_out is not None:
        Path(md_out).write_text(summary)
    print(verdict.headline)
    for note in verdict.notes:
        print(f"note: {note}")
    _run_notifiers(summary)


def _run_notifiers(summary: str) -> None:
    """Fire optional notifiers from environment config. Prints only when an attempt is made,
    so stdout stays clean and deterministic when nothing is configured."""
    webhook = os.environ.get("SLACK_WEBHOOK_URL")
    if webhook:
        print(f"Slack: {notify_slack(summary, webhook)}")

    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    pr_number = _pr_number_from_env()
    if token and repo and pr_number:
        result = upsert_pr_comment(
            summary, repo=repo, pr_number=pr_number, token=token
        )
        print(f"PR comment: {result}")


def _pr_number_from_env() -> int | None:
    # On pull_request events GITHUB_REF looks like 'refs/pull/123/merge'.
    ref = os.environ.get("GITHUB_REF", "")
    parts = ref.split("/")
    if len(parts) >= 3 and parts[1] == "pull":
        try:
            return int(parts[2])
        except ValueError:
            return None
    return None
