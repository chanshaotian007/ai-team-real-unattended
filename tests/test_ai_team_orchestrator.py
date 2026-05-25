from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "ai_team_orchestrator.py"
SPEC = importlib.util.spec_from_file_location("ai_team_orchestrator", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_create_initiative_generates_planning_and_execution_tasks(tmp_path: Path) -> None:
    initiatives = tmp_path / "initiatives.json"
    tasks = tmp_path / "tasks.json"

    args = type(
        "Args",
        (),
        {
            "initiatives_file": str(initiatives),
            "initiative_tasks_file": str(tasks),
            "initiative_id": "INIT-DEMO-001",
            "title": "Add dashboard review flow",
            "request_text": "Add dashboard review flow for frontend approval",
            "requester": "tester",
            "priority": "high",
            "risk_level": "medium",
            "constraint": ["must stay local"],
            "acceptance": ["board updated"],
            "json": True,
        },
    )()

    payload = MODULE.create_initiative(args)

    assert payload["status"] == "created"
    assert payload["tasks_created"] == 5
    saved_initiatives = json.loads(initiatives.read_text(encoding="utf-8"))
    saved_tasks = json.loads(tasks.read_text(encoding="utf-8"))
    assert saved_initiatives["initiatives"]["INIT-DEMO-001"]["approval"]["status"] == "pending"
    assert saved_tasks["tasks"]["INIT-DEMO-001-IMPLEMENT"]["approval_gate"]["required"] is True
    assert saved_tasks["tasks"]["INIT-DEMO-001-IMPLEMENT"]["owner_role"] == "frontend-agent"
