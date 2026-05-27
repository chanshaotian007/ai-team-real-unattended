from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "ai_team_codex_unattended.py"
SPEC = importlib.util.spec_from_file_location("ai_team_codex_unattended", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_execute_dispatch_uses_supervisor_result() -> None:
    original = MODULE.run_supervisor
    try:
        MODULE.run_supervisor = lambda args, role: {"status": "claimed", "dispatch_id": "TASK-1#codex#1", "role": role}
        payload = MODULE.execute_dispatch(type("Args", (), {})(), {"dispatch_id": "TASK-1#codex#1", "task_ref": "TASK-1", "owner_role": "backend-agent"})
    finally:
        MODULE.run_supervisor = original

    assert payload["result"] == "supervised"
    assert payload["runner_result"]["status"] == "claimed"


def test_execute_dispatch_surfaces_blocked_intent() -> None:
    original = MODULE.run_supervisor
    try:
        MODULE.run_supervisor = lambda args, role: {"status": "blocked", "violations": [{"category": "destructive"}]}
        payload = MODULE.execute_dispatch(type("Args", (), {})(), {"dispatch_id": "TASK-2#codex#1", "task_ref": "TASK-2", "owner_role": "backend-agent"})
    finally:
        MODULE.run_supervisor = original

    assert payload["result"] == "blocked"


def test_unattended_round_reports_supervised_execution(monkeypatch=None) -> None:
    original_list_dispatches = MODULE.list_dispatches
    original_claim_dispatch_id = MODULE.claim_dispatch_id
    original_execute_dispatch = MODULE.execute_dispatch
    original_list_pilot_tasks = MODULE.list_pilot_tasks
    try:
        MODULE.list_dispatches = lambda args: {"dispatches": [{"status": "queued", "owner_role": "backend-agent", "dispatch_id": "TASK-3#codex#1"}]}
        MODULE.claim_dispatch_id = lambda args, role, dispatch_id: {"status": "claimed", "dispatch_id": dispatch_id, "dispatch": {"dispatch_id": dispatch_id, "task_ref": "TASK-3", "owner_role": role}}
        MODULE.execute_dispatch = lambda args, dispatch: {"dispatch_id": dispatch["dispatch_id"], "result": "supervised", "owner_role": dispatch["owner_role"]}
        MODULE.list_pilot_tasks = lambda args: {"tasks": []}
        MODULE.status_dispatches = lambda args: {"counts": {"pending": 0, "errored": 0}}
        payload = MODULE.unattended_round(type("Args", (), {"dispatches_file": "", "seed_source": "catalog"})())
    finally:
        MODULE.list_dispatches = original_list_dispatches
        MODULE.claim_dispatch_id = original_claim_dispatch_id
        MODULE.execute_dispatch = original_execute_dispatch
        MODULE.list_pilot_tasks = original_list_pilot_tasks

    assert payload["executions"][0]["result"] == "supervised"
