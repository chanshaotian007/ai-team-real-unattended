from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "ai_team_approval.py"
SPEC = importlib.util.spec_from_file_location("ai_team_approval", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_approve_initiative_creates_batch_and_updates_tasks(tmp_path: Path) -> None:
    initiatives = tmp_path / "initiatives.json"
    tasks = tmp_path / "tasks.json"
    approvals = tmp_path / "approvals.json"
    batches = tmp_path / "batches.json"
    initiatives.write_text(
        json.dumps(
            {
                "initiatives": {
                    "INIT-1": {
                        "initiative_id": "INIT-1",
                        "title": "Demo",
                        "status": "awaiting_approval",
                        "approval": {"required": True, "status": "pending", "approved_by": None, "approved_at": None, "approval_notes": []},
                        "execution_batch_ids": [],
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    tasks.write_text(
        json.dumps(
            {
                "tasks": {
                    "INIT-1-IMPLEMENT": {
                        "task_id": "INIT-1-IMPLEMENT",
                        "task_ref": "INIT-1-IMPLEMENT",
                        "initiative_id": "INIT-1",
                        "task_type": "implementation",
                        "approval_gate": {"required": True, "status": "pending", "reason": "wait"},
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    approvals.write_text(json.dumps({"approvals": {}}), encoding="utf-8")
    batches.write_text(json.dumps({"batches": {}}), encoding="utf-8")

    args = type(
        "Args",
        (),
        {
            "initiatives_file": str(initiatives),
            "initiative_tasks_file": str(tasks),
            "approvals_file": str(approvals),
            "execution_batches_file": str(batches),
            "initiative_id": "INIT-1",
            "approved_by": "tester",
            "note": ["looks good"],
            "json": True,
        },
    )()

    payload = MODULE.approve_initiative(args)

    assert payload["status"] == "approved"
    saved_tasks = json.loads(tasks.read_text(encoding="utf-8"))
    saved_batches = json.loads(batches.read_text(encoding="utf-8"))
    assert saved_tasks["tasks"]["INIT-1-IMPLEMENT"]["approval_gate"]["status"] == "approved"
    assert payload["batch_id"] in saved_batches["batches"]
