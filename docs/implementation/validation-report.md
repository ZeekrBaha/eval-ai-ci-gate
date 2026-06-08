# Validation Report — `eval-ai-ci-gate`

Measured results for the core build (Phases 0–5). Notifiers (T6) and Project 1 onboarding (T7)
are not yet built; their rows are marked PENDING. Honesty rule: no result is checked unless a
command actually produced it.

## Static + unit
- [x] `uv run ruff check .` — clean
- [x] `uv run mypy gate tests` — strict, no issues (16 source files)
- [x] `uv run pytest` — **67 passed**
- [x] `make check` — green

## Behavioral scenarios (exit code + money-shot line) — verified via CLI
- [x] Pass → exit 0 — `Eval gate passed`
- [x] Hard-gate fail → exit 1 — `Eval gate failed: faithfulness 0.93 < 0.95 (hard gate)`
- [x] Incomplete → exit 2 — `Eval gate incomplete: faithfulness not evaluated`
- [x] Regression → exit 1 — `Eval gate failed: answer_relevance dropped 0.08 vs baseline 0.93 (tolerance 0.02) (regression)`
- [x] Bad contract → exit 1 — `Eval gate error: scorecard missing required field 'metric_summary'`
- [x] Determinism (run twice, identical stdout) — `test_cli.test_run_gate_is_deterministic`

## Report
- [x] Self-contained HTML (no `<link>`, no `src=`, no `http`) — `test_report.test_html_is_self_contained_no_external_assets`
- [x] Renders for every verdict type — `test_report`
- [x] Secret hygiene (no webhook host in report/log) — `test_report.test_no_secret_leak_in_output`
- [x] Report written even on contract failure — `test_cli.test_bad_contract_exits_1_and_still_writes_report`

## Baseline safety
- [x] `accept-baseline` stamps `baseline_run_id` + `accepted_at` — `test_cli.test_accept_baseline_writes_stamped_file`
- [x] `run-gate` never mutates the baseline — `test_cli.test_run_gate_never_mutates_baseline`

## CI surfaces
- [x] This repo `ci.yml` authored (lint+types+tests → `make gate` → `make gate-fail`)
- [x] `make gate` PASS (exit 0) and `make gate-fail` BLOCKED (exit 1) confirmed locally
- [ ] PENDING: `examples/consumer-workflow.yml` run from a second repo (needs repo pushed + tagged `v1`)

## Notify (mocked)
- [ ] PENDING (T6.1/T6.2) — Slack + PR-comment notifiers not yet implemented

## End-to-end (Project 1 onboarding)
- [ ] PENDING (T7.1) — migrate Project 1 thresholds to `eval-gates.yaml` + `uses:` the reusable gate

## Skipped checks (with reasons)
- Consumer-workflow live run + notifier tests: deferred until the repo is pushed/tagged and the
  notifiers are implemented. Local dogfood (`make gate` / `make gate-fail`) covers the gate logic.

## Unresolved risks
- The reusable workflow installs the gate from `git+https://github.com/ZeekrBaha/eval-ai-ci-gate@v1`;
  the `v1` tag must exist before a consumer can call it. Until then, consumers can pin a commit SHA.
