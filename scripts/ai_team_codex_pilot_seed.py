#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PLAN = ROOT / "docs/ai-team/operations/M1_M2_72H_PLAN.json"
DEFAULT_CATALOG = ROOT / "docs/ai-team/operations/CODEX_AGENT_PILOT_TASKS.yaml"
DEFAULT_INITIATIVES = ROOT / "docs/ai-team/operations/INITIATIVES.json"
DEFAULT_INITIATIVE_TASKS = ROOT / "docs/ai-team/operations/INITIATIVE_TASKS.json"
DEFAULT_APPROVALS = ROOT / "docs/ai-team/operations/APPROVALS.json"
DEFAULT_EXECUTION_BATCHES = ROOT / "docs/ai-team/operations/EXECUTION_BATCHES.json"
DEFAULT_BROKER_STATE = ROOT / "docs/ai-team/operations/M1_M2_72H_AGENT_BROKER.json"
DEFAULT_DISPATCHES = ROOT / "docs/ai-team/operations/M1_M2_72H_CODEX_AGENT_DISPATCHES.jsonl"
ACTIVE_WORK_ORDER_STATUSES = {"dispatched", "claimed", "preparing_workspace", "starting_session", "running", "collecting_results"}
COMPLETED_WORK_ORDER_STATUSES = {"completed", "accepted", "closed"}
PLANNING_TASK_TYPES = {"analysis", "design", "planning"}
IMPLEMENTATION_TASK_TYPES = {"implementation", "qa", "compliance", "release", "devops"}
DEFAULT_RUNTIME_HINTS = {
    "timeout_seconds": 1800,
    "heartbeat_interval_seconds": 30,
    "max_attempts": 1,
    "execution_backend": "simulation",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed real Codex-agent pilot tasks from a curated catalog.")
    parser.add_argument("--plan", default=str(DEFAULT_PLAN))
    parser.add_argument("--catalog", default=str(DEFAULT_CATALOG))
    parser.add_argument("--initiatives-file", default=str(DEFAULT_INITIATIVES))
    parser.add_argument("--initiative-tasks-file", default=str(DEFAULT_INITIATIVE_TASKS))
    parser.add_argument("--approvals-file", default=str(DEFAULT_APPROVALS))
    parser.add_argument("--execution-batches-file", default=str(DEFAULT_EXECUTION_BATCHES))
    parser.add_argument("--broker-state", default=str(DEFAULT_BROKER_STATE))
    parser.add_argument("--dispatches-file", default=str(DEFAULT_DISPATCHES))
    parser.add_argument("--at", help="Override current time with ISO8601 timestamp")

    subparsers = parser.add_subparsers(dest="command", required=True)

    list_cmd = subparsers.add_parser("list")
    list_cmd.add_argument("--role")
    list_cmd.add_argument("--source", choices=["catalog", "initiative"], default="catalog")
    list_cmd.add_argument("--initiative-id")
    list_cmd.add_argument("--json", action="store_true")

    show_cmd = subparsers.add_parser("show")
    show_cmd.add_argument("--task-ref", required=True)
    show_cmd.add_argument("--source", choices=["catalog", "initiative"], default="catalog")
    show_cmd.add_argument("--initiative-id")
    show_cmd.add_argument("--json", action="store_true")

    seed_cmd = subparsers.add_parser("seed")
    seed_cmd.add_argument("--task-ref", action="append", default=[])
    seed_cmd.add_argument("--role")
    seed_cmd.add_argument("--source", choices=["catalog", "initiative"], default="catalog")
    seed_cmd.add_argument("--initiative-id")
    seed_cmd.add_argument("--batch-id")
    seed_cmd.add_argument("--all", action="store_true")
    seed_cmd.add_argument("--force", action="store_true")
    seed_cmd.add_argument("--requested-by", default="orchestrator")
    seed_cmd.add_argument("--dry-run", action="store_true")
    seed_cmd.add_argument("--json", action="store_true")
    return parser.parse_args()


def resolve_path(raw: str) -> Path:
    path = Path(raw).expanduser()
    return path if path.is_absolute() else ROOT / path


def resolve_now(raw: str | None) -> datetime:
    return datetime.fromisoformat(raw) if raw else datetime.now().astimezone()


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


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return {}
    return payload if isinstance(payload, dict) else {}


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def load_dispatches(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        text = raw.strip()
        if not text:
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def normalized_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def ensure_named_mapping(payload: dict[str, Any] | None, key: str) -> dict[str, Any]:
    state = payload if isinstance(payload, dict) else {}
    value = state.get(key)
    if not isinstance(value, dict):
        value = {}
        state[key] = value
    return state


def load_named_mapping(path: Path, key: str) -> dict[str, Any]:
    return ensure_named_mapping(load_json(path), key)


def task_phase(task: dict[str, Any]) -> str:
    phase = str(task.get("phase") or "").strip().lower()
    if phase:
        return phase
    task_type = str(task.get("task_type") or "").strip().lower()
    if task_type in PLANNING_TASK_TYPES:
        return "planning"
    if task_type in IMPLEMENTATION_TASK_TYPES:
        return "execution"
    return "execution"


def task_type(task: dict[str, Any]) -> str:
    return str(task.get("task_type") or "implementation").strip().lower() or "implementation"


def approval_gate(task: dict[str, Any]) -> dict[str, Any]:
    value = task.get("approval_gate")
    if isinstance(value, dict):
        gate = dict(value)
    else:
        gate = {}
    task_kind = task_type(task)
    phase = task_phase(task)
    required = bool(gate.get("required", task_kind in IMPLEMENTATION_TASK_TYPES and phase != "planning"))
    status = str(gate.get("status") or ("approved" if not required else "pending")).strip().lower()
    reason = str(gate.get("reason") or "").strip() or None
    return {"required": required, "status": status, "reason": reason}


def ensure_broker_state(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    state = payload if isinstance(payload, dict) else {}
    work_orders = state.get("work_orders")
    locks = state.get("locks")
    if not isinstance(work_orders, dict):
        work_orders = {}
    if not isinstance(locks, dict):
        locks = {}
    state["work_orders"] = work_orders
    state["locks"] = locks
    return state


def scope_prefix(pattern: str) -> str:
    value = str(pattern or "").strip()
    if not value:
        return ""
    prefix = value.split("**", 1)[0].split("*", 1)[0].rstrip("/")
    return prefix


def scope_covered_by_lock(scope: str, lock_path: str) -> bool:
    scope_root = scope_prefix(scope)
    lock_root = scope_prefix(lock_path)
    if not scope_root or not lock_root:
        return False
    return scope_root == lock_root or scope_root.startswith(lock_root + "/")


def plan_lock_owners(plan: dict[str, Any], scope: str) -> list[str]:
    owners: list[str] = []
    for lock in plan.get("file_locks", []):
        if not isinstance(lock, dict):
            continue
        lock_path = str(lock.get("path") or "").strip()
        owner = str(lock.get("owner") or "").strip()
        if not owner or not lock_path:
            continue
        if scope_covered_by_lock(scope, lock_path) and owner not in owners:
            owners.append(owner)
    return owners


def task_contract(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_id": str(task.get("task_id") or "").strip(),
        "initiative_id": str(task.get("initiative_id") or "").strip() or None,
        "parent_task_id": str(task.get("parent_task_id") or "").strip() or None,
        "task_type": task_type(task),
        "phase": task_phase(task),
        "approval_gate": approval_gate(task),
        "execution_mode": str(task.get("execution_mode") or "codex_agent").strip() or "codex_agent",
        "batch_id": str(task.get("batch_id") or "").strip() or None,
        "owner_role": str(task.get("owner_role") or "").strip(),
        "collaborators": normalized_string_list(task.get("collaborators")),
        "depends_on_task_refs": normalized_string_list(task.get("depends_on_task_refs")),
        "goal": str(task.get("goal") or "").strip(),
        "constraints": normalized_string_list(task.get("constraints")),
        "read_scopes": normalized_string_list(task.get("read_scopes")),
        "write_scopes": normalized_string_list(task.get("write_scopes")),
        "artifacts": normalized_string_list(task.get("artifacts")),
        "acceptance_commands": normalized_string_list(task.get("acceptance_commands")),
        "risk_notes_required": bool(task.get("risk_notes_required", True)),
        "rollback_hint": str(task.get("rollback_hint") or "").strip(),
        "produces": normalized_string_list(task.get("produces")),
        "consumes": normalized_string_list(task.get("consumes")),
        "source_refs": normalized_string_list(task.get("source_refs")),
        "plan_links": task.get("plan_links") if isinstance(task.get("plan_links"), list) else [],
        "runtime": {
            "timeout_seconds": int(task.get("timeout_seconds") or DEFAULT_RUNTIME_HINTS["timeout_seconds"]),
            "heartbeat_interval_seconds": int(task.get("heartbeat_interval_seconds") or DEFAULT_RUNTIME_HINTS["heartbeat_interval_seconds"]),
            "max_attempts": int(task.get("max_attempts") or DEFAULT_RUNTIME_HINTS["max_attempts"]),
            "execution_backend": str(task.get("execution_backend") or DEFAULT_RUNTIME_HINTS["execution_backend"]).strip()
            or DEFAULT_RUNTIME_HINTS["execution_backend"],
        },
    }


def validate_task(task: dict[str, Any], plan: dict[str, Any], catalog_tasks: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    task_ref = str(task.get("task_ref") or "").strip()
    owner_role = str(task.get("owner_role") or "").strip()
    read_scopes = normalized_string_list(task.get("read_scopes"))
    write_scopes = normalized_string_list(task.get("write_scopes"))
    acceptance_commands = normalized_string_list(task.get("acceptance_commands"))
    depends_on_task_refs = normalized_string_list(task.get("depends_on_task_refs"))
    known_task_refs = {
        str(item.get("task_ref") or "").strip()
        for item in (catalog_tasks or [])
        if isinstance(item, dict) and str(item.get("task_ref") or "").strip()
    }
    task_kind = task_type(task)
    phase = task_phase(task)
    gate = approval_gate(task)

    if not str(task.get("task_id") or "").strip():
        errors.append("missing_task_id")
    if not task_ref:
        errors.append("missing_task_ref")
    if not owner_role:
        errors.append("missing_owner_role")
    if not str(task.get("goal") or "").strip():
        errors.append("missing_goal")
    if not read_scopes:
        errors.append("missing_read_scopes")
    if not write_scopes:
        errors.append("missing_write_scopes")
    if not acceptance_commands:
        errors.append("missing_acceptance_commands")
    if task_kind in IMPLEMENTATION_TASK_TYPES and not str(task.get("initiative_id") or "").strip():
        warnings.append("missing_initiative_id")
    if gate["required"] and gate["status"] not in {"pending", "approved", "rejected"}:
        errors.append(f"invalid_approval_gate_status={gate['status']}")
    if phase == "planning" and task_kind in IMPLEMENTATION_TASK_TYPES:
        errors.append(f"invalid_phase_for_task_type={task_kind}:{phase}")
    for dep_ref in depends_on_task_refs:
        if dep_ref == task_ref:
            errors.append(f"self_dependency={dep_ref}")
            continue
        if known_task_refs and dep_ref not in known_task_refs:
            errors.append(f"missing_dependency_task_ref={dep_ref}")

    for scope in write_scopes:
        owners = plan_lock_owners(plan, scope)
        if not owners:
            errors.append(f"write_scope_unlocked={scope}")
            continue
        if owner_role not in owners:
            errors.append(f"write_scope_owner_mismatch={scope}:{','.join(owners)}")

    if not normalized_string_list(task.get("artifacts")):
        warnings.append("missing_artifacts")
    if not str(task.get("rollback_hint") or "").strip():
        warnings.append("missing_rollback_hint")

    return {"ok": not errors, "errors": errors, "warnings": warnings}


def load_catalog_tasks(path: Path) -> list[dict[str, Any]]:
    payload = load_yaml(path)
    tasks = payload.get("tasks")
    if not isinstance(tasks, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in tasks:
        if not isinstance(item, dict):
            continue
        normalized.append(
            {
                "task_id": str(item.get("task_id") or "").strip(),
                "task_ref": str(item.get("task_ref") or "").strip(),
                "initiative_id": str(item.get("initiative_id") or "").strip() or None,
                "parent_task_id": str(item.get("parent_task_id") or "").strip() or None,
                "owner_role": str(item.get("owner_role") or "").strip(),
                "priority": normalized_int(item.get("priority", 100), 100),
                "summary": str(item.get("summary") or item.get("task_ref") or "").strip(),
                "shift_id": str(item.get("shift_id") or "").strip() or None,
                "goal": str(item.get("goal") or "").strip(),
                "task_type": str(item.get("task_type") or "implementation").strip() or "implementation",
                "phase": str(item.get("phase") or "").strip() or None,
                "approval_gate": item.get("approval_gate") if isinstance(item.get("approval_gate"), dict) else None,
                "execution_mode": str(item.get("execution_mode") or "codex_agent").strip() or "codex_agent",
                "batch_id": str(item.get("batch_id") or "").strip() or None,
                "depends_on_task_refs": normalized_string_list(item.get("depends_on_task_refs")),
                "constraints": normalized_string_list(item.get("constraints")),
                "read_scopes": normalized_string_list(item.get("read_scopes")),
                "write_scopes": normalized_string_list(item.get("write_scopes")),
                "artifacts": normalized_string_list(item.get("artifacts")),
                "acceptance_commands": normalized_string_list(item.get("acceptance_commands")),
                "rollback_hint": str(item.get("rollback_hint") or "").strip(),
                "risk_notes_required": bool(item.get("risk_notes_required", True)),
                "collaborators": normalized_string_list(item.get("collaborators")),
                "model_hint": str(item.get("model_hint") or "").strip() or None,
                "source_refs": normalized_string_list(item.get("source_refs")),
                "plan_links": item.get("plan_links") if isinstance(item.get("plan_links"), list) else [],
                "produces": normalized_string_list(item.get("produces")),
                "consumes": normalized_string_list(item.get("consumes")),
            }
        )
    return normalized


def load_initiative_tasks(path: Path, initiative_id: str | None = None) -> list[dict[str, Any]]:
    payload = load_named_mapping(path, "tasks")
    normalized: list[dict[str, Any]] = []
    requested_initiative = str(initiative_id or "").strip()
    for task_id, raw in payload["tasks"].items():
        if not isinstance(raw, dict):
            continue
        item = dict(raw)
        item["task_id"] = str(item.get("task_id") or task_id).strip()
        item["task_ref"] = str(item.get("task_ref") or item["task_id"]).strip()
        item["summary"] = str(item.get("summary") or item["task_ref"]).strip()
        item["initiative_id"] = str(item.get("initiative_id") or "").strip() or None
        item["parent_task_id"] = str(item.get("parent_task_id") or "").strip() or None
        item["owner_role"] = str(item.get("owner_role") or "").strip()
        item["shift_id"] = str(item.get("shift_id") or "").strip() or None
        item["goal"] = str(item.get("goal") or "").strip()
        item["task_type"] = str(item.get("task_type") or "implementation").strip() or "implementation"
        item["phase"] = str(item.get("phase") or "").strip() or None
        item["approval_gate"] = item.get("approval_gate") if isinstance(item.get("approval_gate"), dict) else None
        item["execution_mode"] = str(item.get("execution_mode") or "codex_agent").strip() or "codex_agent"
        item["batch_id"] = str(item.get("batch_id") or "").strip() or None
        item["priority"] = normalized_int(item.get("priority", 100), 100)
        item["depends_on_task_refs"] = normalized_string_list(item.get("depends_on_task_refs"))
        item["constraints"] = normalized_string_list(item.get("constraints"))
        item["read_scopes"] = normalized_string_list(item.get("read_scopes"))
        item["write_scopes"] = normalized_string_list(item.get("write_scopes"))
        item["artifacts"] = normalized_string_list(item.get("artifacts"))
        item["acceptance_commands"] = normalized_string_list(item.get("acceptance_commands"))
        item["rollback_hint"] = str(item.get("rollback_hint") or "").strip()
        item["risk_notes_required"] = bool(item.get("risk_notes_required", True))
        item["collaborators"] = normalized_string_list(item.get("collaborators"))
        item["model_hint"] = str(item.get("model_hint") or "").strip() or None
        item["source_refs"] = normalized_string_list(item.get("source_refs"))
        item["plan_links"] = item.get("plan_links") if isinstance(item.get("plan_links"), list) else []
        item["produces"] = normalized_string_list(item.get("produces"))
        item["consumes"] = normalized_string_list(item.get("consumes"))
        if requested_initiative and item["initiative_id"] != requested_initiative:
            continue
        normalized.append(item)
    return normalized


def resolve_task_source(args: argparse.Namespace) -> list[dict[str, Any]]:
    if str(getattr(args, "source", "catalog") or "catalog").strip() == "initiative":
        return load_initiative_tasks(resolve_path(args.initiative_tasks_file), getattr(args, "initiative_id", None))
    return load_catalog_tasks(resolve_path(args.catalog))


def approval_lookup(path: Path) -> dict[str, Any]:
    return load_named_mapping(path, "approvals")


def execution_batch_lookup(path: Path) -> dict[str, Any]:
    return load_named_mapping(path, "batches")


def initiative_lookup(path: Path) -> dict[str, Any]:
    return load_named_mapping(path, "initiatives")


def initiative_approval_status(task: dict[str, Any], approvals: dict[str, Any], initiatives: dict[str, Any]) -> str:
    initiative_id = str(task.get("initiative_id") or "").strip()
    if not initiative_id:
        return "missing"
    approval = approvals["approvals"].get(initiative_id, {}) if isinstance(approvals.get("approvals"), dict) else {}
    if isinstance(approval, dict):
        status = str(approval.get("status") or "").strip().lower()
        if status:
            return status
    initiative = initiatives["initiatives"].get(initiative_id, {}) if isinstance(initiatives.get("initiatives"), dict) else {}
    if isinstance(initiative, dict):
        status = str(((initiative.get("approval") if isinstance(initiative.get("approval"), dict) else {}).get("status") or "")).strip().lower()
        if status:
            return status
    return "missing"


def existing_dispatch_count(task_id: str, broker_state: dict[str, Any], dispatches: list[dict[str, Any]]) -> int:
    count = 0
    work_order = broker_state.get("work_orders", {}).get(task_id, {})
    if isinstance(work_order, dict):
        try:
            count = max(count, int(work_order.get("dispatch_count", 0) or 0))
        except (TypeError, ValueError):
            count = max(count, 0)
    pattern = re.compile(rf"^{re.escape(task_id)}#codex#(\d+)$")
    for dispatch in dispatches:
        dispatch_id = str(dispatch.get("dispatch_id") or "").strip()
        match = pattern.match(dispatch_id)
        if match:
            count = max(count, int(match.group(1)))
    return count


def work_order_status(broker_state: dict[str, Any], task_id: str) -> str:
    work_order = broker_state.get("work_orders", {}).get(task_id, {})
    if not isinstance(work_order, dict):
        return "unseeded"
    status = str(work_order.get("status") or "").strip().lower()
    return status or "unseeded"


def task_readiness(task: dict[str, Any], tasks: list[dict[str, Any]], broker_state: dict[str, Any]) -> dict[str, Any]:
    dependencies = normalized_string_list(task.get("depends_on_task_refs"))
    dependency_statuses: list[dict[str, Any]] = []
    blocked_reasons: list[str] = []

    for dep_ref in dependencies:
        dependency_task = find_task(tasks, dep_ref)
        if dependency_task is None:
            dependency_statuses.append(
                {
                    "task_ref": dep_ref,
                    "task_id": None,
                    "status": "missing",
                    "ready": False,
                }
            )
            blocked_reasons.append(f"missing_dependency_task_ref={dep_ref}")
            continue

        dep_status = work_order_status(broker_state, str(dependency_task.get("task_id") or ""))
        ready = dep_status in COMPLETED_WORK_ORDER_STATUSES
        dependency_statuses.append(
            {
                "task_ref": dep_ref,
                "task_id": dependency_task.get("task_id"),
                "status": dep_status,
                "ready": ready,
            }
        )
        if not ready:
            blocked_reasons.append(f"dependency_not_completed={dep_ref}:{dep_status}")

    return {
        "ready": not blocked_reasons,
        "depends_on_task_refs": dependencies,
        "dependency_statuses": dependency_statuses,
        "blocked_reasons": blocked_reasons,
    }


def task_dispatch_readiness(
    task: dict[str, Any],
    tasks: list[dict[str, Any]],
    broker_state: dict[str, Any],
    approvals: dict[str, Any],
    initiatives: dict[str, Any],
    execution_batches: dict[str, Any],
) -> dict[str, Any]:
    readiness = task_readiness(task, tasks, broker_state)
    gate = approval_gate(task)
    batch_id = str(task.get("batch_id") or "").strip()
    approval_status = initiative_approval_status(task, approvals, initiatives)
    blocked = list(readiness["blocked_reasons"])
    if gate["required"] and gate["status"] != "approved":
        if approval_status != "approved":
            blocked.append(f"approval_not_granted={approval_status or 'missing'}")
        if batch_id:
            batch = execution_batches["batches"].get(batch_id, {}) if isinstance(execution_batches.get("batches"), dict) else {}
            batch_status = str((batch.get("status") if isinstance(batch, dict) else "") or "").strip().lower()
            if batch_status not in {"approved", "ready", "running"}:
                blocked.append(f"batch_not_approved={batch_status or 'missing'}")
        else:
            blocked.append("missing_batch_id")
    return {
        **readiness,
        "dispatch_ready": not blocked,
        "blocked_reasons": blocked,
        "approval_gate": gate,
        "approval_status": approval_status,
        "batch_id": batch_id or None,
    }


def seedable_tasks(args: argparse.Namespace, tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected = tasks
    role = str(getattr(args, "role", "") or "").strip()
    task_refs = [str(item).strip() for item in getattr(args, "task_ref", []) if str(item).strip()]
    initiative_id = str(getattr(args, "initiative_id", "") or "").strip()
    batch_id = str(getattr(args, "batch_id", "") or "").strip()

    if role:
        selected = [task for task in selected if str(task.get("owner_role") or "").strip() == role]
    if initiative_id:
        selected = [task for task in selected if str(task.get("initiative_id") or "").strip() == initiative_id]
    if batch_id:
        selected = [task for task in selected if str(task.get("batch_id") or "").strip() == batch_id]
    if task_refs:
        wanted = set(task_refs)
        selected = [task for task in selected if str(task.get("task_ref") or "").strip() in wanted]
    if not getattr(args, "all", False) and not task_refs and not role and not initiative_id and not batch_id and getattr(args, "command", "") == "seed":
        return []
    return selected


def list_tasks(args: argparse.Namespace) -> dict[str, Any]:
    plan = load_json(resolve_path(args.plan))
    tasks = resolve_task_source(args)
    broker_state = ensure_broker_state(load_json(resolve_path(args.broker_state)))
    approvals = approval_lookup(resolve_path(args.approvals_file))
    initiatives = initiative_lookup(resolve_path(args.initiatives_file))
    execution_batches = execution_batch_lookup(resolve_path(args.execution_batches_file))

    items: list[dict[str, Any]] = []
    for task in seedable_tasks(args, tasks):
        validation = validate_task(task, plan, tasks)
        readiness = task_dispatch_readiness(task, tasks, broker_state, approvals, initiatives, execution_batches)
        items.append(
            {
                "task_ref": task["task_ref"],
                "task_id": task["task_id"],
                "initiative_id": task.get("initiative_id"),
                "task_type": task_type(task),
                "phase": task_phase(task),
                "approval_gate": approval_gate(task),
                "batch_id": task.get("batch_id"),
                "owner_role": task["owner_role"],
                "shift_id": task.get("shift_id"),
                "summary": task["summary"],
                "validation": validation,
                "readiness": readiness,
                "broker_status": work_order_status(broker_state, task["task_id"]),
            }
        )
    return {"status": "ok", "task_count": len(items), "tasks": items}


def show_task(args: argparse.Namespace) -> dict[str, Any]:
    plan = load_json(resolve_path(args.plan))
    tasks = resolve_task_source(args)
    broker_state = ensure_broker_state(load_json(resolve_path(args.broker_state)))
    approvals = approval_lookup(resolve_path(args.approvals_file))
    initiatives = initiative_lookup(resolve_path(args.initiatives_file))
    execution_batches = execution_batch_lookup(resolve_path(args.execution_batches_file))
    task = find_task(tasks, args.task_ref)
    if task is None:
        return {"status": "missing", "task_ref": str(args.task_ref)}
    return {
        "status": "ok",
        "task": task,
        "validation": validate_task(task, plan, tasks),
        "readiness": task_dispatch_readiness(task, tasks, broker_state, approvals, initiatives, execution_batches),
    }


def seed_one_task(
    *,
    task: dict[str, Any],
    catalog_tasks: list[dict[str, Any]],
    plan: dict[str, Any],
    approvals: dict[str, Any],
    initiatives: dict[str, Any],
    execution_batches: dict[str, Any],
    broker_state: dict[str, Any],
    dispatches_path: Path,
    dispatches: list[dict[str, Any]],
    when: datetime,
    requested_by: str,
    force: bool,
    dry_run: bool,
) -> dict[str, Any]:
    validation = validate_task(task, plan, catalog_tasks)
    readiness = task_dispatch_readiness(task, catalog_tasks, broker_state, approvals, initiatives, execution_batches)
    if not validation["ok"]:
        return {"status": "invalid", "task_ref": task["task_ref"], "validation": validation, "readiness": readiness}

    if not force and not readiness["dispatch_ready"]:
        return {"status": "blocked", "task_ref": task["task_ref"], "validation": validation, "readiness": readiness}

    task_id = str(task.get("task_id") or "").strip()
    work_order = broker_state["work_orders"].get(task_id, {})
    if not isinstance(work_order, dict):
        work_order = {}

    active_status = str(work_order.get("status") or "").strip().lower()
    if not force and active_status in ACTIVE_WORK_ORDER_STATUSES:
        return {
            "status": "skipped",
            "task_ref": task["task_ref"],
            "reason": f"active_work_order={active_status}",
            "dispatch_id": work_order.get("last_work_order_id"),
            "readiness": readiness,
        }
    if not force and active_status in COMPLETED_WORK_ORDER_STATUSES:
        return {
            "status": "skipped",
            "task_ref": task["task_ref"],
            "reason": f"existing_work_order={active_status}",
            "dispatch_id": work_order.get("last_work_order_id"),
            "readiness": readiness,
        }

    next_count = existing_dispatch_count(task_id, broker_state, dispatches) + 1
    dispatch_id = f"{task_id}#codex#{next_count}"
    payload = {
        "dispatch_id": dispatch_id,
        "task_id": task_id,
        "initiative_id": task.get("initiative_id"),
        "owner_role": task["owner_role"],
        "summary": task["summary"],
        "task_ref": task["task_ref"],
        "shift_id": task.get("shift_id"),
        "delivery_mode": "codex_agent",
        "task_contract_version": "v2",
        "task_contract": task_contract(task),
        "executor_rule": "manual-codex-pilot-seed",
        "emitted_at": when.isoformat(),
        "requested_by": requested_by,
        "model_hint": task.get("model_hint"),
        "source_refs": task.get("source_refs"),
        "plan_links": task.get("plan_links"),
        "batch_id": task.get("batch_id"),
    }

    work_order_payload = {
        "task_id": task_id,
        "initiative_id": task.get("initiative_id"),
        "parent_task_id": task.get("parent_task_id"),
        "task_type": task_type(task),
        "phase": task_phase(task),
        "approval_gate": approval_gate(task),
        "batch_id": task.get("batch_id"),
        "owner_role": task["owner_role"],
        "summary": task["summary"],
        "task_ref": task["task_ref"],
        "shift_id": task.get("shift_id"),
        "status": "dispatched",
        "artifacts": normalized_string_list(task.get("artifacts")),
        "write_scopes": normalized_string_list(task.get("write_scopes")),
        "goal": str(task.get("goal") or "").strip(),
        "depends_on_task_refs": normalized_string_list(task.get("depends_on_task_refs")),
        "constraints": normalized_string_list(task.get("constraints")),
        "read_scopes": normalized_string_list(task.get("read_scopes")),
        "acceptance_commands": normalized_string_list(task.get("acceptance_commands")),
        "risk_notes_required": bool(task.get("risk_notes_required", True)),
        "rollback_hint": str(task.get("rollback_hint") or "").strip(),
        "collaborators": normalized_string_list(task.get("collaborators")),
        "dispatch_channel": "codex_agent",
        "dispatched_at": when.isoformat(),
        "dispatch_count": next_count,
        "last_work_order_id": dispatch_id,
        "last_result": None,
        "created_at": work_order.get("created_at") or when.isoformat(),
        "updated_at": when.isoformat(),
        "task_source": "initiative_task_graph" if task.get("initiative_id") else "codex_pilot_catalog",
    }

    if not dry_run:
        append_jsonl(dispatches_path, payload)
        broker_state["work_orders"][task_id] = work_order_payload
        broker_state["updated_at"] = when.isoformat()

    return {
        "status": "seeded" if not dry_run else "preview",
        "task_ref": task["task_ref"],
        "task_id": task_id,
        "dispatch_id": dispatch_id,
        "owner_role": task["owner_role"],
        "validation": validation,
        "readiness": readiness,
    }


def seed_tasks(args: argparse.Namespace) -> dict[str, Any]:
    plan = load_json(resolve_path(args.plan))
    tasks = resolve_task_source(args)
    broker_state_path = resolve_path(args.broker_state)
    dispatches_path = resolve_path(args.dispatches_file)
    approvals = approval_lookup(resolve_path(args.approvals_file))
    initiatives = initiative_lookup(resolve_path(args.initiatives_file))
    execution_batches = execution_batch_lookup(resolve_path(args.execution_batches_file))
    broker_state = ensure_broker_state(load_json(broker_state_path))
    dispatches = load_dispatches(dispatches_path)
    when = resolve_now(args.at)

    selected = seedable_tasks(args, tasks)
    if not selected:
        return {
            "status": "empty_selection",
            "detail": "use --task-ref/--role/--initiative-id/--batch-id/--all to select tasks",
        }

    results = [
        seed_one_task(
            task=task,
            catalog_tasks=tasks,
            plan=plan,
            approvals=approvals,
            initiatives=initiatives,
            execution_batches=execution_batches,
            broker_state=broker_state,
            dispatches_path=dispatches_path,
            dispatches=dispatches,
            when=when,
            requested_by=str(args.requested_by or "orchestrator").strip() or "orchestrator",
            force=bool(args.force),
            dry_run=bool(args.dry_run),
        )
        for task in selected
    ]

    if not args.dry_run:
        write_json(broker_state_path, broker_state)

    seeded = [item for item in results if item["status"] in {"seeded", "preview"}]
    return {
        "status": "ok",
        "source": str(getattr(args, "source", "catalog") or "catalog"),
        "selected_count": len(selected),
        "seeded_count": len(seeded),
        "results": results,
        "dispatches_file": str(dispatches_path),
        "broker_state": str(broker_state_path),
    }


def emit(payload: dict[str, Any], as_json: bool) -> int:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(payload, ensure_ascii=False))
    return 0


def main() -> int:
    args = parse_args()
    if args.command == "list":
        return emit(list_tasks(args), args.json)
    if args.command == "show":
        return emit(show_task(args), args.json)
    if args.command == "seed":
        return emit(seed_tasks(args), args.json)
    return emit({"status": "unsupported_command"}, False)


if __name__ == "__main__":
    raise SystemExit(main())
