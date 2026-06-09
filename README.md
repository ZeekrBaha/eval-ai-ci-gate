# Eval AI CI Gate

> **One sentence:** a reusable CI release gate for GenAI eval harnesses — it reads a standard
> `scorecard.json`, enforces **config-driven hard thresholds**, detects **regression against a
> committed baseline**, renders a self-contained **HTML report**, and **exits non-zero** (blocking
> the merge) when a hard gate fails or a metric regresses beyond tolerance.

> **Status (measured, offline):** core pipeline complete and verified — `make check` is green
> (**ruff** clean, **mypy --strict** clean, **107 tests pass**), and all five verdict paths run
> end-to-end with the right exit codes:
> `make gate` → PASS (exit 0), `make gate-fail` → BLOCKED (exit 1).
>
> **Implemented now:** the scorecard contract + validator · YAML-driven hard/soft thresholds ·
> direction-aware regression-vs-baseline · the verdict precedence engine · the self-contained HTML
> report + markdown summary · the `run-gate` / `accept-baseline` / `validate-scorecard` CLI ·
> graceful Slack + sticky-PR-comment notifiers · the composite action + reusable workflow · this
> repo dogfooding its own gate in CI. **Project 1 (`eval-financial-rag-evaluation-framework`) is
> onboarded** — its scorecard emits `schema_version`, its thresholds live in `eval-gates.yaml`, and
> its real PASS scorecard clears the gate.
>
> **Not yet wired (next):** a historical trend DB / dashboard (single-run report only for now).

> **What this is (and isn't):** Project 2 of an AI-evaluation portfolio. It is the **infrastructure**
> half — the thing that turns an eval harness into a release decision. It deliberately **does not run
> the system under test**; it consumes the `scorecard.json` the harness already emits, which is what
> makes it reusable across a RAG harness, an agent harness, and a chatbot harness alike. Every
> threshold here is a **proposed** starting gate — calibrate against your own baseline.

If reading cold, start with **§1 Mental model** and **§3 The money shot**.

---

## 1. Mental model

```
consumer repo (Project 1/3/4)                 eval-ai-ci-gate (this repo)
─────────────────────────────                 ───────────────────────────
runs its own eval suite                        reusable workflow / composite action
        │ emits                                          │ pulls in
        ▼                                                ▼
  scorecard.json  ───────────(contract v1)─────────▶  run-gate
  baseline/scorecard.json ──────────────────────────▶   ├─ validate contract
  eval-gates.yaml ──────────────────────────────────▶   ├─ check hard/soft thresholds
                                                         ├─ diff vs baseline (regression)
                                                         ├─ render report.html
                                                         └─ exit 0 / 1 / 2
```

The gate cares about exactly one artifact — `scorecard.json` — not about how the harness produced it.

## 2. Why it exists (the delta over an embedded gate)

Project 1 already had an in-repo gate. This project generalizes it so any eval harness can adopt it:

| Capability | Before (embedded in Project 1) | Here |
|---|---|---|
| Hard-threshold gating | thresholds hard-coded in Python | **`eval-gates.yaml`**, no code edit |
| Regression vs baseline | absent | **direction-aware diff** vs committed baseline |
| HTML report | per-run only | **CI artifact**, with baseline-diff + age |
| Reuse across repos | copy-paste CI | **reusable workflow + composite action** + a versioned scorecard contract |

## 3. The money shot

```console
$ make gate          # passing scorecard
Eval gate passed                                              # exit 0

$ make gate-fail     # a regressed prompt/model
Eval gate failed: faithfulness 0.93 < 0.95 (hard gate)        # exit 1
```

Regression and incomplete paths are first-class too:

```console
Eval gate failed: answer_relevance dropped 0.08 vs baseline 0.93 (tolerance 0.02) (regression)  # exit 1
Eval gate incomplete: faithfulness not evaluated                                                # exit 2
```

Exit codes match Project 1's contract: **0 = PASS, 1 = BLOCKED, 2 = INCOMPLETE**.

## 4. Verdict precedence

Highest wins: **contract → hard_gate → regression → incomplete → pass**. A `null` (unevaluated)
hard-gated metric yields INCOMPLETE — never PASS. Soft-gate failures are **warnings only**; they
never block. A missing **or invalid** required baseline yields INCOMPLETE (you cannot certify "no
regression" against a baseline that is absent or not a valid scorecard — it is never silently
skipped). Operational problems — bad YAML, missing/invalid scorecard or baseline JSON, a gate
referencing a metric the scorecard never emits — are **caught and turned into a deterministic
report + exit code**, never an uncaught stack trace.

## 5. `eval-gates.yaml`

```yaml
schema_version: "1.0"
hard_gates:
  - { metric: faithfulness,       threshold: 0.95, op: ">=" }
  - { metric: hallucination_rate, threshold: 0.01, op: "<=" }   # lower is better
soft_gates:
  - { metric: answer_relevance,   threshold: 0.90, op: ">=" }
regression:
  default_tolerance: 0.02       # max allowed adverse change vs baseline
  per_metric:
    hallucination_rate: 0.01    # for "<=" metrics, tolerance caps the allowed INCREASE
    advice_boundary: 0.00       # zero tolerance — must not slip at all
  baseline_max_age_days: 30     # baseline older than this -> a non-blocking note in the report
  require_baseline: true        # with --baseline, a missing baseline -> INCOMPLETE (not a silent pass)
```

Regression is **direction-aware**: a `>=` metric regresses on a *drop*; a `<=` metric regresses on
an *increase*. The gate reads each metric's `op` to decide which way is bad. Comparisons decide on
the **exact** value (rounding is display-only), so a `0.9495` cannot slip past a `0.95` gate.

## 6. The scorecard contract (v1)

The gate consumes any JSON with `schema_version`, `run_id`, `status`, and a flat `metric_summary`
(`metric → number | null`). `null` means "not evaluated". Full spec:
[`docs/implementation/scorecard-contract.md`](docs/implementation/scorecard-contract.md).
Onboarding Project 1 requires only adding `"schema_version": "1.0"` to its existing emitter.

## 7. How to run

```bash
uv sync
make check            # ruff + mypy --strict + pytest (107 tests)

# Run the gate directly
uv run run-gate \
  --scorecard path/to/scorecard.json \
  --gates eval-gates.yaml \
  --baseline baseline/scorecard.json \
  --report-out report.html --md-out summary.md

# Promote the current scorecard to the new baseline (explicit; in an "accept baseline" PR)
uv run accept-baseline --scorecard scorecard.json --baseline-out baseline/scorecard.json

# Let a consumer self-test its emitter against the contract
uv run validate-scorecard --scorecard scorecard.json
```

In a consumer repo, run your eval suite then call the gate via the **composite action** in the
same job, so it sees the freshly produced `scorecard.json` (see
[`examples/consumer-workflow.yml`](examples/consumer-workflow.yml)):

```yaml
jobs:
  gate:
    runs-on: ubuntu-latest
    permissions: { contents: read, pull-requests: write }
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv sync --frozen
      - run: make eval && cp "$(ls -dt reports/run-* | head -1)/scorecard.json" scorecard.json
      - uses: ZeekrBaha/eval-ai-ci-gate@v1
        with:
          scorecard-path: scorecard.json
          gates-path: eval-gates.yaml
          baseline-path: baseline/scorecard.json
        env:
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}   # optional
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}             # enables the sticky PR comment
```

> A reusable workflow (`.github/workflows/eval-gate.yml`) is also provided, but it runs as its
> own job and only sees a scorecard that is committed to the repo. For the common case where the
> scorecard is generated in CI, use the composite action above.

## 8. Repo map

| Path | What it is |
|---|---|
| `gate/schema.py` | scorecard contract (v1) validation |
| `gate/config.py` | load + validate `eval-gates.yaml` into typed specs |
| `gate/thresholds.py` | hard/soft threshold evaluation over `metric_summary` |
| `gate/regression.py` | direction-aware diff vs baseline |
| `gate/decide.py` | verdict precedence → `Verdict` + exit code |
| `gate/report.py` | self-contained HTML report + markdown summary |
| `gate/cli.py` | `run-gate` / `accept-baseline` / `validate-scorecard` |
| `.github/workflows/eval-gate.yml` | the reusable workflow (the product) |
| `action.yml` | composite-action wrapper |
| `.github/workflows/ci.yml` | this repo dogfooding its own gate |
| `examples/` | consumer workflow + starter `eval-gates.yaml` |
| `tests/` | 107 tests (one suite per module) |
| `docs/implementation/` | research, requirements, design, architecture, plan, validation |

## 9. Tech stack

Python 3.12 · `uv` · `pyyaml` · `jinja2` · `ruff` · `mypy --strict` · `pytest` · GitHub Actions.
Notifiers add `requests` (optional extra). No web framework, no DB — the gate is a short-lived CLI.

## 10. Limitations / next steps

- **`v1` tag required for consumers.** The composite action is referenced as `@v1`; that tag must
  exist before a consumer's CI can resolve it. Until tagged, pin a commit SHA.
- **Single-run only.** No historical trend DB / dashboard — out of scope for v1.
- **Notifier HTTP paths are mock-tested.** Slack/PR-comment logic is unit-tested with injected
  HTTP; the live POST paths run only in real CI (graceful skip without a webhook/token).
- Built and tested TDD: every module had a failing test first (**107 tests**). See `docs/implementation/`.
