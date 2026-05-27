from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "ai_team_board.py"
SPEC = importlib.util.spec_from_file_location("ai_team_board", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_build_board_projects_awaiting_approval_and_done(tmp_path: Path) -> None:
    initiatives = tmp_path / "initiatives.json"
    tasks = tmp_path / "tasks.json"
    approvals = tmp_path / "approvals.json"
    batches = tmp_path / "batches.json"
    broker = tmp_path / "broker.json"
    report = tmp_path / "board.json"

    initiatives.write_text(json.dumps({"initiatives": {"INIT-1": {"initiative_id": "INIT-1", "title": "Demo", "status": "planned"}}}), encoding="utf-8")
    tasks.write_text(
        json.dumps(
            {
                "tasks": {
                    "INIT-1-ANALYSIS": {"task_id": "INIT-1-ANALYSIS", "task_ref": "INIT-1-ANALYSIS", "initiative_id": "INIT-1", "summary": "analysis", "owner_role": "orchestrator", "task_type": "analysis", "approval_gate": {"required": False, "status": "approved"}, "write_scopes": []},
                    "INIT-1-IMPLEMENT": {"task_id": "INIT-1-IMPLEMENT", "task_ref": "INIT-1-IMPLEMENT", "initiative_id": "INIT-1", "summary": "impl", "owner_role": "backend-agent", "task_type": "implementation", "approval_gate": {"required": True, "status": "pending"}, "write_scopes": ["scripts/**"]},
                }
            }
        ),
        encoding="utf-8",
    )
    approvals.write_text(json.dumps({"approvals": {}}), encoding="utf-8")
    batches.write_text(json.dumps({"batches": {}}), encoding="utf-8")
    broker.write_text(json.dumps({"work_orders": {"INIT-1-ANALYSIS": {"status": "completed"}, "INIT-1-IMPLEMENT": {"status": "running", "attempt_id": "attempt-1", "heartbeat_at": "2026-01-01T00:00:00+00:00", "lease_expires_at": "2026-01-01T00:01:00+00:00", "worker_session_id": "session-1"}}}), encoding="utf-8")

    args = type(
        "Args",
        (),
        {
            "initiatives_file": str(initiatives),
            "initiative_tasks_file": str(tasks),
            "approvals_file": str(approvals),
            "execution_batches_file": str(batches),
            "broker_state": str(broker),
            "write_report": str(report),
            "json": True,
        },
    )()

    payload = MODULE.build_board(args)

    assert payload["status"] == "ok"
    assert payload["columns"]["Done"][0]["task_ref"] == "INIT-1-ANALYSIS"
    assert payload["columns"]["Coding"][0]["task_ref"] == "INIT-1-IMPLEMENT"
    assert payload["columns"]["Coding"][0]["attempt_id"] == "attempt-1"
