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


def test_reconcile_runtime_schedules_retry_for_expired_attempt(tmp_path: Path) -> None:
    runtime_state = tmp_path / "runtime.json"
    event_log = tmp_path / "events.jsonl"
    MODULE.register_attempt(
        runtime_state,
        dispatch_id="TASK-4#codex#1",
        task_id="TASK-4",
        attempt_id="attempt-004",
        owner_role="backend-agent",
        worktree_path="/tmp/worktree-4",
        backend="simulation",
        status="running",
        heartbeat_at="2026-01-01T00:00:00+00:00",
        lease_expires_at="2000-01-01T00:00:00+00:00",
        retry_count=0,
        max_attempts=2,
    )
    args = type(
        "Args",
        (),
        {
            "runtime_state": str(runtime_state),
            "event_log": str(event_log),
            "artifact_root": str(tmp_path / "artifacts"),
            "worktree_root": str(tmp_path),
            "dispatches_file": "",
            "notifications_file": "",
            "state_file": "",
            "broker_state": "",
            "role": "backend-agent",
        },
    )()
    payload = MODULE.reconcile_runtime(args)
    assert payload["status"] == "ok"
    assert payload["retries"][0]["task_id"] == "TASK-4"
    assert payload["retries"][0]["retry_count"] == 1
    saved = json.loads(runtime_state.read_text(encoding="utf-8"))
    assert saved["workers"]["TASK-4"]["status"] == "retry_scheduled"
    assert saved["workers"]["TASK-4"]["retry_count"] == 1
