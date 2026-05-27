from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "ai_team_runtime_state.py"
SPEC = importlib.util.spec_from_file_location("ai_team_runtime_state", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_register_attempt_and_cleanup(tmp_path: Path) -> None:
    state_path = tmp_path / "runtime.json"
    payload = MODULE.register_attempt(
        state_path,
        dispatch_id="TASK-1#codex#1",
        task_id="TASK-1",
        attempt_id="attempt-001",
        owner_role="backend-agent",
        worktree_path="/tmp/worktree",
        backend="simulation",
        status="preparing_workspace",
        heartbeat_at="2026-01-01T00:00:00+00:00",
        lease_expires_at="2026-01-01T00:10:00+00:00",
        retry_count=0,
        max_attempts=2,
    )

    assert payload["task_id"] == "TASK-1"
    saved = MODULE.load_runtime_state(state_path)
    assert saved["workers"]["TASK-1"]["attempt_id"] == "attempt-001"

    cleanup = MODULE.mark_cleanup(state_path, "TASK-1#codex#1", "expired")
    assert cleanup["reason"] == "expired"
    saved_after = MODULE.load_runtime_state(state_path)
    assert saved_after["cleanup_queue"][0]["dispatch_id"] == "TASK-1#codex#1"


def test_update_heartbeat_and_reconcile_cleanup(tmp_path: Path) -> None:
    state_path = tmp_path / "runtime.json"
    MODULE.register_attempt(
        state_path,
        dispatch_id="TASK-2#codex#1",
        task_id="TASK-2",
        attempt_id="attempt-002",
        owner_role="backend-agent",
        worktree_path="/tmp/worktree-2",
        backend="tmux",
        status="running",
        heartbeat_at="2026-01-01T00:00:00+00:00",
        lease_expires_at="2026-01-01T00:05:00+00:00",
        retry_count=0,
        max_attempts=2,
    )
    MODULE.update_attempt(
        state_path,
        task_id="TASK-2",
        status="cleanup_pending",
        heartbeat_at="2026-01-01T00:10:00+00:00",
        session_id="session-2",
        transcript_path="/tmp/transcript.log",
    )
    saved = MODULE.load_runtime_state(state_path)
    assert saved["workers"]["TASK-2"]["status"] == "cleanup_pending"
    assert saved["workers"]["TASK-2"]["session_id"] == "session-2"

    expired = MODULE.expired_attempts(state_path, "2026-01-01T00:06:00+00:00")
    assert expired[0]["task_id"] == "TASK-2"
