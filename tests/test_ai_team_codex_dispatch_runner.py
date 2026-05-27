from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "ai_team_codex_dispatch_runner.py"
SPEC = importlib.util.spec_from_file_location("ai_team_codex_dispatch_runner", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_claim_skips_dispatch_awaiting_approval(tmp_path: Path) -> None:
    dispatches = tmp_path / "dispatches.jsonl"
    notifications = tmp_path / "notifications.jsonl"
    state = tmp_path / "state.json"
    broker = tmp_path / "broker.json"
    dispatches.write_text(
        json.dumps(
            {
                "dispatch_id": "TASK-1#codex#1",
                "task_id": "TASK-1",
                "owner_role": "backend-agent",
                "summary": "impl",
                "task_ref": "TASK-1",
                "task_contract": {"task_type": "implementation", "approval_gate": {"required": True, "status": "pending"}},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    broker.write_text(json.dumps({"work_orders": {"TASK-1": {"status": "dispatched", "approval_gate": {"required": True, "status": "pending"}}}}), encoding="utf-8")

    args = type(
        "Args",
        (),
        {
            "dispatches_file": str(dispatches),
            "notifications_file": str(notifications),
            "state_file": str(state),
            "broker_state": str(broker),
            "role": "backend-agent",
            "dispatch_id": None,
            "json": True,
        },
    )()

    payload = MODULE.claim_dispatch(args)

    assert payload["status"] == "empty"


def test_update_dispatch_runtime_for_heartbeat_and_retry(tmp_path: Path) -> None:
    dispatches = tmp_path / "dispatches.jsonl"
    notifications = tmp_path / "notifications.jsonl"
    state = tmp_path / "state.json"
    broker = tmp_path / "broker.json"
    dispatches.write_text(
        json.dumps(
            {
                "dispatch_id": "TASK-2#codex#1",
                "task_id": "TASK-2",
                "owner_role": "backend-agent",
                "summary": "impl",
                "task_ref": "TASK-2",
                "task_contract": {"task_type": "implementation", "approval_gate": {"required": True, "status": "approved"}},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    broker.write_text(json.dumps({"work_orders": {"TASK-2": {"status": "dispatched", "approval_gate": {"required": True, "status": "approved"}}}}), encoding="utf-8")

    args = type(
        "Args",
        (),
        {
            "dispatches_file": str(dispatches),
            "notifications_file": str(notifications),
            "state_file": str(state),
            "broker_state": str(broker),
            "json": True,
        },
    )()

    heartbeat = MODULE.update_dispatch_runtime(
        args,
        "TASK-2#codex#1",
        status="running",
        message="heartbeat",
        heartbeat_at="2026-01-01T00:00:00+00:00",
        lease_expires_at="2026-01-01T00:01:00+00:00",
        attempt_id="attempt-001",
    )
    assert heartbeat["status"] == "running"

    retry = MODULE.update_dispatch_runtime(
        args,
        "TASK-2#codex#1",
        status="retry_scheduled",
        message="retry scheduled",
    )
    assert retry["status"] == "retry_scheduled"

    saved = json.loads(state.read_text(encoding="utf-8"))
    assert saved["dispatches"]["TASK-2#codex#1"]["attempt_id"] == "attempt-001"
