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


def test_build_board_projects_runtime_observability_fields(tmp_path: Path) -> None:
    initiatives = tmp_path / "initiatives.json"
    tasks = tmp_path / "tasks.json"
    approvals = tmp_path / "approvals.json"
    batches = tmp_path / "batches.json"
    broker = tmp_path / "broker.json"
    report = tmp_path / "board.json"

    initiatives.write_text(json.dumps({"initiatives": {"INIT-2": {"initiative_id": "INIT-2", "title": "Demo 2", "status": "approved_for_execution"}}}), encoding="utf-8")
    tasks.write_text(
        json.dumps(
            {
                "tasks": {
                    "INIT-2-IMPLEMENT": {
                        "task_id": "INIT-2-IMPLEMENT",
                        "task_ref": "INIT-2-IMPLEMENT",
                        "initiative_id": "INIT-2",
                        "summary": "impl",
                        "owner_role": "backend-agent",
                        "task_type": "implementation",
                        "approval_gate": {"required": True, "status": "approved"},
                        "write_scopes": ["scripts/**"],
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    approvals.write_text(json.dumps({"approvals": {"INIT-2": {"status": "approved"}}}), encoding="utf-8")
    batches.write_text(json.dumps({"batches": {}}), encoding="utf-8")
    broker.write_text(
        json.dumps({"work_orders": {"INIT-2-IMPLEMENT": {"status": "running", "attempt_id": "attempt-2", "heartbeat_at": "2026-01-01T00:00:00+00:00", "lease_expires_at": "2026-01-01T00:01:00+00:00", "worker_session_id": "session-2"}}}),
        encoding="utf-8",
    )

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
    item = payload["columns"]["Coding"][0]
    assert item["attempt_id"] == "attempt-2"
    assert item["worker_session_id"] == "session-2"
