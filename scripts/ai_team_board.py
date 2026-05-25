#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INITIATIVES = ROOT / "docs/ai-team/operations/INITIATIVES.json"
DEFAULT_INITIATIVE_TASKS = ROOT / "docs/ai-team/operations/INITIATIVE_TASKS.json"
DEFAULT_APPROVALS = ROOT / "docs/ai-team/operations/APPROVALS.json"
DEFAULT_EXECUTION_BATCHES = ROOT / "docs/ai-team/operations/EXECUTION_BATCHES.json"
DEFAULT_BROKER_STATE = ROOT / "docs/ai-team/operations/M1_M2_72H_AGENT_BROKER.json"
DEFAULT_REPORT = ROOT / "docs/ai-team/reports/BOARD_STATE.json"


COLUMNS = [
    "Intake",
    "Analysis",
    "Design",
    "Plan",
    "Awaiting Approval",
    "Approved",
    "Coding",
    "QA/Compliance",
    "Ready for MR",
    "Ready for Release",
    "Done",
    "Blocked",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Project initiative and task state into an ai-team board report.")
    parser.add_argument("--initiatives-file", default=str(DEFAULT_INITIATIVES))
    parser.add_argument("--initiative-tasks-file", default=str(DEFAULT_INITIATIVE_TASKS))
    parser.add_argument("--approvals-file", default=str(DEFAULT_APPROVALS))
    parser.add_argument("--execution-batches-file", default=str(DEFAULT_EXECUTION_BATCHES))
    parser.add_argument("--broker-state", default=str(DEFAULT_BROKER_STATE))
    parser.add_argument("--write-report", default=str(DEFAULT_REPORT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def resolve_path(raw: str) -> Path:
    path = Path(raw).expanduser()
    return path if path.is_absolute() else ROOT / path


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def ensure_mapping(payload: dict[str, Any] | None, key: str) -> dict[str, Any]:
    state = payload if isinstance(payload, dict) else {}
    if not isinstance(state.get(key), dict):
        state[key] = {}
    return state


def work_order_for_task(broker: dict[str, Any], task_id: str) -> dict[str, Any]:
    work_orders = broker.get("work_orders") if isinstance(broker.get("work_orders"), dict) else {}
    work_order = work_orders.get(task_id, {})
    return work_order if isinstance(work_order, dict) else {}


def column_for(task: dict[str, Any], initiative: dict[str, Any], work_order: dict[str, Any]) -> str:
    initiative_status = str(initiative.get("status") or "").strip().lower()
    task_type = str(task.get("task_type") or "implementation").strip().lower()
    work_status = str(work_order.get("status") or task.get("runtime_status") or "").strip().lower()
    approval = task.get("approval_gate") if isinstance(task.get("approval_gate"), dict) else {}
    approval_status = str(approval.get("status") or "").strip().lower()
    batch = task.get("batch") if isinstance(task.get("batch"), dict) else {}
    batch_status = str((batch.get("status") if isinstance(batch, dict) else "") or "").strip().lower()
    verification = batch.get("verification_summary") if isinstance(batch.get("verification_summary"), dict) else {}

    if initiative_status in {"rejected", "blocked", "failed"} or work_status == "errored":
        return "Blocked"
    if task_type == "analysis":
        return "Done" if work_status == "completed" else "Analysis"
    if task_type == "design":
        return "Done" if work_status == "completed" else "Design"
    if task_type == "planning":
        return "Done" if work_status == "completed" else "Plan"
    if approval_status != "approved":
        return "Awaiting Approval"
    if task_type == "implementation":
        mr_status = str(verification.get("mr_status") or "").strip().lower()
        push_status = str(((verification.get("git_save") if isinstance(verification.get("git_save"), dict) else {}).get("push") if isinstance((verification.get("git_save") if isinstance(verification.get("git_save"), dict) else {}).get("push"), dict) else {}).get("status") or "").strip().lower()
        if mr_status in {"blocked_missing_context", "planned_only"}:
            return "Approved"
        if push_status == "pushed" and mr_status in {"created", "existing", "open"}:
            return "Ready for MR"
        if work_status == "completed" or batch_status in {"completed", "integration_ready"}:
            return "Approved"
        return "Coding" if work_status in {"claimed", "running", "dispatched"} else "Approved"
    if task_type in {"qa", "compliance"}:
        release_gate = str(verification.get("release_gate") or "").strip().lower()
        pipeline_status = str(verification.get("pipeline_status") or "").strip().lower()
        if release_gate == "ready_for_release" and pipeline_status in {"", "passed", "success", "ok", "missing_context", "missing"}:
            return "Ready for Release"
        return "QA/Compliance"
    if task_type in {"release", "devops"}:
        return "Ready for Release"
    return "Approved"


def build_board(args: argparse.Namespace) -> dict[str, Any]:
    initiatives = ensure_mapping(load_json(resolve_path(args.initiatives_file)), "initiatives")
    tasks_state = ensure_mapping(load_json(resolve_path(args.initiative_tasks_file)), "tasks")
    approvals = ensure_mapping(load_json(resolve_path(args.approvals_file)), "approvals")
    batches = ensure_mapping(load_json(resolve_path(args.execution_batches_file)), "batches")
    broker = load_json(resolve_path(args.broker_state))

    columns = {column: [] for column in COLUMNS}
    for initiative_id, initiative in initiatives.get("initiatives", {}).items():
        if not isinstance(initiative, dict):
            continue
        for task in tasks_state.get("tasks", {}).values():
            if not isinstance(task, dict) or str(task.get("initiative_id") or "") != initiative_id:
                continue
            work_order = work_order_for_task(broker, str(task.get("task_id") or ""))
            batch = batches.get("batches", {}).get(task.get("batch_id")) if task.get("batch_id") else None
            if isinstance(batch, dict):
                task = {**task, "batch": batch}
            column = column_for(task, initiative, work_order)
            columns[column].append(
                {
                    "initiative_id": initiative_id,
                    "task_id": task.get("task_id"),
                    "task_ref": task.get("task_ref"),
                    "title": initiative.get("title"),
                    "summary": task.get("summary"),
                    "owner_role": task.get("owner_role"),
                    "task_type": task.get("task_type"),
                    "approval": approvals.get("approvals", {}).get(initiative_id),
                    "batch_id": task.get("batch_id"),
                    "batch": batches.get("batches", {}).get(task.get("batch_id")) if task.get("batch_id") else None,
                    "work_order_status": work_order.get("status") or "unseeded",
                    "write_scopes": task.get("write_scopes", []),
                }
            )

    payload = {
        "status": "ok",
        "column_count": len(columns),
        "columns": columns,
    }
    write_json(resolve_path(args.write_report), payload)
    return payload


def emit(payload: dict[str, Any], as_json: bool) -> int:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(payload, ensure_ascii=False))
    return 0


def main() -> int:
    args = parse_args()
    return emit(build_board(args), args.json)


if __name__ == "__main__":
    raise SystemExit(main())
