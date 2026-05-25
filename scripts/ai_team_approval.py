#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INITIATIVES = ROOT / "docs/ai-team/operations/INITIATIVES.json"
DEFAULT_INITIATIVE_TASKS = ROOT / "docs/ai-team/operations/INITIATIVE_TASKS.json"
DEFAULT_APPROVALS = ROOT / "docs/ai-team/operations/APPROVALS.json"
DEFAULT_EXECUTION_BATCHES = ROOT / "docs/ai-team/operations/EXECUTION_BATCHES.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage approval gates and execution batches for ai-team initiatives.")
    parser.add_argument("--initiatives-file", default=str(DEFAULT_INITIATIVES))
    parser.add_argument("--initiative-tasks-file", default=str(DEFAULT_INITIATIVE_TASKS))
    parser.add_argument("--approvals-file", default=str(DEFAULT_APPROVALS))
    parser.add_argument("--execution-batches-file", default=str(DEFAULT_EXECUTION_BATCHES))
    parser.add_argument("--json", action="store_true")

    subparsers = parser.add_subparsers(dest="command", required=True)

    approve_cmd = subparsers.add_parser("approve")
    approve_cmd.add_argument("--initiative-id", required=True)
    approve_cmd.add_argument("--approved-by", default="user")
    approve_cmd.add_argument("--note", action="append", default=[])
    approve_cmd.add_argument("--json", action="store_true")

    reject_cmd = subparsers.add_parser("reject")
    reject_cmd.add_argument("--initiative-id", required=True)
    reject_cmd.add_argument("--rejected-by", default="user")
    reject_cmd.add_argument("--note", action="append", default=[])
    reject_cmd.add_argument("--json", action="store_true")

    list_cmd = subparsers.add_parser("list")
    list_cmd.add_argument("--json", action="store_true")

    return parser.parse_args()


def resolve_path(raw: str) -> Path:
    path = Path(raw).expanduser()
    return path if path.is_absolute() else ROOT / path


def now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def ensure_mapping(payload: dict[str, Any] | None, key: str) -> dict[str, Any]:
    state = payload if isinstance(payload, dict) else {}
    if not isinstance(state.get(key), dict):
        state[key] = {}
    return state


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def batch_id_for(initiative_id: str, existing: dict[str, Any]) -> str:
    count = 1
    while True:
        candidate = f"{initiative_id}-BATCH-{count:03d}"
        if candidate not in existing.get("batches", {}):
            return candidate
        count += 1


def related_task_ids(tasks_state: dict[str, Any], initiative_id: str) -> list[str]:
    items = []
    for task_id, task in tasks_state.get("tasks", {}).items():
        if isinstance(task, dict) and str(task.get("initiative_id") or "") == initiative_id:
            items.append(str(task.get("task_id") or task_id))
    return sorted(items)


def update_tasks_for_approval(tasks_state: dict[str, Any], initiative_id: str, *, approved: bool, batch_id: str | None) -> None:
    for task in tasks_state.get("tasks", {}).values():
        if not isinstance(task, dict) or str(task.get("initiative_id") or "") != initiative_id:
            continue
        gate = task.get("approval_gate") if isinstance(task.get("approval_gate"), dict) else {"required": False, "status": "approved", "reason": None}
        if gate.get("required"):
            gate["status"] = "approved" if approved else "rejected"
            gate["reason"] = None if approved else "initiative approval rejected"
            task["batch_id"] = batch_id if approved else None
        task["approval_gate"] = gate


def approve_initiative(args: argparse.Namespace) -> dict[str, Any]:
    initiatives_path = resolve_path(args.initiatives_file)
    tasks_path = resolve_path(args.initiative_tasks_file)
    approvals_path = resolve_path(args.approvals_file)
    batches_path = resolve_path(args.execution_batches_file)

    initiatives = ensure_mapping(load_json(initiatives_path), "initiatives")
    tasks_state = ensure_mapping(load_json(tasks_path), "tasks")
    approvals = ensure_mapping(load_json(approvals_path), "approvals")
    batches = ensure_mapping(load_json(batches_path), "batches")

    initiative = initiatives.get("initiatives", {}).get(args.initiative_id, {})
    if not isinstance(initiative, dict) or not initiative:
        return {"status": "missing", "initiative_id": args.initiative_id}

    approved_at = now_iso()
    notes = [str(item).strip() for item in args.note if str(item).strip()]
    batch_id = batch_id_for(args.initiative_id, batches)
    task_ids = related_task_ids(tasks_state, args.initiative_id)
    initiatives["initiatives"][args.initiative_id]["status"] = "approved_for_execution"
    initiatives["initiatives"][args.initiative_id]["updated_at"] = approved_at
    initiatives["initiatives"][args.initiative_id]["approval"] = {
        "required": True,
        "status": "approved",
        "approved_by": str(args.approved_by).strip() or "user",
        "approved_at": approved_at,
        "approval_notes": notes,
    }
    initiatives["initiatives"][args.initiative_id].setdefault("execution_batch_ids", []).append(batch_id)
    initiatives["updated_at"] = approved_at

    approvals["approvals"][args.initiative_id] = {
        "initiative_id": args.initiative_id,
        "status": "approved",
        "approved_by": str(args.approved_by).strip() or "user",
        "approved_at": approved_at,
        "approval_notes": notes,
        "batch_id": batch_id,
    }
    approvals["updated_at"] = approved_at

    batches["batches"][batch_id] = {
        "batch_id": batch_id,
        "initiative_id": args.initiative_id,
        "approved_snapshot_id": approved_at,
        "task_ids": task_ids,
        "status": "approved",
        "triggered_by": str(args.approved_by).strip() or "user",
        "triggered_at": approved_at,
        "started_at": None,
        "completed_at": None,
        "verification_summary": None,
    }
    batches["updated_at"] = approved_at

    update_tasks_for_approval(tasks_state, args.initiative_id, approved=True, batch_id=batch_id)
    tasks_state["updated_at"] = approved_at

    write_json(initiatives_path, initiatives)
    write_json(tasks_path, tasks_state)
    write_json(approvals_path, approvals)
    write_json(batches_path, batches)
    return {
        "status": "approved",
        "initiative_id": args.initiative_id,
        "batch_id": batch_id,
        "task_ids": task_ids,
    }


def reject_initiative(args: argparse.Namespace) -> dict[str, Any]:
    initiatives_path = resolve_path(args.initiatives_file)
    tasks_path = resolve_path(args.initiative_tasks_file)
    approvals_path = resolve_path(args.approvals_file)

    initiatives = ensure_mapping(load_json(initiatives_path), "initiatives")
    tasks_state = ensure_mapping(load_json(tasks_path), "tasks")
    approvals = ensure_mapping(load_json(approvals_path), "approvals")

    initiative = initiatives.get("initiatives", {}).get(args.initiative_id, {})
    if not isinstance(initiative, dict) or not initiative:
        return {"status": "missing", "initiative_id": args.initiative_id}

    rejected_at = now_iso()
    notes = [str(item).strip() for item in args.note if str(item).strip()]
    initiatives["initiatives"][args.initiative_id]["status"] = "rejected"
    initiatives["initiatives"][args.initiative_id]["updated_at"] = rejected_at
    initiatives["initiatives"][args.initiative_id]["approval"] = {
        "required": True,
        "status": "rejected",
        "approved_by": str(args.rejected_by).strip() or "user",
        "approved_at": rejected_at,
        "approval_notes": notes,
    }
    initiatives["updated_at"] = rejected_at

    approvals["approvals"][args.initiative_id] = {
        "initiative_id": args.initiative_id,
        "status": "rejected",
        "approved_by": str(args.rejected_by).strip() or "user",
        "approved_at": rejected_at,
        "approval_notes": notes,
        "batch_id": None,
    }
    approvals["updated_at"] = rejected_at

    update_tasks_for_approval(tasks_state, args.initiative_id, approved=False, batch_id=None)
    tasks_state["updated_at"] = rejected_at

    write_json(initiatives_path, initiatives)
    write_json(tasks_path, tasks_state)
    write_json(approvals_path, approvals)
    return {"status": "rejected", "initiative_id": args.initiative_id}


def list_approvals(args: argparse.Namespace) -> dict[str, Any]:
    approvals = ensure_mapping(load_json(resolve_path(args.approvals_file)), "approvals")
    batches = ensure_mapping(load_json(resolve_path(args.execution_batches_file)), "batches")
    return {
        "status": "ok",
        "approval_count": len(approvals.get("approvals", {})),
        "approvals": list(approvals.get("approvals", {}).values()),
        "batches": list(batches.get("batches", {}).values()),
    }


def emit(payload: dict[str, Any], as_json: bool) -> int:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(payload, ensure_ascii=False))
    return 0


def main() -> int:
    args = parse_args()
    if args.command == "approve":
        return emit(approve_initiative(args), args.json)
    if args.command == "reject":
        return emit(reject_initiative(args), args.json)
    if args.command == "list":
        return emit(list_approvals(args), args.json)
    return emit({"status": "unsupported_command"}, args.json)


if __name__ == "__main__":
    raise SystemExit(main())
