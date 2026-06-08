# Design — `eval-ai-ci-gate`

How the requirements become a system. No UI, so no design-system doc (infra/CLI project).

## 1. Mental model

```
consumer repo (Project 1/3/4)                 eval-ai-ci-gate (this repo)
─────────────────────────────                 ───────────────────────────
runs its own eval suite                        reusable workflow / composite action
        │ emits                                          │ pulls in
        ▼                                                ▼
  scorecard.json  ───────────(contract v1)─────────▶  gate engine
  baseline/scorecard.json ──────────────────────────▶   ├─ schema validate
  eval-gates.yaml ──────────────────────────────────▶   ├─ threshold check (hard/soft)
                                                         ├─ regression diff vs baseline
                                                         ├─ render report.html
                                                         ├─ notify (Slack, PR comment) — optional
                                                         └─ exit 0 / 1 / 2
```

The gate **never runs the SUT**. It consumes the artifact the consumer already produced. This is what
keeps it reusable across a RAG harness, an agent harness, and a chatbot harness alike.

## 2. Verdict logic (precedence — highest wins)

1. **Contract invalid** → exit `1`, reason `contract`. (Bad/missing `metric_summary`, wrong major version.)
2. **Hard gate failed** (an evaluated metric breaches its hard threshold) → `BLOCKED`, exit `1`,
   reason `hard_gate`.
3. **Regression** (any metric dropped > tolerance vs baseline) → `BLOCKED`, exit `1`, reason `regression`.
4. **Incomplete** (a hard-gated metric is `null`, nothing failed above) → `INCOMPLETE`, exit `2`,
   reason `incomplete`.
5. **Pass** (all hard gates evaluated + passed, no regression) → `PASS`, exit `0`. Soft-gate failures
   attach as **warnings** only.

Rounding: all displayed values to 3 dp for deterministic output (N-03), matching Project 1's convention.

## 3. `eval-gates.yaml` shape

Mirrors Project 1's `GateSpec` (`metric`/`threshold`/`op`) so migration is mechanical, and adds a
per-metric regression `tolerance`.

```yaml
schema_version: "1.0"
hard_gates:
  - { metric: faithfulness,        threshold: 0.95, op: ">=" }
  - { metric: negative_rejection,  threshold: 0.95, op: ">=" }
  - { metric: hallucination_rate,  threshold: 0.01, op: "<=" }
  - { metric: advice_boundary,     threshold: 1.00, op: ">=" }
soft_gates:
  - { metric: context_recall,      threshold: 0.90, op: ">=" }
  - { metric: answer_relevance,    threshold: 0.90, op: ">=" }
regression:
  default_tolerance: 0.02          # max allowed drop for any metric not listed below
  per_metric:
    hallucination_rate: 0.01       # for "<=" metrics, tolerance is max allowed INCREASE
    advice_boundary: 0.00          # zero tolerance — must not drop at all
  baseline_max_age_days: 30        # warn (not fail) when baseline is older than this
```

Direction-awareness: for `op: ">="` metrics a *drop* is bad; for `op: "<="` metrics (e.g.
`hallucination_rate`) an *increase* is bad. The regression check reads `op` to know which direction
counts as a regression.

## 4. Module layout (`gate/` package)

| Module | Responsibility |
|---|---|
| `gate/config.py` | Load + validate `eval-gates.yaml` into typed `GateSpec`/`RegressionSpec`. Fail fast on bad keys. |
| `gate/schema.py` | `validate(scorecard)` against the v1 contract; `ContractError`. |
| `gate/thresholds.py` | Hard/soft evaluation over `metric_summary`. Port of Project 1's `gates.py` logic, YAML-fed. |
| `gate/regression.py` | Diff current vs baseline `metric_summary`, direction-aware, per-metric tolerance. |
| `gate/decide.py` | Apply the §2 precedence → `Verdict{status, exit_code, reason, hard, soft, regressions, warnings}`. |
| `gate/report.py` | Render `report.html` (self-contained) + a markdown summary (reused by PR comment + Slack). |
| `gate/notify.py` | Slack webhook POST + PR-comment upsert. Both no-op gracefully without their token. |
| `gate/cli.py` | Entry points: `run-gate`, `accept-baseline`, `validate-scorecard`. |

Single small package, standard library + `pyyaml` + `jinja2` (report) + `requests` (notify). No framework.
Matches the "simplest solution that works" principle.

## 5. CLI surface

```
run-gate --scorecard PATH --gates eval-gates.yaml --baseline baseline/scorecard.json \
         --report-out report.html [--md-out summary.md]
         # exit 0/1/2 per §2; always writes the report.

accept-baseline --scorecard PATH --baseline-out baseline/scorecard.json
         # copies current -> baseline, stamps baseline_run_id + date. Used only in the accept-baseline PR.

validate-scorecard --scorecard PATH
         # contract check only; for consumers to self-test their emitter. exit 0/1.
```

## 6. CI surfaces this repo ships

- **`.github/workflows/eval-gate.yml`** — a **reusable** workflow (`on: workflow_call`) with inputs
  `scorecard-path`, `gates-path`, `baseline-path`, and secret `slack-webhook-url` (optional). Steps:
  checkout → `uv sync` → `run-gate` → upload `report.html` → notify. Consumers call it with `uses:`.
- **`action.yml`** — a **composite action** wrapping the same steps for repos that prefer a step over a
  reusable workflow.
- **`.github/workflows/ci.yml`** — this repo's own gate dogfooding: `ruff` + `mypy` + `pytest`, then
  `run-gate` against bundled pass/fail fixtures (proves green-on-pass, red-on-fail).
- **`examples/consumer-workflow.yml`** — copy-paste starter for Project 1/3/4.

## 7. Error handling & observability

- Every failure path prints a **single actionable line** first (the "money shot"), then details.
  Example: `Eval gate failed: faithfulness 0.93 < 0.95 (hard gate)`.
- The report always renders, even on contract failure (it shows the contract error), so a red CI run is
  never a blank artifact.
- Logs are structured-ish plain text; secret values are never interpolated into any string.

## 8. Reviewer pass (pre-implementation) — concerns raised & resolved

- *"Two ways to invoke (reusable workflow + composite action) doubles maintenance."* — Accepted cost:
  both delegate to the **same** `run-gate` CLI, so logic lives in one place; the YAML wrappers are thin.
- *"Trusting the consumer's `status` field?"* — No. Gate recomputes (§2 rule 4). `status` is display-only.
- *"Regression on LLM-judge noise."* — Mitigated by per-metric tolerance + `default_tolerance`, not exact
  equality. Documented as a known tuning surface.
- *"Baseline rot."* — `baseline_max_age_days` surfaces a warning in the report; not a hard fail (avoids
  blocking unrelated PRs on a calendar).
