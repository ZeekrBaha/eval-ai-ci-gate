"""schema.py — scorecard contract (v1) validation.

The gate is SUT-agnostic because it depends on one artifact shape, not on any
harness's internals. This module is the gatekeeper for that shape.

Contract (see docs/implementation/scorecard-contract.md):
  - schema_version : str "major.minor"   (REQUIRED; same major = compatible)
  - run_id         : str                 (REQUIRED)
  - status         : str                 (REQUIRED; advisory, gate recomputes its own)
  - metric_summary : dict[str, float|int|None]  (REQUIRED; the comparison surface)
  Other fields (overall, dimensions, buckets, ...) are optional and ignored here.
"""

from __future__ import annotations

import math
from typing import Any

SUPPORTED_MAJOR = 1

REQUIRED_FIELDS = ("schema_version", "run_id", "status", "metric_summary")
KNOWN_STATUSES = ("PASS", "BLOCKED", "INCOMPLETE")


class ContractError(ValueError):
    """Raised when a scorecard does not conform to the v1 contract."""


def validate(scorecard: Any) -> None:
    """Validate *scorecard* against the v1 contract. Raise ContractError on any violation."""
    if not isinstance(scorecard, dict):
        raise ContractError(f"scorecard must be a JSON object, got {type(scorecard).__name__}")

    for field in REQUIRED_FIELDS:
        if field not in scorecard:
            raise ContractError(f"scorecard missing required field '{field}'")

    _validate_version(scorecard["schema_version"])

    if not isinstance(scorecard["run_id"], str):
        raise ContractError(
            f"run_id must be a string, got {type(scorecard['run_id']).__name__}"
        )

    status = scorecard["status"]
    if status not in KNOWN_STATUSES:
        raise ContractError(
            f"status must be one of {list(KNOWN_STATUSES)}, got {status!r}"
        )

    _validate_metric_summary(scorecard["metric_summary"])


def _validate_version(version: Any) -> None:
    if not isinstance(version, str):
        raise ContractError(f"schema_version must be a string, got {type(version).__name__}")
    parts = version.split(".")
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        raise ContractError(
            f"schema_version '{version}' is not exactly 'major.minor' (two integers)"
        )
    major = int(parts[0])
    if major != SUPPORTED_MAJOR:
        raise ContractError(
            f"unsupported scorecard schema_version '{version}': "
            f"this gate supports major version {SUPPORTED_MAJOR}"
        )


def _validate_metric_summary(metric_summary: Any) -> None:
    if not isinstance(metric_summary, dict):
        raise ContractError(
            f"metric_summary must be an object (metric -> number|null), "
            f"got {type(metric_summary).__name__}"
        )
    for name, value in metric_summary.items():
        if not isinstance(name, str):
            raise ContractError(
                f"metric name must be a string, got {type(name).__name__} ({name!r})"
            )
        # bool is a subclass of int — reject it explicitly; a gate metric is numeric or null.
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ContractError(
                f"metric_summary['{name}'] must be a number or null, "
                f"got {type(value).__name__}"
            )
        if not math.isfinite(float(value)):
            raise ContractError(
                f"metric_summary['{name}'] must be a finite number, got {value!r}"
            )
