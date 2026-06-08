# Validation Plan — `eval-ai-ci-gate`

Commands and checks defined **before** coding. After implementation, results go in
`validation-report.md` (commands run, summaries, skips, unresolved risks).

## 1. Static + unit (local, offline, no secrets)

| Check | Command | Gate |
|---|---|---|
| Lint | `uv run ruff check gate tests` | clean |
| Types | `uv run mypy gate` | clean |
| Unit/integration tests | `uv run pytest -q` | all pass |
| All of the above | `make check` | green |

Coverage expectation: every module in `gate/` has a matching `tests/test_*.py`; every precedence rung in
`decide.py` has a dedicated case.

## 2. Behavioral gate checks (the money shots — run against bundled fixtures)

| Scenario | Command | Expected exit | Expected first line |
|---|---|---|---|
| Pass | `run-gate --scorecard fixtures/pass.json ...` | `0` | `Eval gate passed` |
| Hard-gate fail | `... fixtures/fail.json ...` | `1` | `Eval gate failed: faithfulness 0.93 < 0.95 (hard gate)` |
| Incomplete | `... fixtures/incomplete.json ...` | `2` | `Eval gate incomplete: faithfulness not evaluated` |
| Regression | `... fixtures/regressed.json --baseline fixtures/baseline.json` | `1` | `Eval gate failed: answer_relevance 0.85 < 0.88 (regression: dropped 0.05 > tol 0.02)` |
| Bad contract | `... fixtures/no_metric_summary.json` | `1` | `Eval gate error: scorecard missing required field 'metric_summary'` |

All five must be **deterministic** (N-03): run twice, diff the stdout + `report.html` → no differences.

## 3. Report checks

- `report.html` opens in a browser with **no network** (no external CSS/JS/font refs) — grep the file for
  `http://`/`https://` asset links → none (except intentional run links, which are fine as text).
- Report renders for every verdict type, including bad-contract.
- **Secret hygiene (N-04):** with a webhook configured, grep `report.html` + `run.log` for the webhook
  host → zero matches.

## 4. CI surface checks

- This repo's `.github/workflows/ci.yml` is green on `main`/`master` (ruff+mypy+pytest+`run-gate` on pass fixture).
- `examples/consumer-workflow.yml` exercised against a passing fixture (green) and a failing fixture (red),
  via `act` locally or a throwaway consumer run. Capture both for the README.
- Reusable workflow `uses:` resolves and runs from a second repo (the Project 1 migration proves this for real).

## 5. Notify checks (mocked — no live Slack/GitHub calls in tests)

- Slack: mocked POST asserts payload contains verdict + top failures; **no-webhook** path logs
  `skipped: no webhook` and the process still exits with the correct code.
- PR comment: mocked GitHub API asserts create-then-update yields **one** comment; off-PR/token-less runs skip.

## 6. End-to-end proof (Project 1 onboarding — T7.1)

- Project 1 CI runs through the reusable gate; verdict matches a local `run-gate` on the same scorecard.
- Migrate `src/config.py` thresholds to `eval-gates.yaml` → verdict unchanged (regression-free migration).
- Introduce a deliberate metric regression in Project 1 → its PR is blocked with the regression money-shot.

## 7. Anti-slop / honesty gate (carried from the portfolio)

- README labels thresholds **proposed**, calibrated against a stated baseline — never "real internal gate".
- No fabricated metric values in examples; fixtures use realistic numbers consistent with Project 1 runs.
- `README` includes the red-PR screenshot (`Eval gate failed: faithfulness 0.93 < 0.95`) as the headline artifact.

## 8. Definition of done (project-level)

One command in a consumer repo's CI → validate scorecard → check thresholds → diff baseline → render
report → post summary → **exit non-zero if any hard gate fails or any metric regresses beyond tolerance** —
with the gate logic living entirely in `eval-ai-ci-gate`, zero copies in the consumer.
