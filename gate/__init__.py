"""eval-ai-ci-gate — a reusable CI release gate for GenAI eval harnesses.

Consumes a standard ``scorecard.json`` (see docs/implementation/scorecard-contract.md),
applies config-driven hard/soft thresholds and regression-vs-baseline detection, renders
an HTML report, and exits 0/1/2 (PASS/BLOCKED/INCOMPLETE).
"""

__version__ = "0.1.0"
