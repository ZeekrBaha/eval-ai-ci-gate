# Agent Assignments — `eval-ai-ci-gate`

Maps the implementation plan to roles for a multi-agent (or multi-session) build. Each role works only
from the approved docs and reports changed files + command results back to the Team Lead.

| Phase / Task | Owner role | Reviewer | Notes |
|---|---|---|---|
| T0.1 Scaffold | Developer | Team Lead | tooling must match Project 1 (`uv`, ruff, mypy, pytest) |
| T1.1 Schema | Developer | Reviewer | contract is the linchpin — review carefully |
| T1.2 Config loader | Developer | Reviewer | fail-fast messages must name the bad key |
| T2.1 Thresholds | Developer | Reviewer | faithful port of Project 1 `gates.py` semantics |
| T2.2 Regression | Developer | Reviewer + Tester | direction-awareness is the subtle bug surface |
| T2.3 Decide | Developer | Reviewer | precedence order is correctness-critical |
| T3.1 Report | Developer | Reviewer | self-contained HTML; secret hygiene |
| T4.1 CLI | Developer | Tester | exit codes + accept-baseline safety |
| T5.1 Reusable workflow + action | Developer | Team Lead | both delegate to one CLI |
| T5.2 Dogfood CI | Developer | Team Lead | mirrors Project 1's eval-gate.yml |
| T6.1 Slack | Junior Developer | Reviewer | graceful skip; secret hygiene |
| T6.2 PR comment | Developer | Reviewer | sticky upsert, not append |
| T7.1 Onboard Project 1 | Developer | Team Lead + Reviewer | the real-world reuse proof |
| All phases | Tester | — | owns `validation-plan.md` execution + `validation-report.md` |

## Working agreement

- **Scope discipline:** a role touches only the files its task names. Cross-cutting changes go back to
  the Team Lead.
- **Tests first where practical:** logic tasks (T2.*) write the failing test before the implementation.
- **No invented rules:** any ambiguity in thresholds/contract is escalated, not guessed.
- **Report format:** every handoff lists changed files + the exact commands run with pass/fail summaries.

## Prompts

Role prompts live in `docs/prompts/`: `team-lead.md`, `developer.md`, `tester.md`, `reviewer.md`.
(A junior-developer prompt reuses `developer.md` with scope narrowed to T6.1.)
