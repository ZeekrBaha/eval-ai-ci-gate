# Scorecard Contract (v1) — the integration linchpin

The gate is SUT-agnostic because it depends on **one artifact**, not on any harness's internals.
Any repo that emits a conforming `scorecard.json` can be gated. This file is the source of truth for
that shape; `requirements.md` C-01/C-02 reference it.

## Required shape

```jsonc
{
  "schema_version": "1.0",          // REQUIRED. Major version gates compatibility (C-02).
  "run_id": "run-20260606-175957",  // REQUIRED. Opaque, unique per run.
  "status": "BLOCKED",              // REQUIRED. PASS | BLOCKED | INCOMPLETE — the SUT's own verdict.
  "metric_summary": {               // REQUIRED. Flat metric -> float | null. THE comparison surface.
    "faithfulness": 0.81,
    "hallucination_rate": 0.19,
    "answer_relevance": 0.867,
    "consistency_passk": null       // null = not evaluated -> drives INCOMPLETE, never blocks/regresses.
  },

  // OPTIONAL — surfaced in the report if present, ignored by gate logic otherwise.
  "overall": 87.52,
  "mode": "replay",
  "hard_gate_failures": ["faithfulness"],
  "dimensions": [ /* name, weight, score, status, metrics */ ],
  "buckets": { "factual_lookup": 0.333 }
}
```

## Rules

1. **`metric_summary` is the only field gate logic reads for verdicts.** Thresholds (`eval-gates.yaml`)
   and the baseline diff both operate on this flat map. Everything else is presentation.
2. **`null` means "not evaluated".** A `null` hard-gated metric → `INCOMPLETE` (never `PASS`, never a
   regression hit). A `null` baseline value for a metric → that metric is skipped in the regression diff.
3. **Metric names are stable identifiers.** They must match the `metric:` keys in `eval-gates.yaml`.
   A threshold referencing a metric absent from `metric_summary` is a configuration error (fail fast).
4. **`status` is advisory.** The gate recomputes its own verdict from thresholds + regression; it does
   **not** trust the SUT's `status` blindly. `status` is shown in the report for cross-checking.
5. **`schema_version` uses major.minor.** Same major = compatible (new optional fields allowed).
   Different major = the gate fails fast (C-02).

## Compatibility with Project 1

Project 1 already emits every REQUIRED field except `schema_version`. The only consumer-side change to
onboard Project 1 is **adding `"schema_version": "1.0"`** to its scorecard emitter. No restructuring.
Projects 3 and 4 author their emitters to this contract from the start.

## Validation

`gate/schema.py` provides `validate(scorecard: dict) -> None` raising `ContractError` with a precise
message (missing field, bad type, unsupported major version). Run in the gate before any threshold logic,
and exposed as a standalone `validate-scorecard` entry point so consumers can self-check in their own CI.
