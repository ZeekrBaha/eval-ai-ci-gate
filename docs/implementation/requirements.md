# Requirements — `eval-ai-ci-gate`

Each requirement has an ID, a statement, and an acceptance criterion that maps to a validation check
in `validation-plan.md`. Functional = `F-`, Non-functional = `N-`, Contract = `C-`.

## Functional

**F-01 — Config-driven thresholds.**
The gate reads hard/soft thresholds from `eval-gates.yaml`, not from code.
*Accept:* changing a threshold in YAML changes the verdict with no code edit; a malformed YAML fails
fast with a clear error naming the bad key.

**F-02 — Hard-gate enforcement.**
Given a `scorecard.json`, the gate evaluates every hard gate in `eval-gates.yaml` against
`metric_summary`. Any evaluated hard gate that fails → verdict `BLOCKED`, exit `1`.
*Accept:* a fixture with `faithfulness: 0.93` against `faithfulness >= 0.95` → exit `1`, message
`Eval gate failed: faithfulness 0.93 < 0.95`.

**F-03 — Incomplete handling.**
If a hard-gated metric is `null` (not evaluated), and no hard gate failed, verdict is `INCOMPLETE`,
exit `2`. A high soft-metric score must never upgrade `INCOMPLETE` to `PASS`.
*Accept:* fixture with `faithfulness: null` and all other hard gates passing → exit `2`.

**F-04 — Regression vs baseline.**
The gate diffs each metric in `metric_summary` against `baseline/scorecard.json`. If any metric drops
by more than its configured tolerance, verdict is `BLOCKED`, exit `1`, with a distinct `regression` reason.
*Accept:* baseline `answer_relevance: 0.90`, current `0.85`, tolerance `0.02` → exit `1`, message names
the metric, both values, and the tolerance.

**F-05 — Baseline accept flow.**
A documented, explicit path promotes the current scorecard to the new baseline (a script + an
"accept baseline" PR), never an automatic overwrite on a normal CI run.
*Accept:* running `accept-baseline` updates `baseline/scorecard.json` + records `baseline_run_id` and date;
a normal gate run never mutates the baseline file.

**F-06 — HTML report artifact.**
Each gate run renders a self-contained `report.html` (verdict, per-gate pass/fail, current-vs-baseline
diff table, baseline age) and uploads it as a CI artifact.
*Accept:* artifact present on every run (pass or fail); opens offline with no external assets.

**F-07 — Slack notifier (optional, graceful).**
When `SLACK_WEBHOOK_URL` is set, post a summary (verdict, top failures, link to the run). When unset,
skip silently and still exit with the correct code.
*Accept:* with no webhook, the run completes and exits correctly; notifier logs `skipped: no webhook`.

**F-08 — PR-comment summary.**
On `pull_request`, post/update a single sticky comment with the verdict, failing gates, and the
diff table. Re-runs update the same comment, not append new ones.
*Accept:* two runs on one PR → exactly one gate comment, reflecting the latest run.

**F-09 — Reusable workflow + composite action.**
Consumers invoke the gate via `uses: ZeekrBaha/eval-ai-ci-gate/.github/workflows/eval-gate.yml@v1`
(reusable workflow) **or** a composite action step, passing the path to their `scorecard.json` and
their `eval-gates.yaml`.
*Accept:* a sample consumer workflow in `examples/` runs green against a passing fixture and red against
a failing one, with zero gate logic copied into the consumer.

## Contract

**C-01 — Scorecard schema.**
The gate consumes `scorecard.json` containing at minimum `schema_version`, `status`, and a flat
`metric_summary` (metric → float|null). Documented in `scorecard-contract.md`.
*Accept:* a schema validator rejects a scorecard missing `metric_summary` with a clear error.

**C-02 — Versioning.**
The gate checks `schema_version` and fails clearly on an unsupported major version rather than
silently misreading.
*Accept:* `schema_version: "2.0"` against a v1 gate → fast, explicit failure.

## Non-functional

**N-01 — Offline core.** Threshold check + regression diff + report render run with no network, no secrets.
*Accept:* CI step with secrets masked/empty still produces a verdict and report.

**N-02 — Exit-code compatibility.** Preserve `0/1/2` = `PASS/BLOCKED/INCOMPLETE`.
*Accept:* matches Project 1's existing contract; documented in README.

**N-03 — Deterministic output.** Same inputs → byte-identical verdict text and report tables
(values rounded to 3 dp, stable key ordering).
*Accept:* running twice on the same fixtures diffs clean.

**N-04 — Secret hygiene.** Webhook URLs/tokens never appear in logs, the report, or artifacts.
*Accept:* grep of run.log + report.html for the webhook host returns nothing.

**N-05 — Quality gates on the gate itself.** `ruff`, `mypy`, and `pytest` pass in the repo's own CI.
*Accept:* `make check` is green.

## Non-goals (v1)

- Running the SUT or its eval suite (consumers do that; the gate consumes the artifact).
- Self-hosted runners; non-GitHub CI providers.
- A web dashboard / historical trend DB (single-run report only; trends deferred).
- Auto-tuning thresholds.
