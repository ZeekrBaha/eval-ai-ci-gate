"""report.py — render a gate Verdict as a self-contained HTML report + a markdown summary.

The HTML inlines all CSS (no external assets) so it opens offline as a CI artifact, and
the markdown summary is reused by the Slack and PR-comment notifiers. Both are deterministic:
same Verdict + metadata -> identical bytes. The renderer is given only a Verdict and run
metadata, never a secret — secrets cannot leak into the report.
"""

from __future__ import annotations

from jinja2 import Template

from gate.decide import Verdict

_STATUS_BADGE = {"PASS": "✅ PASS", "BLOCKED": "⛔ BLOCKED", "INCOMPLETE": "⚠️ INCOMPLETE"}


def render_markdown(
    verdict: Verdict,
    *,
    scorecard_run_id: str,
    baseline_run_id: str | None = None,
    baseline_age_days: int | None = None,
) -> str:
    """Render a markdown summary (used by PR comment + Slack)."""
    lines: list[str] = [
        f"### {_STATUS_BADGE.get(verdict.status, verdict.status)}",
        "",
        f"**{verdict.headline}**",
        "",
        f"- Status: `{verdict.status}` (exit {verdict.exit_code}, reason `{verdict.reason}`)",
        f"- Scorecard: `{scorecard_run_id}`",
    ]
    if baseline_run_id is not None:
        age = f" ({baseline_age_days} days old)" if baseline_age_days is not None else ""
        lines.append(f"- Baseline: `{baseline_run_id}`{age}")
    lines.append("")

    lines.append("| Gate | Metric | Value | Op | Threshold | Result |")
    lines.append("|---|---|---|---|---|---|")
    for r in verdict.hard:
        lines.append(
            f"| hard | {r.metric} | {_fmt(r.value)} | `{r.op}` | "
            f"{round(r.threshold, 3)} | {r.status} |"
        )
    for r in verdict.soft:
        lines.append(
            f"| soft | {r.metric} | {_fmt(r.value)} | `{r.op}` | "
            f"{round(r.threshold, 3)} | {r.status} |"
        )

    if verdict.notes:
        lines += ["", "**Notes:**"]
        lines += [f"- {n}" for n in verdict.notes]
    if verdict.regressions:
        lines += ["", "**Regressions vs baseline:**"]
        lines += [f"- {r.message}" for r in verdict.regressions]
    if verdict.warnings:
        lines += ["", "**Soft-gate warnings (non-blocking):**"]
        lines += [f"- {r.message}" for r in verdict.warnings]
    return "\n".join(lines) + "\n"


def render_html(
    verdict: Verdict,
    *,
    scorecard_run_id: str,
    baseline_run_id: str | None = None,
    baseline_age_days: int | None = None,
) -> str:
    """Render a self-contained HTML report (inline CSS, no external assets)."""
    return _HTML_TEMPLATE.render(
        v=verdict,
        badge=_STATUS_BADGE.get(verdict.status, verdict.status),
        scorecard_run_id=scorecard_run_id,
        baseline_run_id=baseline_run_id,
        baseline_age_days=baseline_age_days,
        fmt=_fmt,
        round3=lambda x: round(x, 3),
    )


def _fmt(value: float | None) -> str:
    return "n/a" if value is None else str(round(value, 3))


_COLOR = {"PASS": "#1a7f37", "BLOCKED": "#cf222e", "INCOMPLETE": "#9a6700"}

# Inline-CSS template. No <link>, no <script src>, no <img> — opens offline.
_HTML_TEMPLATE = Template(
    """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Eval Gate Report - {{ v.status }}</title>
<style>
  body { font-family: -apple-system, system-ui, sans-serif; margin: 2rem; color: #1f2328;
         background: #f6f8fa; }
  .card { background: #fff; border: 1px solid #d0d7de; border-radius: 6px; padding: 1.5rem;
          max-width: 880px; margin: 0 auto; }
  .status { font-size: 1.4rem; font-weight: 700;
            color: {{ {"PASS":"#1a7f37","BLOCKED":"#cf222e","INCOMPLETE":"#9a6700"}[v.status] }}; }
  .headline { font-size: 1.05rem; margin: .5rem 0 1rem; }
  .meta { color: #57606a; font-size: .9rem; margin-bottom: 1rem; }
  table { border-collapse: collapse; width: 100%; margin-top: .5rem; }
  th, td { border: 1px solid #d0d7de; padding: .4rem .6rem; text-align: left; font-size: .9rem; }
  th { background: #f6f8fa; }
  .fail { color: #cf222e; font-weight: 600; }
  .pass { color: #1a7f37; }
  .unevaluated { color: #9a6700; }
  h2 { font-size: 1rem; margin-top: 1.4rem; }
  .note { color: #57606a; font-size: .85rem; }
</style>
</head>
<body>
<div class="card">
  <div class="status">{{ badge }}</div>
  <div class="headline">{{ v.headline }}</div>
  <div class="meta">
    exit {{ v.exit_code }} &middot; reason {{ v.reason }} &middot; scorecard {{ scorecard_run_id }}
    {%- if baseline_run_id %} &middot; baseline {{ baseline_run_id }}
      {%- if baseline_age_days is not none %} ({{ baseline_age_days }} days old){% endif -%}
    {% endif %}
  </div>

  <h2>Threshold gates</h2>
  <table>
    <tr><th>Gate</th><th>Metric</th><th>Value</th><th>Op</th><th>Threshold</th><th>Result</th></tr>
    {%- for r in v.hard %}
    <tr><td>hard</td><td>{{ r.metric }}</td><td>{{ fmt(r.value) }}</td><td>{{ r.op }}</td>
        <td>{{ round3(r.threshold) }}</td><td class="{{ r.status }}">{{ r.status }}</td></tr>
    {%- endfor %}
    {%- for r in v.soft %}
    <tr><td>soft</td><td>{{ r.metric }}</td><td>{{ fmt(r.value) }}</td><td>{{ r.op }}</td>
        <td>{{ round3(r.threshold) }}</td><td class="{{ r.status }}">{{ r.status }}</td></tr>
    {%- endfor %}
  </table>

  {%- if v.notes %}
  <h2>Notes</h2>
  <ul>{% for n in v.notes %}<li class="unevaluated">{{ n }}</li>{% endfor %}</ul>
  {%- endif %}

  {%- if v.regressions %}
  <h2>Regressions vs baseline</h2>
  <ul>{% for r in v.regressions %}<li class="fail">{{ r.message }}</li>{% endfor %}</ul>
  {%- endif %}

  {%- if v.warnings %}
  <h2>Soft-gate warnings (non-blocking)</h2>
  <ul>{% for r in v.warnings %}<li class="unevaluated">{{ r.message }}</li>{% endfor %}</ul>
  {%- endif %}

  <p class="note">Thresholds are proposed and calibrated against a stated baseline - not a
  certified production gate. Generated by eval-ai-ci-gate.</p>
</div>
</body>
</html>
""",
    autoescape=True,
)
