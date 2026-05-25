from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "ai_team_codex_pilot_seed.py"
SPEC = importlib.util.spec_from_file_location("ai_team_codex_pilot_seed", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_initiative_task_requires_approval_before_dispatch(tmp_path: Path) -> None:
    plan = tmp_path / "plan.json"
    broker = tmp_path / "broker.json"
    dispatches = tmp_path / "dispatches.jsonl"
    initiatives = tmp_path / "initiatives.json"
    initiative_tasks = tmp_path / "initiative_tasks.json"
    approvals = tmp_path / "approvals.json"
    batches = tmp_path / "batches.json"

    plan.write_text(json.dumps({"file_locks": [{"path": "scripts/**", "owner": "backend-agent"}]}), encoding="utf-8")
    broker.write_text(json.dumps({"work_orders": {}}), encoding="utf-8")
    initiatives.write_text(json.dumps({"initiatives": {"INIT-1": {"initiative_id": "INIT-1", "approval": {"status": "pending"}}}}), encoding="utf-8")
    initiative_tasks.write_text(
        json.dumps(
            {
                "tasks": {
                    "INIT-1-IMPLEMENT": {
                        "task_id": "INIT-1-IMPLEMENT",
                        "task_ref": "INIT-1-IMPLEMENT",
                        "initiative_id": "INIT-1",
                        "owner_role": "backend-agent",
                        "summary": "impl",
                        "goal": "implement",
                        "task_type": "implementation",
                        "phase": "execution",
                        "approval_gate": {"required": True, "status": "pending"},
                        "read_scopes": ["scripts/**"],
                        "write_scopes": ["scripts/**"],
                        "artifacts": ["scripts/x.py"],
                        "acceptance_commands": ["python3 -V"],
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    approvals.write_text(json.dumps({"approvals": {"INIT-1": {"status": "pending"}}}), encoding="utf-8")
    batches.write_text(json.dumps({"batches": {}}), encoding="utf-8")

    args = type(
        "Args",
        (),
        {
            "plan": str(plan),
            "catalog": "",
            "initiatives_file": str(initiatives),
            "initiative_tasks_file": str(initiative_tasks),
            "approvals_file": str(approvals),
            "execution_batches_file": str(batches),
            "broker_state": str(broker),
            "dispatches_file": str(dispatches),
            "at": None,
            "source": "initiative",
            "initiative_id": "INIT-1",
            "batch_id": None,
            "role": None,
            "task_ref": ["INIT-1-IMPLEMENT"],
            "all": False,
            "force": False,
            "requested_by": "tester",
            "dry_run": True,
            "json": True,
            "command": "seed",
        },
    )()

    payload = MODULE.seed_tasks(args)

    assert payload["results"][0]["status"] == "blocked"
    assert "approval_not_granted=pending" in payload["results"][0]["readiness"]["blocked_reasons"]
