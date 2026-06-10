"""history.py — optional JSONL trend history, one line appended per gate run.

Append-only so consumers accumulate history across runs (file and parent
directories are created on first write). Each line is a self-contained JSON
object: run_id, ISO-8601 UTC timestamp, verdict status/reason, and the
scorecard's metric summary.
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any

from gate.decide import Verdict


def append_history(
    path: Path, run_id: str, verdict: Verdict, metric_summary: dict[str, Any]
) -> None:
    """Append one JSON line describing this run to *path* (created if missing)."""
    entry = {
        "run_id": run_id,
        "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
        "status": verdict.status,
        "reason": verdict.reason,
        "metrics": metric_summary,
    }
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a") as fh:
        fh.write(json.dumps(entry, sort_keys=True) + "\n")
