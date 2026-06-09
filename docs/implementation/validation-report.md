# Validation Report — `eval-ai-ci-gate`

Measured results. Honesty rule: no result is checked unless a command actually produced it.
Live notifier POSTs and the consumer-workflow run only execute in real CI; those rows say so.

## Static + unit
- [x] `uv run ruff check .` — clean
- [x] `uv run mypy gate tests` — strict, no issues
- [x] `uv run pytest` — **100 passed**
- [x] `make check` — green

## Behavioral scenarios (exit code + money-shot line) — verified via CLI
- [x] Pass → exit 0 — `Eval gate passed`
- [x] Hard-gate fail → exit 1 — `Eval gate failed: faithfulness 0.93 < 0.95 (hard gate)`
- [x] Incomplete (null hard metric) → exit 2 — `Eval gate incomplete: faithfulness not evaluated`
- [x] Regression → exit 1 — `... answer_relevance dropped 0.08 vs baseline 0.93 (tolerance 0.02) (regression)`
- [x] Bad contract → exit 1 — `Eval gate error: scorecard missing required field 'metric_summary'`
- [x] Determinism (run twice, identical stdout) — `test_cli.test_run_gate_is_deterministic`

## Decision correctness (post-review hardening)
- [x] Exact comparison, not rounded — `0.9495` fails a `>= 0.95` gate (`test_thresholds`)
- [x] Regression uses exact adverse delta with subtraction-noise epsilon — a drop equal to tolerance does not regress (`test_regression`)

## Baseline policy
- [x] Missing required baseline → INCOMPLETE (exit 2), not a silent pass — `test_cli.test_missing_baseline_is_incomplete`
- [x] `regression.require_baseline: false` → skip with a note, PASS — `test_cli.test_missing_baseline_optional_when_not_required`
- [x] `baseline_max_age_days` enforced as a non-blocking note — `test_cli.test_stale_baseline_adds_note_but_still_passes`
- [x] `accept-baseline` stamps `baseline_run_id` + `accepted_at`; `run-gate` never mutates the baseline — `test_cli`

## Operational error handling (deterministic, never a stack trace)
- [x] Bad YAML gates → exit 1 + report — `test_cli.test_bad_yaml_gates_is_controlled_error`
- [x] Missing scorecard file → exit 1 + report — `test_cli.test_missing_scorecard_file_is_controlled`
- [x] Gate metric absent from scorecard → exit 1 + report — `test_cli.test_missing_configured_metric_is_controlled`

## Contract validator (tightened)
- [x] Rejects non-string `run_id`, unknown `status`, non-string metric keys, non-finite values, and `schema_version` that is not exactly `major.minor` — `test_schema`

## Report
- [x] Self-contained HTML (no `<link>`/`src=`/`http`) — `test_report`
- [x] Renders for every verdict type, incl. contract failure — `test_report`, `test_cli`
- [x] Secret hygiene (no webhook host in report/log) — `test_report.test_no_secret_leak_in_output`

## Notifiers (T6 — implemented)
- [x] Slack: posts when webhook set; skips when unset; reports non-2xx without raising — `test_notify`
- [x] PR comment: create-then-update yields one sticky comment; off-PR/token-less skips — `test_notify`
- [x] Graceful when `requests` (notify extra) is absent — skips, never crashes — `test_notify`
- [x] CLI glue fires from env and stays silent/deterministic when unconfigured — `test_cli`
- [ ] LIVE-CI-ONLY: real Slack/GitHub POSTs run only in CI with a webhook/token (unit tests mock HTTP)
- [x] Action install path uses the `notify` extra (`action.yml`, `eval-gate.yml`); `ci.yml` `install-smoke` job proves `import requests, gate.notify`

## End-to-end (Project 1 onboarding — T7, done)
- [x] `schema_version` added to Project 1 emitter (TDD) — Project 1 suite **559 passed**
- [x] Project 1 thresholds externalized to `eval-gates.yaml`; baseline committed from a real PASS run
- [x] Project 1's real PASS scorecard clears the gate locally (`Eval gate passed`, exit 0)
- [ ] LIVE-CI-ONLY: Project 1's `eval-ci-gate.yml` resolves `@v1` once eval-ai-ci-gate#1 merges

## Unresolved risks
- `@v1` tag must exist for consumers; it is pushed. Consumers may pin a commit SHA instead.
- Notifier live paths are exercised only in CI; local proof is mock + import-smoke.
