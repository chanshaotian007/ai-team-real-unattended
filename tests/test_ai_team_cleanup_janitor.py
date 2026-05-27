from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "ai_team_worker_supervisor.py"
SPEC = importlib.util.spec_from_file_location("ai_team_worker_supervisor", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_cleanup_janitor_clears_queue(tmp_path: Path) -> None:
    runtime_state = tmp_path / "runtime.json"
    event_log = tmp_path / "events.jsonl"
    MODULE.mark_cleanup(runtime_state, "TASK-5#codex#1", "lease_expired")
    args = type("Args", (), {"runtime_state": str(runtime_state), "event_log": str(event_log)})()
    payload = MODULE.cleanup_janitor(args)
    assert payload["status"] == "ok"
    assert payload["cleaned"][0]["dispatch_id"] == "TASK-5#codex#1"
    saved = json.loads(runtime_state.read_text(encoding="utf-8"))
    assert saved["cleanup_queue"] == []
