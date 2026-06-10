"""Trend history — append-only JSONL written by gate/history.py."""

import datetime
import json
from pathlib import Path

from gate.decide import Verdict
from gate.history import append_history


def _verdict() -> Verdict:
    return Verdict(status="PASS", exit_code=0, reason="pass", headline="Eval gate passed")


def test_append_creates_file_with_one_entry(tmp_path: Path) -> None:
    out = tmp_path / "history.jsonl"
    append_history(out, "run-1", _verdict(), {"faithfulness": 0.96})
    lines = out.read_text().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["run_id"] == "run-1"
    assert entry["status"] == "PASS"
    assert entry["reason"] == "pass"
    assert entry["metrics"] == {"faithfulness": 0.96}


def test_append_accumulates_instead_of_overwriting(tmp_path: Path) -> None:
    out = tmp_path / "history.jsonl"
    append_history(out, "run-1", _verdict(), {})
    append_history(out, "run-2", _verdict(), {})
    entries = [json.loads(line) for line in out.read_text().splitlines()]
    assert [e["run_id"] for e in entries] == ["run-1", "run-2"]


def test_timestamp_is_iso_utc(tmp_path: Path) -> None:
    out = tmp_path / "history.jsonl"
    append_history(out, "run-1", _verdict(), {})
    entry = json.loads(out.read_text())
    ts = datetime.datetime.fromisoformat(entry["timestamp"])
    assert ts.tzinfo is not None
    assert ts.utcoffset() == datetime.timedelta(0)


def test_append_creates_missing_parent_directories(tmp_path: Path) -> None:
    out = tmp_path / "nested" / "history.jsonl"
    append_history(out, "run-1", _verdict(), {})
    assert out.exists()
