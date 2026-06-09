.PHONY: test typecheck lint check gate gate-fail accept-baseline

# ---------------------------------------------------------------------------
# test — full offline test suite (no secrets, no network).
# ---------------------------------------------------------------------------
test:
	uv run pytest

# ---------------------------------------------------------------------------
# typecheck — mypy (strict, configured in pyproject.toml) over gate AND tests.
# ---------------------------------------------------------------------------
typecheck:
	uv run mypy gate tests

# ---------------------------------------------------------------------------
# lint — ruff over the whole repo.
# ---------------------------------------------------------------------------
lint:
	uv run ruff check .

# ---------------------------------------------------------------------------
# check — the full local gate: lint + typecheck + tests (what CI runs offline).
# ---------------------------------------------------------------------------
check: lint typecheck test

# ---------------------------------------------------------------------------
# gate — run the release gate against this repo's own fixtures (dogfood).
# Passing scorecard + baseline -> RELEASE OK, exit 0.
# ---------------------------------------------------------------------------
gate:
	uv run run-gate \
		--scorecard tests/fixtures/pass.json \
		--gates eval-gates.yaml \
		--baseline baseline/scorecard.json \
		--report-out report.html

# ---------------------------------------------------------------------------
# gate-fail — the BLOCKED money-shot. Non-zero exit (1) is expected; prefix
# with - so make itself does not error.
# ---------------------------------------------------------------------------
gate-fail:
	-uv run run-gate \
		--scorecard tests/fixtures/fail.json \
		--gates eval-gates.yaml \
		--baseline baseline/scorecard.json \
		--report-out report.html

# ---------------------------------------------------------------------------
# accept-baseline — promote the current passing scorecard to the new baseline.
# Used only in an explicit "accept baseline" PR, never on a normal gate run.
# ---------------------------------------------------------------------------
accept-baseline:
	uv run accept-baseline \
		--scorecard tests/fixtures/pass.json \
		--baseline-out baseline/scorecard.json
