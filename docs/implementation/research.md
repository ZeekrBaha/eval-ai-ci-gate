# Research — AI Evaluation CI/CD Pipeline (`eval-ai-ci-gate`)

**Project:** Project 2 of the AI Evaluation Portfolio.
**Owner:** Baha.
**Source plan:** `/Users/baha/Desktop/AI-Evaluation-Portfolio-5-Projects-Plan.md` (§ Project 2).

> This file captures facts and constraints only. Design decisions live in `design.md`.
> Each claim is tagged `Repository fact`, `Evidence`, or `Assumption`.

## 1. Goal

Turn an offline eval harness into a **release gate**: every prompt/model/config change runs
the full suite in CI and **blocks the merge** if any hard threshold is breached **or** if scores
**regress** beyond tolerance against a committed baseline. The gate must be **SUT-agnostic** so
Projects 1, 3, and 4 can all adopt it without copy-pasting CI logic.

One-line pitch: *"A reusable CI release gate for GenAI eval harnesses — config-driven hard
thresholds, regression-vs-baseline detection, an HTML report artifact, and Slack/PR-comment
surfacing. Drop it into any repo that emits a standard scorecard."*

## 2. Decisions already made (with the user, this session)

- **Packaging:** standalone repo `eval-ai-ci-gate` exposing a **reusable GitHub Actions workflow**
  + a **composite action** + shared scripts. Consumer repos (Projects 1/3/4) call it and emit a
  standard `scorecard.json`. *(Decision, locked.)*
- **Regression baseline:** a **committed `baseline/scorecard.json`** in each consumer repo, updated
  through an explicit "accept baseline" PR. Deterministic, diff-reviewable, offline-friendly.
  *(Decision, locked.)*

## 3. Existing assets — what already exists in Project 1 (reuse, do not rebuild)

Repo: `eval-financial-rag-evaluation-framework`.

- **Repository fact:** It already ships `.github/workflows/eval-gate.yml` — an offline gate that runs
  `uv sync --frozen` → `ruff check` → `mypy` → `pytest -q` → `make eval` → `make demo-block`. A hard-gate
  failure in `make eval` exits non-zero and fails the build.
- **Repository fact:** It has a working hard-gate engine at `src/eval/gates.py`
  (`evaluate_gates`, `decide_release`, `enforce`). Release states and exit codes:
  `PASS = 0`, `BLOCKED = 1`, `INCOMPLETE = 2` (a hard gate could not be evaluated → metric is `null`).
- **Repository fact:** Thresholds currently live in **Python** (`src/config.py`: `HARD_GATES`,
  `SOFT_GATES`, each a `{"metric", "threshold", "op"}` dict where `op ∈ {">=", "<="}`), not in a YAML file.
- **Repository fact:** Each run writes `reports/run-<ts>/` containing `scorecard.json`,
  `scorecard.html`, `REPORT.md`, and `run.log`.
- **Repository fact:** Stack is `uv` + Python 3.12, deps include `deepeval`, `ragas`, `pytest`.
  Tooling: `ruff`, `mypy`. Branches: `main`/`master`.

### Real `scorecard.json` shape (the integration contract is grounded in this)

```json
{
  "run_id": "run-20260606-175957",
  "mode": "replay",
  "status": "BLOCKED",
  "hard_gate_failures": ["faithfulness", "negative_rejection", "hallucination_rate"],
  "overall": 87.52,
  "dimensions": [ { "name": "...", "weight": 30, "score": 80.39, "status": "yellow", "metrics": { } } ],
  "buckets": { "factual_lookup": 0.333 },
  "metric_summary": {
    "faithfulness": 0.81, "hallucination_rate": 0.19, "negative_rejection": 0.667,
    "advice_boundary": 1.0, "answer_relevance": 0.867, "citation_validity": 0.798,
    "context_recall": 0.972, "context_precision": 0.944, "numerical_exactness": 0.938,
    "temporal_correctness": 0.667, "entity_disambiguation": 1.0, "injection_resistance": 1.0,
    "consistency_passk": null
  }
}
```

**Implication:** The reusable gate consumes `metric_summary` (the flat metric→value map) plus `status`.
That map, not the SUT internals, is the contract. Any harness that can emit this shape can be gated.

## 4. The genuine delta — what Project 2 adds beyond Project 1

| # | Capability | Status in Project 1 | Project 2 work |
|---|---|---|---|
| 1 | Hard-threshold gating | Exists (`gates.py`, Python config) | **Generalize:** read thresholds from `eval-gates.yaml`, not Python |
| 2 | Regression vs baseline | **Absent** | **Net-new:** diff `metric_summary` vs `baseline/scorecard.json`, fail on drop > tolerance |
| 3 | HTML report in CI | Per-run `scorecard.html` exists | **Add:** CI artifact + baseline-diff view, uploaded per run |
| 4 | Slack notifier | **Absent** | **Net-new:** post pass/fail summary via incoming webhook |
| 5 | PR-comment summary | **Absent** | **Net-new:** sticky PR comment with gate verdict + diffs |
| 6 | Reusability across repos | Embedded/SUT-specific | **Net-new:** reusable workflow + composite action + `scorecard.json` contract |

## 5. Constraints

- **Stack (Constraint):** Python 3.12 + `uv`, `ruff`, `mypy`, `pytest` — match Project 1 exactly so the
  gate's own dev loop mirrors the consumers it serves.
- **CI offline by default (Constraint):** the gate logic (threshold check + regression diff + report)
  must run with **no secrets and no network**. Slack/PR-comment posting is the only step needing a token,
  and it must **degrade gracefully** (skip, not fail) when the token is absent — so forks and offline runs
  still get a valid pass/fail.
- **Exit-code compatibility (Constraint):** preserve Project 1's contract — `0` PASS, `1` BLOCKED,
  `2` INCOMPLETE. Add nothing that breaks it. Regression failure maps to `1` (BLOCKED) with a distinct reason.
- **No client/secret leakage (Constraint):** Slack webhook URL and any tokens only via env/GitHub secrets;
  never written to logs, artifacts, or the report.
- **Honest framing (Constraint):** thresholds are *proposed*, calibrated against a stated baseline — never
  presented as a company's real internal gate. Carried over from the portfolio's honesty checklist.

## 6. Risks / unknowns

- **Assumption:** Projects 3 and 4 will emit the same `scorecard.json` shape. *Mitigation:* publish a
  versioned schema (`schema_version`) + a validator; consumers adapt their emitter to it.
- **Assumption:** GitHub-hosted runners are the target. Self-hosted runners are out of scope for v1.
- **Risk:** baseline staleness — a baseline that is never re-accepted hides slow erosion.
  *Mitigation:* record `baseline_run_id` + date in the report; warn when baseline age exceeds N days.
- **Risk:** flaky LLM-judge metrics cause false regression alarms. *Mitigation:* per-metric tolerance in
  `eval-gates.yaml`; regression compares against tolerance, not exact equality.
- **Unknown:** does each consumer run its suite inside its own repo (gate consumes the emitted artifact),
  or does the gate repo orchestrate the run? *Resolved in `design.md`:* consumer runs its own suite; the
  gate consumes the artifact. Keeps the gate SUT-agnostic.
