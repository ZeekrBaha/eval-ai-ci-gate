# Developer Prompt — `eval-ai-ci-gate`

You are implementing one task from `docs/implementation/implementation-plan.md` in the
`eval-ai-ci-gate` repo. Work only from the approved docs.

## Read first
- `docs/implementation/design.md` (verdict logic §2, module layout §4, CLI §5)
- `docs/implementation/architecture.md` (repo layout, dependencies)
- `docs/implementation/scorecard-contract.md` (the v1 contract — do not deviate)
- The specific task in `implementation-plan.md` you were assigned.

## Rules
- **Scope:** touch only the files your task names. No drive-by refactors, no speculative abstraction.
  Write the simplest code that passes the acceptance criteria.
- **Stack:** Python 3.12, `uv`, std lib + `pyyaml` + `jinja2` + `requests` only. No web framework, no DB,
  no async. Match Project 1's conventions.
- **Tests:** for logic tasks (T2.*), write the failing test first, then implement. Every module gets a
  matching `tests/test_*.py`.
- **Determinism:** round displayed metric values to 3 decimal places; keep key ordering stable.
- **Exit codes:** preserve `0 = PASS`, `1 = BLOCKED`, `2 = INCOMPLETE`. Never invent new codes.
- **Secret hygiene:** never interpolate a webhook URL or token into any logged or rendered string.
- **Contract trust:** recompute the verdict from thresholds + regression; never trust the scorecard's own
  `status` field for the decision.

## Done means
1. Acceptance criteria in your task are met.
2. `make check` (ruff + mypy + pytest) is green.
3. You report: list of changed files, exact commands run, and their pass/fail summaries.

If a business rule (a threshold, a contract field, a tolerance) is unclear, **stop and escalate** to the
Team Lead. Do not guess.
