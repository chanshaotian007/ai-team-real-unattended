from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "ai_team_full_autonomy.py"
SPEC = importlib.util.spec_from_file_location("ai_team_full_autonomy", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_finalize_lifecycle_marks_integration_ready(tmp_path: Path) -> None:
    initiatives = tmp_path / "initiatives.json"
    batches = tmp_path / "batches.json"
    board = tmp_path / "board.json"
    workflow = tmp_path / "workflow.json"
    mr_report = tmp_path / "mr.json"
    release_state = tmp_path / "release.json"

    initiatives.write_text(json.dumps({"initiatives": {"INIT-1": {"initiative_id": "INIT-1", "status": "closed"}}}), encoding="utf-8")
    batches.write_text(json.dumps({"batches": {"INIT-1-BATCH-001": {"batch_id": "INIT-1-BATCH-001", "initiative_id": "INIT-1", "status": "completed", "verification_summary": {"completed_task_count": 2}}}}), encoding="utf-8")
    board.write_text(json.dumps({"columns": {"Done": [{"task_ref": "INIT-1-IMPLEMENT"}]}}), encoding="utf-8")
    workflow.write_text(json.dumps({"verification_summary": {"completed_task_count": 2}}), encoding="utf-8")

    args = type(
        "Args",
        (),
        {
            "initiatives_file": str(initiatives),
            "execution_batches_file": str(batches),
            "board_report": str(board),
            "autonomous_report": str(workflow),
            "mr_report": str(mr_report),
            "release_state": str(release_state),
            "initiative_id": "INIT-1",
            "batch_id": "INIT-1-BATCH-001",
            "json": True,
        },
    )()

    original_run_supervised_workflow = MODULE.run_supervised_workflow
    original_run_git_save = MODULE.run_git_save
    original_run_git_push = MODULE.run_git_push
    original_run_mr_plan = MODULE.run_mr_plan
    original_run_mr_ensure = MODULE.run_mr_ensure
    original_run_mr_status = MODULE.run_mr_status
    original_run_release_state = MODULE.run_release_state
    original_refresh_board = MODULE.refresh_board
    try:
        MODULE.run_supervised_workflow = lambda args: {"status": "ok", "completed_tasks": [{"changed_files": ["scripts/x.py"], "tests_run": [{"command": "python3 -m py_compile scripts/ai_team_generated_impl.py", "status": "passed"}], "risk_notes": [], "handover_notes": []}], "verification_summary": {"completed_task_count": 2}}
        MODULE.run_git_save = lambda: {"status": "saved"}
        MODULE.run_git_push = lambda args: {"status": "pushed"}
        MODULE.run_mr_plan = lambda args: {"status": "ok"}
        MODULE.run_mr_ensure = lambda args: {"status": "created"}
        MODULE.run_mr_status = lambda args: {"status": "open", "pipeline": {"pipeline_status": "passed"}}
        MODULE.run_release_state = lambda args, verification_command: {"status": {"status": "ok"}}
        MODULE.refresh_board = lambda args: {"status": "ok", "columns": {"Done": [{"task_ref": "INIT-1-IMPLEMENT"}]}}

        payload = MODULE.finalize_lifecycle(args)
    finally:
        MODULE.run_supervised_workflow = original_run_supervised_workflow
        MODULE.run_git_save = original_run_git_save
        MODULE.run_git_push = original_run_git_push
        MODULE.run_mr_plan = original_run_mr_plan
        MODULE.run_mr_ensure = original_run_mr_ensure
        MODULE.run_mr_status = original_run_mr_status
        MODULE.run_release_state = original_run_release_state
        MODULE.refresh_board = original_refresh_board

    assert payload["status"] == "completed"
    assert payload["workflow"]["status"] in {"ok", "conditional"}
    saved_initiatives = json.loads(initiatives.read_text(encoding="utf-8"))
    saved_batches = json.loads(batches.read_text(encoding="utf-8"))
    assert saved_initiatives["initiatives"]["INIT-1"]["status"] == "integration_ready"
    assert saved_batches["batches"]["INIT-1-BATCH-001"]["status"] == "integration_ready"
    assert mr_report.exists()
