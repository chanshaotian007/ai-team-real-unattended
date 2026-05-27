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


def test_reconcile_runtime_reports_cleanup_pending(tmp_path: Path) -> None:
    runtime_state = tmp_path / "runtime.json"
    event_log = tmp_path / "events.jsonl"
    MODULE.register_attempt(
        runtime_state,
        dispatch_id="TASK-3#codex#1",
        task_id="TASK-3",
        attempt_id="attempt-003",
        owner_role="backend-agent",
        worktree_path="/tmp/worktree-3",
        backend="simulation",
        status="cleanup_pending",
        heartbeat_at="2026-01-01T00:00:00+00:00",
    )
    args = type("Args", (), {"runtime_state": str(runtime_state), "event_log": str(event_log)})()
    payload = MODULE.reconcile_runtime(args)
    assert payload["status"] == "ok"
    assert payload["cleaned_tasks"] == ["TASK-3"]
