from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "ai_team_autonomous_workflow.py"
SPEC = importlib.util.spec_from_file_location("ai_team_autonomous_workflow", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_run_workflow_completes_batch_and_writes_artifacts(tmp_path: Path) -> None:
    initiatives = tmp_path / "initiatives.json"
    tasks = tmp_path / "tasks.json"
    batches = tmp_path / "batches.json"
    report = tmp_path / "report.json"

    initiatives.write_text(json.dumps({"initiatives": {"INIT-1": {"initiative_id": "INIT-1", "status": "approved_for_execution", "plan_artifact_refs": []}}}), encoding="utf-8")
    tasks.write_text(
        json.dumps(
            {
                "tasks": {
                    "INIT-1-PLAN": {"task_id": "INIT-1-PLAN", "task_ref": "INIT-1-PLAN", "initiative_id": "INIT-1", "task_type": "planning", "owner_role": "orchestrator", "goal": "plan", "phase": "planning", "artifacts": [str(tmp_path / "plan.json")]},
                    "INIT-1-IMPLEMENT": {"task_id": "INIT-1-IMPLEMENT", "task_ref": "INIT-1-IMPLEMENT", "initiative_id": "INIT-1", "task_type": "implementation", "owner_role": "backend-agent", "goal": "implement", "phase": "execution", "artifacts": [str(tmp_path / "implement.json")]},
                }
            }
        ),
        encoding="utf-8",
    )
    batches.write_text(json.dumps({"batches": {"INIT-1-BATCH-001": {"batch_id": "INIT-1-BATCH-001", "initiative_id": "INIT-1", "status": "approved"}}}), encoding="utf-8")

    args = type(
        "Args",
        (),
        {
            "initiatives_file": str(initiatives),
            "initiative_tasks_file": str(tasks),
            "execution_batches_file": str(batches),
            "report": str(report),
            "initiative_id": "INIT-1",
            "batch_id": "INIT-1-BATCH-001",
            "json": True,
        },
    )()

    payload = MODULE.run_workflow(args)

    assert payload["status"] == "completed"
    saved_batches = json.loads(batches.read_text(encoding="utf-8"))
    assert saved_batches["batches"]["INIT-1-BATCH-001"]["status"] == "completed"
    assert (tmp_path / "plan.json").exists()
    assert (tmp_path / "implement.json").exists()
