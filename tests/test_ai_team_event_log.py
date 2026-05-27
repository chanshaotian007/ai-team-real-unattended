from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "ai_team_event_log.py"
SPEC = importlib.util.spec_from_file_location("ai_team_event_log", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_append_event_writes_jsonl(tmp_path: Path) -> None:
    log_path = tmp_path / "events.jsonl"
    event = MODULE.append_event(log_path, "worker_started", {"dispatch_id": "TASK-1#codex#1"})
    assert event["event_type"] == "worker_started"
    rows = log_path.read_text(encoding="utf-8").splitlines()
    saved = json.loads(rows[0])
    assert saved["payload"]["dispatch_id"] == "TASK-1#codex#1"
