"""T3.1 — report rendering (HTML + markdown). See docs/implementation/design.md §4, validation §3."""

import html as _html

from gate.decide import Verdict, decide
from gate.regression import RegressionResult
from gate.report import render_html, render_markdown
from gate.thresholds import GateResult

WEBHOOK = "hooks.slack.com"


def _hard(metric: str, status: str) -> GateResult:
    return GateResult(metric, ">=", 0.95, 0.9 if status == "fail" else 0.99, status)  # type: ignore[arg-type]


def _pass() -> Verdict:
    return decide([_hard("faithfulness", "pass")], [], [])


def _blocked() -> Verdict:
    return decide([_hard("faithfulness", "fail")], [], [])


def _regressed() -> Verdict:
    reg = RegressionResult("answer_relevance", ">=", 0.85, 0.90, 0.02, 0.05, True)
    return decide([_hard("faithfulness", "pass")], [], [reg])


def _incomplete() -> Verdict:
    return decide([_hard("consistency_passk", "unevaluated")], [], [])


def test_markdown_contains_headline_and_status() -> None:
    md = render_markdown(_blocked(), scorecard_run_id="run-1")
    assert "Eval gate failed: faithfulness 0.9 < 0.95 (hard gate)" in md
    assert "BLOCKED" in md


def test_markdown_renders_for_every_verdict_type() -> None:
    for v in (_pass(), _blocked(), _regressed(), _incomplete()):
        md = render_markdown(v, scorecard_run_id="run-1")
        assert v.status in md
        assert v.headline in md


def test_html_renders_for_every_verdict_type() -> None:
    for v in (_pass(), _blocked(), _regressed(), _incomplete()):
        html = render_html(v, scorecard_run_id="run-1")
        assert "<html" in html.lower()
        # Headline is HTML-escaped (it may contain < or >); assert the escaped form.
        assert _html.escape(v.headline) in html


def test_html_is_self_contained_no_external_assets() -> None:
    html = render_html(_pass(), scorecard_run_id="run-1")
    assert "<link" not in html.lower()  # no external stylesheet
    assert "src=" not in html.lower()  # no external script/img
    assert "http://" not in html and "https://" not in html


def test_html_shows_baseline_age() -> None:
    html = render_html(_pass(), scorecard_run_id="run-1", baseline_run_id="run-0", baseline_age_days=12)
    assert "run-0" in html
    assert "12" in html


def test_render_is_deterministic() -> None:
    a = render_html(_regressed(), scorecard_run_id="run-1")
    b = render_html(_regressed(), scorecard_run_id="run-1")
    assert a == b


def test_no_secret_leak_in_output() -> None:
    # The renderer is given only a verdict + metadata, never a secret; prove it stays out.
    md = render_markdown(_blocked(), scorecard_run_id="run-1")
    html = render_html(_blocked(), scorecard_run_id="run-1")
    assert WEBHOOK not in md
    assert WEBHOOK not in html
