# Architecture — `eval-ai-ci-gate`

Complements `design.md` (which covers verdict logic + modules). This file covers repo layout, data flow,
dependencies, and how consumers integrate.

## 1. Repository layout

```
eval-ai-ci-gate/
├── gate/                       # the package (see design.md §4)
│   ├── __init__.py
│   ├── cli.py                  # run-gate / accept-baseline / validate-scorecard
│   ├── config.py               # load+validate eval-gates.yaml
│   ├── schema.py               # scorecard contract validation
│   ├── thresholds.py           # hard/soft evaluation
│   ├── regression.py           # baseline diff (direction-aware)
│   ├── decide.py               # precedence -> Verdict
│   ├── report.py               # report.html + markdown summary (jinja2)
│   └── notify.py               # slack + PR-comment upsert
├── templates/
│   └── report.html.j2          # self-contained report template (inlined CSS)
├── tests/
│   ├── fixtures/               # pass / fail / incomplete / regression scorecards + baselines
│   ├── test_thresholds.py
│   ├── test_regression.py
│   ├── test_decide.py
│   ├── test_schema.py
│   └── test_report.py
├── examples/
│   ├── consumer-workflow.yml   # copy-paste for Project 1/3/4
│   └── eval-gates.yaml         # annotated starter config
├── .github/workflows/
│   ├── eval-gate.yml           # REUSABLE (on: workflow_call) — the product
│   └── ci.yml                  # this repo's own dogfooding gate
├── action.yml                  # composite action wrapper
├── eval-gates.yaml             # this repo's own gate config (dogfood)
├── baseline/scorecard.json     # this repo's own baseline (dogfood)
├── Makefile                    # check / test / lint / typecheck / gate / accept-baseline
├── pyproject.toml              # uv-managed; deps: pyyaml, jinja2, requests; dev: ruff, mypy, pytest
├── uv.lock
├── README.md                   # pitch + red-PR screenshot + onboarding steps
└── docs/                       # this package
```

## 2. Data flow (single CI run in a consumer repo)

```
1. consumer eval suite      -> writes scorecard.json (contract v1)
2. consumer workflow calls  -> uses: .../eval-gate.yml@v1 (passes paths + optional webhook secret)
3. run-gate:
     read eval-gates.yaml ──┐
     read scorecard.json  ──┼─> schema.validate ─> thresholds.evaluate ─> regression.diff(baseline)
     read baseline.json   ──┘                                   │
                                                                ▼
                                                   decide.verdict (precedence)
                                                                │
                          ┌─────────────────────────────────────┼───────────────────────┐
                          ▼                                     ▼                         ▼
                  report.html (artifact)              PR comment (upsert)         Slack (if webhook)
                          │
                          ▼
                  process exit 0 / 1 / 2  -> CI green/red
```

## 3. Dependencies & rationale

| Dep | Why | Alternative rejected |
|---|---|---|
| `pyyaml` | parse `eval-gates.yaml` | — |
| `jinja2` | render self-contained HTML report | hand-rolled string templating (brittle) |
| `requests` | Slack POST + GitHub PR-comment API | stdlib `urllib` (workable; `requests` clearer, already common in Project 1's orbit) |
| dev: `ruff`, `mypy`, `pytest` | match Project 1's quality bar (N-05) | — |

Deliberately **no** web framework, no DB, no async. The gate is a short-lived CLI invoked by CI.

## 4. Integration topology (how the 3 consumers attach)

- **Project 1 (financial RAG):** add `schema_version` to its emitter; replace its bespoke
  `eval-gate.yml` body with a `uses:` call to the reusable workflow; migrate `src/config.py` thresholds
  into `eval-gates.yaml`. Net: less code in Project 1, gate logic centralized here.
- **Project 3 (agent eval):** author its scorecard emitter to the contract from day one; supply its own
  `eval-gates.yaml` (agent metrics: tool_selection, parameter_accuracy, injection_resistance, …).
- **Project 4 (chatbot QA):** same — emit contract scorecard, supply chatbot `eval-gates.yaml`
  (multi_turn_consistency, persona_adherence, toxicity, …).

The gate cares about none of these metric names specifically — they are just keys in `metric_summary`
matched against keys in that repo's `eval-gates.yaml`. That indifference is the architecture's whole point.

## 5. Versioning & release

- Tag releases `v1`, `v1.1`, … Consumers pin `@v1` (moving major tag) per GitHub Actions convention.
- `schema_version` in the scorecard contract is independent of the action's release tag; the gate
  declares which contract majors it supports.

## 6. Security boundaries

- Secrets (`SLACK_WEBHOOK_URL`, `GITHUB_TOKEN` for PR comments) enter only as GitHub Actions
  secrets/inputs, consumed by `notify.py`, never logged, never written to the artifact (N-04).
- The gate reads only the three input files + env; it performs no network I/O except the optional
  notify POSTs. Offline core (N-01) means a leaked/empty secret degrades to "skip notify", not failure.
