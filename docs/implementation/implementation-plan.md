# Implementation Plan — `eval-ai-ci-gate`

Small, testable tasks. Each maps to requirements and to a validation check. Build order is
dependency-driven: contract → logic → reporting → CI surfaces → notify → consumer integration.
Coding begins only after this plan is approved.

Legend: **Files** (likely touched) · **Done when** (acceptance) · **Tests** · **Reqs**.

---

## Phase 0 — Scaffold

**T0.1 — Repo skeleton + tooling.**
- Files: `pyproject.toml`, `uv.lock`, `Makefile`, `ruff`/`mypy` config, `gate/__init__.py`, `.gitignore`, empty `tests/`.
- Done when: `uv sync` works; `make check` (ruff+mypy+pytest) runs green on an empty suite.
- Tests: a trivial `test_smoke.py`.
- Reqs: N-05.

---

## Phase 1 — Contract + config (the foundation)

**T1.1 — Scorecard schema validation.**
- Files: `gate/schema.py`, `tests/test_schema.py`, `tests/fixtures/*.json`.
- Done when: `validate()` accepts a v1 scorecard, rejects missing `metric_summary`, bad types, and
  unsupported major version, each with a precise `ContractError` message.
- Tests: valid; missing field; wrong type; `schema_version: "2.0"`.
- Reqs: C-01, C-02.

**T1.2 — Load + validate `eval-gates.yaml`.**
- Files: `gate/config.py`, `tests/test_config.py`, `examples/eval-gates.yaml`.
- Done when: YAML loads into typed specs; malformed/unknown keys fail fast naming the bad key;
  a threshold metric absent from a given scorecard is flagged as a config error at evaluation time.
- Tests: valid config; bad `op`; missing `threshold`; unknown top-level key.
- Reqs: F-01.

---

## Phase 2 — Verdict logic

**T2.1 — Threshold evaluation (hard/soft).**
- Files: `gate/thresholds.py`, `tests/test_thresholds.py`.
- Done when: hard fail → recorded; soft fail → warning; `null` metric → "unevaluated"; values rounded 3 dp.
  Logic is a faithful, YAML-fed port of Project 1's `gates.py` semantics.
- Tests: hard pass/fail; soft fail (warning only); `null` hard metric; `<=` metric (hallucination).
- Reqs: F-02, F-03, N-03.

**T2.2 — Regression diff vs baseline.**
- Files: `gate/regression.py`, `tests/test_regression.py`, regression fixtures.
- Done when: direction-aware drop detection; per-metric + default tolerance; `null` baseline metric skipped;
  baseline-age warning computed.
- Tests: drop > tolerance (`>=` metric); increase > tolerance (`<=` metric); within tolerance (pass);
  zero-tolerance metric; missing baseline metric; stale baseline warning.
- Reqs: F-04.

**T2.3 — Decide (precedence).**
- Files: `gate/decide.py`, `tests/test_decide.py`.
- Done when: §2 precedence enforced — contract > hard_gate > regression > incomplete > pass; correct
  exit codes (0/1/2); soft fails never block; produces a `Verdict` object carrying all detail.
- Tests: one case per precedence rung, plus pass-with-soft-warnings.
- Reqs: F-02, F-03, F-04, N-02.

---

## Phase 3 — Reporting

**T3.1 — HTML report + markdown summary.**
- Files: `gate/report.py`, `templates/report.html.j2`, `tests/test_report.py`.
- Done when: `report.html` is self-contained (inlined CSS, opens offline), shows verdict, per-gate
  table, current-vs-baseline diff, baseline age; markdown summary shares the same content; renders even
  on contract failure.
- Tests: render for each verdict type; assert key strings present; assert no external asset refs;
  assert webhook host string never appears.
- Reqs: F-06, N-04, "report always renders" (design §7).

---

## Phase 4 — CLI

**T4.1 — `run-gate`, `accept-baseline`, `validate-scorecard` entry points.**
- Files: `gate/cli.py`, `pyproject.toml` (`[project.scripts]`), `tests/test_cli.py`.
- Done when: `run-gate` wires read→validate→evaluate→regress→decide→report→exit; `accept-baseline`
  copies current→baseline with stamped `baseline_run_id`+date and never runs in a normal gate; an
  ordinary `run-gate` never mutates the baseline.
- Tests: end-to-end on pass/fail/incomplete/regression fixtures asserting exit codes + money-shot line;
  accept-baseline writes the file; run-gate leaves baseline untouched.
- Reqs: F-02–F-06, N-02.

---

## Phase 5 — CI surfaces

**T5.1 — Reusable workflow + composite action.**
- Files: `.github/workflows/eval-gate.yml` (`on: workflow_call`), `action.yml`,
  `examples/consumer-workflow.yml`.
- Done when: both delegate to `run-gate`; inputs `scorecard-path`/`gates-path`/`baseline-path` + optional
  `slack-webhook-url`; uploads `report.html` artifact.
- Tests: `examples/consumer-workflow.yml` green on a passing fixture, red on a failing one (verified via
  `act` locally or a throwaway consumer repo run).
- Reqs: F-09, F-06.

**T5.2 — Dogfood CI for this repo.**
- Files: `.github/workflows/ci.yml`, `eval-gates.yaml`, `baseline/scorecard.json`.
- Done when: this repo's own CI runs ruff+mypy+pytest then `run-gate` against bundled fixtures, proving
  green-on-pass and (informationally) the red money-shot — mirroring Project 1's `eval-gate.yml` pattern.
- Reqs: N-05.

---

## Phase 6 — Notify (last; optional, graceful)

**T6.1 — Slack notifier.**
- Files: `gate/notify.py`, `tests/test_notify.py` (mock POST).
- Done when: posts summary when `SLACK_WEBHOOK_URL` set; logs `skipped: no webhook` and exits correctly
  when unset; never logs the URL.
- Tests: mocked POST payload shape; no-webhook skip path; secret-hygiene assertion.
- Reqs: F-07, N-01, N-04.

**T6.2 — PR-comment upsert.**
- Files: `gate/notify.py` (PR-comment fn), `tests/test_notify.py`.
- Done when: posts/updates a single sticky comment (find-by-marker, edit-or-create) via the GitHub API
  using `GITHUB_TOKEN`; two runs → one comment; skips gracefully off-PR or token-less.
- Tests: mocked create vs update; off-PR skip.
- Reqs: F-08.

---

## Phase 7 — Onboard Project 1 (proof of reuse)

**T7.1 — Migrate Project 1 to the gate.**
- Files (in Project 1): scorecard emitter (+`schema_version`), `eval-gates.yaml` (from `src/config.py`),
  `.github/workflows/eval-gate.yml` (replace body with `uses:`), `baseline/scorecard.json`.
- Done when: Project 1 CI runs through the reusable gate; thresholds no longer hard-coded in Python;
  a deliberately-regressed metric blocks the PR.
- Reqs: F-09, F-04 (proven on a real consumer); ties Project 2 back to Project 1.

---

## Sequencing summary

```
T0.1 → T1.1 → T1.2 → T2.1 → T2.2 → T2.3 → T3.1 → T4.1 → T5.1 → T5.2 → T6.1 → T6.2 → T7.1
```
Minimum demoable slice (the headline): **T0.1 → T2.3 → T4.1 → T5.2** = a working config-driven,
regression-aware gate dogfooding itself in CI. Notify + multi-repo onboarding layer on after.
