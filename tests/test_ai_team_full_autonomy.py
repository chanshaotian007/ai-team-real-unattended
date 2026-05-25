from __future__ import annotations

import importlib.util
import json
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

    payload = MODULE.finalize_lifecycle(args)

    assert payload["status"] == "completed"
    saved_initiatives = json.loads(initiatives.read_text(encoding="utf-8"))
    saved_batches = json.loads(batches.read_text(encoding="utf-8"))
    assert saved_initiatives["initiatives"]["INIT-1"]["status"] == "integration_ready"
    assert saved_batches["batches"]["INIT-1-BATCH-001"]["status"] == "integration_ready"
    assert mr_report.exists()
    assert release_state.exists()
