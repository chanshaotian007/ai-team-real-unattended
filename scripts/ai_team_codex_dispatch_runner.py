#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DISPATCHES = ROOT / "docs/ai-team/operations/M1_M2_72H_CODEX_AGENT_DISPATCHES.jsonl"
DEFAULT_NOTIFICATIONS = ROOT / "docs/ai-team/operations/M1_M2_72H_AGENT_NOTIFICATIONS.jsonl"
DEFAULT_STATE = ROOT / "docs/ai-team/operations/M1_M2_72H_CODEX_AGENT_RUNNER_STATE.json"
DEFAULT_BROKER_STATE = ROOT / "docs/ai-team/operations/M1_M2_72H_AGENT_BROKER.json"
COMPLETED_WORK_ORDER_STATUSES = {"completed", "accepted", "closed"}
ACTIVE_WORK_ORDER_STATUSES = {"claimed", "preparing_workspace", "starting_session", "running", "collecting_results"}
QUEUED_WORK_ORDER_STATUSES = {"queued", "pending", "dispatched", "retry_scheduled", "lease_expired", "cleanup_pending"}
APPROVAL_ALLOWED_STATUSES = {"approved", "not_required"}
RUNTIME_ACTIVE_STATUSES = {"preparing_workspace", "starting_session", "running", "collecting_results"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bridge Codex agent dispatches to supervisor-compatible notifications.")
    parser.add_argument("--dispatches-file", default=str(DEFAULT_DISPATCHES))
    parser.add_argument("--notifications-file", default=str(DEFAULT_NOTIFICATIONS))
    parser.add_argument("--state-file", default=str(DEFAULT_STATE))
    parser.add_argument("--broker-state", default=str(DEFAULT_BROKER_STATE))
    parser.add_argument("--interval-seconds", type=float, default=15.0)
    parser.add_argument("--json", action="store_true")

    subparsers = parser.add_subparsers(dest="command", required=True)

    init_cmd = subparsers.add_parser("init")
    init_cmd.add_argument("--json", action="store_true")

    claim = subparsers.add_parser("claim")
    claim.add_argument("--role", required=True)
    claim.add_argument("--dispatch-id")
    claim.add_argument("--json", action="store_true")

    status_cmd = subparsers.add_parser("status")
    status_cmd.add_argument("--role")
    status_cmd.add_argument("--json", action="store_true")

    watch_cmd = subparsers.add_parser("watch")
    watch_cmd.add_argument("--role")
    watch_cmd.add_argument("--json", action="store_true")

    heartbeat_cmd = subparsers.add_parser("heartbeat")
    heartbeat_cmd.add_argument("--dispatch-id", required=True)
    heartbeat_cmd.add_argument("--attempt-id")
    heartbeat_cmd.add_argument("--heartbeat-at")
    heartbeat_cmd.add_argument("--lease-expires-at")
    heartbeat_cmd.add_argument("--json", action="store_true")

    expire_cmd = subparsers.add_parser("expire")
    expire_cmd.add_argument("--dispatch-id", required=True)
    expire_cmd.add_argument("--reason", default="lease_expired")
    expire_cmd.add_argument("--json", action="store_true")

    retry_cmd = subparsers.add_parser("retry")
    retry_cmd.add_argument("--dispatch-id", required=True)
    retry_cmd.add_argument("--message")
    retry_cmd.add_argument("--json", action="store_true")

    list_cmd = subparsers.add_parser("list")
    list_cmd.add_argument("--role")
    list_cmd.add_argument("--json", action="store_true")

    complete = subparsers.add_parser("complete")
    complete.add_argument("--dispatch-id", required=True)
    complete.add_argument("--message")
    complete.add_argument("--changed-file", action="append", default=[])
    complete.add_argument("--artifact", action="append", default=[])
    complete.add_argument("--risk-note", action="append", default=[])
    complete.add_argument("--handover-note", action="append", default=[])
    complete.add_argument("--test-result", action="append", default=[], help="JSON object with command/status fields")
    complete.add_argument("--json", action="store_true")

    fail = subparsers.add_parser("fail")
    fail.add_argument("--dispatch-id", required=True)
    fail.add_argument("--message", required=True)
    fail.add_argument("--risk-note", action="append", default=[])
    fail.add_argument("--json", action="store_true")
    return parser.parse_args()


def resolve_path(raw: str) -> Path:
    path = Path(raw).expanduser()
    return path if path.is_absolute() else ROOT / path


def resolve_now() -> datetime:
    return datetime.now().astimezone()


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


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def ensure_state(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    state = payload if isinstance(payload, dict) else {}
    dispatches = state.get("dispatches")
    claims = state.get("claims")
    if not isinstance(dispatches, dict):
        dispatches = {}
    if not isinstance(claims, dict):
        claims = {}
    state["dispatches"] = dispatches
    state["claims"] = claims
    return state


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


def dispatch_contract(dispatch: dict[str, Any]) -> dict[str, Any]:
    payload = dispatch.get("task_contract")
    return payload if isinstance(payload, dict) else {}


def approval_gate_status(dispatch: dict[str, Any], broker_work_order: dict[str, Any] | None = None) -> str:
    contract = dispatch_contract(dispatch)
    gate = contract.get("approval_gate") if isinstance(contract.get("approval_gate"), dict) else {}
    if isinstance(broker_work_order, dict):
        broker_gate = broker_work_order.get("approval_gate") if isinstance(broker_work_order.get("approval_gate"), dict) else {}
        if broker_gate:
            gate = broker_gate
    required = bool(gate.get("required", False))
    if not required:
        return "not_required"
    return str(gate.get("status") or "pending").strip().lower() or "pending"


def task_type(dispatch: dict[str, Any]) -> str:
    contract = dispatch_contract(dispatch)
    return str(contract.get("task_type") or dispatch.get("task_type") or "implementation").strip().lower() or "implementation"


def broker_dispatch_view(entry: dict[str, Any], broker_state: dict[str, Any] | None) -> dict[str, Any]:
    state = ensure_broker_state(broker_state)
    task_id = str(entry.get("task_id") or "").strip()
    dispatch_id = str(entry.get("dispatch_id") or "").strip()
    work_order = state["work_orders"].get(task_id, {}) if task_id else {}
    if not isinstance(work_order, dict):
        work_order = {}
    last_work_order_id = str(work_order.get("last_work_order_id") or "").strip()
    matches = bool(work_order) and (not last_work_order_id or last_work_order_id == dispatch_id)
    gate = work_order.get("delivery_gate") if isinstance(work_order.get("delivery_gate"), dict) else {}
    gate_status = str(gate.get("status") or "").strip().lower()
    return {
        "work_order": work_order,
        "matches": matches,
        "superseded": bool(work_order) and bool(last_work_order_id) and last_work_order_id != dispatch_id,
        "status": str(work_order.get("status") or "").strip().lower(),
        "last_work_order_id": last_work_order_id or None,
        "delivery_gate_status": gate_status or None,
        "approval_gate_status": approval_gate_status(entry, work_order),
        "completion_rejected": gate_status == "rejected" or int(work_order.get("completion_rejected_count", 0) or 0) > 0,
    }


def effective_dispatch_status(
    entry: dict[str, Any],
    dispatch_state: dict[str, Any] | None,
    broker_state: dict[str, Any] | None,
) -> tuple[str, dict[str, Any]]:
    state = dispatch_state if isinstance(dispatch_state, dict) else {}
    raw_status = str(state.get("status") or "queued").strip().lower() or "queued"
    broker_view = broker_dispatch_view(entry, broker_state)
    if broker_view["superseded"]:
        return "superseded", broker_view
    if not broker_view["matches"]:
        return raw_status, broker_view

    broker_status = broker_view["status"]
    if broker_view["completion_rejected"] and raw_status == "completed":
        return "reopened", broker_view
    if broker_view.get("approval_gate_status") not in APPROVAL_ALLOWED_STATUSES and raw_status in {"queued", "pending"}:
        return "awaiting_approval", broker_view
    if broker_status in COMPLETED_WORK_ORDER_STATUSES:
        return "completed", broker_view
    if broker_status == "errored":
        return "errored", broker_view
    if broker_status in ACTIVE_WORK_ORDER_STATUSES:
        return "claimed", broker_view
    if broker_status in QUEUED_WORK_ORDER_STATUSES:
        if raw_status in {"completed", "errored"} or broker_view["completion_rejected"]:
            return "reopened", broker_view
        return "queued", broker_view
    return raw_status, broker_view


def sync_broker_work_order(
    broker_state_path: Path,
    dispatch: dict[str, Any],
    *,
    status: str,
    when: datetime,
    result_message: str | None = None,
    delivery: dict[str, Any] | None = None,
    claimed_by: str | None = None,
) -> None:
    broker_state = ensure_broker_state(load_json(broker_state_path))
    task_id = str(dispatch.get("task_id") or "").strip()
    if not task_id:
        write_json(broker_state_path, broker_state)
        return

    work_order = broker_state["work_orders"].get(task_id, {})
    if not isinstance(work_order, dict):
        work_order = {}

    if not work_order:
        work_order = {
            "task_id": task_id,
            "task_ref": str(dispatch.get("task_ref") or "").strip(),
            "owner_role": str(dispatch.get("owner_role") or "").strip(),
            "summary": str(dispatch.get("summary") or "").strip(),
            "shift_id": str(dispatch.get("shift_id") or "").strip(),
            "dispatch_channel": "codex_agent",
            "last_work_order_id": str(dispatch.get("dispatch_id") or "").strip() or None,
            "created_at": when.isoformat(),
        }

    work_order["task_type"] = task_type(dispatch)
    work_order["approval_gate"] = dispatch_contract(dispatch).get("approval_gate") if isinstance(dispatch_contract(dispatch).get("approval_gate"), dict) else work_order.get("approval_gate")
    work_order["initiative_id"] = str(dispatch.get("initiative_id") or work_order.get("initiative_id") or "").strip() or None
    work_order["batch_id"] = str(dispatch.get("batch_id") or dispatch_contract(dispatch).get("batch_id") or work_order.get("batch_id") or "").strip() or None
    if dispatch_contract(dispatch).get("phase"):
        work_order["phase"] = str(dispatch_contract(dispatch).get("phase") or "").strip() or None
    work_order["status"] = status
    work_order["updated_at"] = when.isoformat()
    work_order["dispatch_channel"] = "codex_agent"
    work_order["last_work_order_id"] = str(dispatch.get("dispatch_id") or "").strip() or work_order.get("last_work_order_id")
    if result_message is not None:
        work_order["last_result"] = result_message
    if delivery is not None:
        work_order["last_delivery"] = delivery
    if claimed_by:
        work_order["claimed_by"] = claimed_by
        work_order["claimed_at"] = when.isoformat()
    elif status == "claimed":
        work_order["claimed_at"] = when.isoformat()
    if status == "completed":
        work_order["completed_at"] = when.isoformat()
    if status == "errored":
        work_order["errored_at"] = when.isoformat()
    broker_state["work_orders"][task_id] = work_order
    broker_state["updated_at"] = when.isoformat()
    write_json(broker_state_path, broker_state)


def ensure_runtime_files(dispatches_path: Path, state_path: Path) -> dict[str, Any]:
    dispatches_created = False
    state_created = False
    dispatches_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    if not dispatches_path.exists():
        dispatches_path.write_text("", encoding="utf-8")
        dispatches_created = True
    if not state_path.exists():
        write_json(state_path, ensure_state({}))
        state_created = True
    else:
        write_json(state_path, ensure_state(load_json(state_path)))
    return {
        "dispatches_file": str(dispatches_path),
        "state_file": str(state_path),
        "dispatches_created": dispatches_created,
        "state_created": state_created,
    }


def update_watch_state(
    state_path: Path,
    *,
    status: str,
    detail: str,
    interval_seconds: float,
    counts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    state = ensure_state(load_json(state_path))
    when = resolve_now()
    watch = state.setdefault("watch", {})
    watch["mode"] = "watch"
    watch["pid"] = os.getpid()
    watch["heartbeat_at"] = when.isoformat()
    watch["interval_seconds"] = interval_seconds
    watch["status"] = status
    watch["detail"] = detail[:400]
    if counts is not None:
        watch["counts"] = counts
    if status == "running":
        watch["last_success_at"] = when.isoformat()
        watch["consecutive_errors"] = 0
        watch.pop("last_error", None)
        watch.pop("last_error_at", None)
    else:
        watch["consecutive_errors"] = int(watch.get("consecutive_errors", 0) or 0) + 1
        watch["last_error_at"] = when.isoformat()
        watch["last_error"] = detail[:400]
    write_json(state_path, state)
    return state


def load_dispatches(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    entries: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        text = raw.strip()
        if not text:
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            entries.append(payload)
    return entries


def find_dispatch(entries: list[dict[str, Any]], dispatch_id: str) -> dict[str, Any] | None:
    for entry in entries:
        if str(entry.get("dispatch_id") or "").strip() == dispatch_id:
            return entry
    return None


def build_notification(
    dispatch: dict[str, Any],
    *,
    state: str,
    message: str,
    when: datetime,
    delivery: dict[str, Any] | None = None,
) -> dict[str, Any]:
    owner_role = str(dispatch.get("owner_role") or "").strip() or "unknown-agent"
    payload = {
        "agent_path": owner_role,
        "agent_id": owner_role,
        "owner_role": owner_role,
        "task_id": str(dispatch.get("task_id") or "").strip(),
        "task_ref": str(dispatch.get("task_ref") or "").strip(),
        "shift_id": str(dispatch.get("shift_id") or "").strip(),
        "summary": str(dispatch.get("summary") or "").strip(),
        "executor_rule": str(dispatch.get("executor_rule") or "").strip() or None,
        "work_order_id": str(dispatch.get("dispatch_id") or "").strip() or None,
        "emitted_at": when.isoformat(),
        "status": {state: message},
    }
    if delivery is not None:
        payload["execution"] = {"delivery": delivery}
    return payload


def parse_test_results(values: list[str]) -> list[dict[str, Any]]:
    parsed: list[dict[str, Any]] = []
    for raw in values:
        text = str(raw).strip()
        if not text:
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        parsed.append(
            {
                "command": str(payload.get("command") or "").strip(),
                "status": str(payload.get("status") or "").strip() or "unknown",
            }
        )
    return parsed


def init_runtime(args: argparse.Namespace) -> dict[str, Any]:
    dispatches_path = resolve_path(args.dispatches_file)
    state_path = resolve_path(args.state_file)
    return {
        "status": "initialized",
        **ensure_runtime_files(dispatches_path, state_path),
    }


def claim_dispatch(args: argparse.Namespace) -> dict[str, Any]:
    dispatches_path = resolve_path(args.dispatches_file)
    notifications_path = resolve_path(args.notifications_file)
    state_path = resolve_path(args.state_file)
    broker_state_path = resolve_path(args.broker_state)
    ensure_runtime_files(dispatches_path, state_path)
    entries = load_dispatches(dispatches_path)
    state = ensure_state(load_json(state_path))
    role = str(args.role or "").strip()
    requested_dispatch_id = str(getattr(args, "dispatch_id", "") or "").strip()
    when = resolve_now()

    for entry in entries:
        dispatch_id = str(entry.get("dispatch_id") or "").strip()
        if not dispatch_id:
            continue
        if str(entry.get("owner_role") or "").strip() != role:
            continue
        if requested_dispatch_id and dispatch_id != requested_dispatch_id:
            continue
        dispatch_state = state["dispatches"].get(dispatch_id, {})
        if not isinstance(dispatch_state, dict):
            dispatch_state = {}
        status = str(dispatch_state.get("status") or "").strip().lower()
        if status in {"claimed", "completed", "errored"}:
            continue
        broker_view = broker_dispatch_view(entry, ensure_broker_state(load_json(broker_state_path)))
        if broker_view.get("approval_gate_status") not in APPROVAL_ALLOWED_STATUSES:
            continue
        dispatch_state.update(
            {
                "status": "claimed",
                "claimed_by": role,
                "claimed_at": when.isoformat(),
                "updated_at": when.isoformat(),
            }
        )
        state["dispatches"][dispatch_id] = dispatch_state
        state["claims"][role] = dispatch_id
        write_json(state_path, state)
        append_jsonl(
            notifications_path,
            build_notification(
                entry,
                state="running",
                message=f"codex agent claimed {dispatch_id}",
                when=when,
                delivery={"mode": "codex_agent", "dispatch_id": dispatch_id, "claim_status": "claimed"},
            ),
        )
        sync_broker_work_order(
            broker_state_path,
            entry,
            status="claimed",
            when=when,
            result_message=f"codex agent claimed {dispatch_id}",
            delivery={"mode": "codex_agent", "dispatch_id": dispatch_id, "claim_status": "claimed"},
            claimed_by=role,
        )
        return {
            "status": "claimed",
            "dispatch_id": dispatch_id,
            "owner_role": role,
            "dispatch": entry,
            "state_file": str(state_path),
            "notifications_file": str(notifications_path),
            "broker_state": str(broker_state_path),
        }

    write_json(state_path, state)
    return {"status": "empty", "owner_role": role, "dispatch_id": requested_dispatch_id or None}


def list_dispatches(args: argparse.Namespace) -> dict[str, Any]:
    dispatches_path = resolve_path(args.dispatches_file)
    state_path = resolve_path(args.state_file)
    broker_state_path = resolve_path(args.broker_state)
    ensure_runtime_files(dispatches_path, state_path)
    entries = load_dispatches(dispatches_path)
    state = ensure_state(load_json(state_path))
    broker_state = ensure_broker_state(load_json(broker_state_path))
    role = str(getattr(args, "role", "") or "").strip()
    items: list[dict[str, Any]] = []
    suppressed_superseded_count = 0
    for entry in entries:
        dispatch_id = str(entry.get("dispatch_id") or "").strip()
        if not dispatch_id:
            continue
        owner_role = str(entry.get("owner_role") or "").strip()
        if role and owner_role != role:
            continue
        dispatch_state = state["dispatches"].get(dispatch_id, {})
        if not isinstance(dispatch_state, dict):
            dispatch_state = {}
        effective_status, broker_view = effective_dispatch_status(entry, dispatch_state, broker_state)
        if broker_view.get("superseded"):
            suppressed_superseded_count += 1
            continue
        items.append(
            {
                "dispatch_id": dispatch_id,
                "owner_role": owner_role,
                "task_id": str(entry.get("task_id") or "").strip(),
                "task_ref": str(entry.get("task_ref") or "").strip(),
                "summary": str(entry.get("summary") or "").strip(),
                "task_type": task_type(entry),
                "approval_gate_status": broker_view["approval_gate_status"],
                "status": effective_status,
                "runner_status": str(dispatch_state.get("status") or "queued").strip() or "queued",
                "broker_status": broker_view["status"] or None,
                "broker_last_work_order_id": broker_view["last_work_order_id"],
                "completion_rejected": bool(broker_view["completion_rejected"]),
                "claimed_by": dispatch_state.get("claimed_by"),
                "claimed_at": dispatch_state.get("claimed_at"),
                "completed_at": dispatch_state.get("completed_at"),
                "errored_at": dispatch_state.get("errored_at"),
            }
        )
    return {
        "status": "ok",
        "role": role or None,
        "dispatch_count": len(items),
        "suppressed_superseded_count": suppressed_superseded_count,
        "dispatches": items,
    }


def status_dispatches(args: argparse.Namespace) -> dict[str, Any]:
    listing = list_dispatches(args)
    counts = {"pending": 0, "queued": 0, "claimed": 0, "completed": 0, "errored": 0, "reopened": 0, "awaiting_approval": 0, "other": 0}
    for item in listing["dispatches"]:
        status = str(item.get("status") or "").strip().lower()
        if status in {"queued", "pending"}:
            counts["pending"] += 1
            counts["queued"] += 1
        elif status in counts:
            counts[status] += 1
        else:
            counts["other"] += 1
    return {
        "status": "ok",
        "role": listing["role"],
        "dispatch_count": listing["dispatch_count"],
        "suppressed_superseded_count": listing.get("suppressed_superseded_count", 0),
        "counts": counts,
        "active_claims": [item for item in listing["dispatches"] if str(item.get("status") or "").strip().lower() == "claimed"],
        "claims": {
            str(item.get("owner_role") or "").strip(): str(item.get("dispatch_id") or "").strip()
            for item in listing["dispatches"]
            if str(item.get("status") or "").strip().lower() == "claimed"
            and str(item.get("owner_role") or "").strip()
            and str(item.get("dispatch_id") or "").strip()
        },
    }


def watch_once(args: argparse.Namespace) -> dict[str, Any]:
    state_path = resolve_path(args.state_file)
    dispatches_path = resolve_path(args.dispatches_file)
    ensure_runtime_files(dispatches_path, state_path)
    payload = status_dispatches(args)
    counts = payload.get("counts", {})
    detail = (
        f"dispatches={payload.get('dispatch_count', 0)} "
        f"pending={counts.get('pending', 0)} "
        f"claimed={counts.get('claimed', 0)} "
        f"completed={counts.get('completed', 0)} "
        f"reopened={counts.get('reopened', 0)} "
        f"errored={counts.get('errored', 0)} "
        f"superseded={payload.get('suppressed_superseded_count', 0)}"
    )
    update_watch_state(
        state_path,
        status="running",
        detail=detail,
        interval_seconds=float(args.interval_seconds or 15.0),
        counts=counts if isinstance(counts, dict) else None,
    )
    state = ensure_state(load_json(state_path))
    state["claims"] = payload.get("claims", {}) if isinstance(payload.get("claims"), dict) else {}
    state["last_payload"] = {
        "dispatch_count": payload.get("dispatch_count", 0),
        "suppressed_superseded_count": payload.get("suppressed_superseded_count", 0),
        "counts": counts if isinstance(counts, dict) else {},
        "role": payload.get("role"),
    }
    write_json(state_path, state)
    payload["state_file"] = str(state_path)
    return payload


def record_watch_failure(args: argparse.Namespace, exc: Exception) -> dict[str, Any]:
    state_path = resolve_path(args.state_file)
    state = update_watch_state(
        state_path,
        status="error",
        detail=str(exc).strip() or exc.__class__.__name__,
        interval_seconds=float(args.interval_seconds or 15.0),
    )
    return {
        "status": "error",
        "dispatch_count": 0,
        "suppressed_superseded_count": 0,
        "counts": {"pending": 0, "queued": 0, "claimed": 0, "completed": 0, "errored": 0, "reopened": 0, "other": 0},
        "active_claims": [],
        "claims": {},
        "error": str(exc).strip() or exc.__class__.__name__,
        "runner_state": state,
    }


def watch_loop(args: argparse.Namespace) -> int:
    while True:
        try:
            payload = watch_once(args)
        except Exception as exc:  # noqa: BLE001
            payload = record_watch_failure(args, exc)
        emit(payload, args.json)
        time.sleep(max(1.0, float(args.interval_seconds or 15.0)))


def update_dispatch_runtime(
    args: argparse.Namespace,
    dispatch_id: str,
    *,
    status: str,
    message: str,
    lease_expires_at: str | None = None,
    heartbeat_at: str | None = None,
    attempt_id: str | None = None,
) -> dict[str, Any]:
    dispatches_path = resolve_path(args.dispatches_file)
    notifications_path = resolve_path(args.notifications_file)
    state_path = resolve_path(args.state_file)
    broker_state_path = resolve_path(args.broker_state)
    ensure_runtime_files(dispatches_path, state_path)
    entries = load_dispatches(dispatches_path)
    state = ensure_state(load_json(state_path))
    dispatch = find_dispatch(entries, dispatch_id)
    if dispatch is None:
        return {"status": "missing", "dispatch_id": dispatch_id}
    when = resolve_now()
    dispatch_state = state["dispatches"].get(dispatch_id, {})
    if not isinstance(dispatch_state, dict):
        dispatch_state = {}
    dispatch_state.update({"status": status, "updated_at": when.isoformat()})
    if heartbeat_at:
        dispatch_state["heartbeat_at"] = heartbeat_at
    if lease_expires_at:
        dispatch_state["lease_expires_at"] = lease_expires_at
    if attempt_id:
        dispatch_state["attempt_id"] = attempt_id
    state["dispatches"][dispatch_id] = dispatch_state
    write_json(state_path, state)
    append_jsonl(notifications_path, build_notification(dispatch, state=status, message=message, when=when, delivery={"mode": "codex_agent", "dispatch_id": dispatch_id, "attempt_id": attempt_id, "heartbeat_at": heartbeat_at, "lease_expires_at": lease_expires_at}))
    sync_broker_work_order(broker_state_path, dispatch, status=status, when=when, result_message=message, delivery={"mode": "codex_agent", "dispatch_id": dispatch_id, "attempt_id": attempt_id, "heartbeat_at": heartbeat_at, "lease_expires_at": lease_expires_at})
    return {"status": status, "dispatch_id": dispatch_id, "state_file": str(state_path), "broker_state": str(broker_state_path)}


def complete_dispatch(args: argparse.Namespace) -> dict[str, Any]:
    dispatches_path = resolve_path(args.dispatches_file)
    notifications_path = resolve_path(args.notifications_file)
    state_path = resolve_path(args.state_file)
    broker_state_path = resolve_path(args.broker_state)
    ensure_runtime_files(dispatches_path, state_path)
    entries = load_dispatches(dispatches_path)
    state = ensure_state(load_json(state_path))
    dispatch_id = str(args.dispatch_id or "").strip()
    dispatch = find_dispatch(entries, dispatch_id)
    if dispatch is None:
        return {"status": "missing", "dispatch_id": dispatch_id}

    when = resolve_now()
    message = str(args.message or f"codex agent completed {dispatch_id}").strip()
    delivery = {
        "mode": "codex_agent",
        "dispatch_id": dispatch_id,
        "changed_files": [str(item).strip() for item in args.changed_file if str(item).strip()],
        "artifacts_produced": [str(item).strip() for item in args.artifact if str(item).strip()],
        "risk_notes": [str(item).strip() for item in args.risk_note if str(item).strip()],
        "handover_notes": [str(item).strip() for item in args.handover_note if str(item).strip()],
        "tests_run": parse_test_results(args.test_result),
    }
    append_jsonl(notifications_path, build_notification(dispatch, state="completed", message=message, when=when, delivery=delivery))

    dispatch_state = state["dispatches"].get(dispatch_id, {})
    if not isinstance(dispatch_state, dict):
        dispatch_state = {}
    dispatch_state.update({"status": "completed", "completed_at": when.isoformat(), "updated_at": when.isoformat()})
    state["dispatches"][dispatch_id] = dispatch_state
    role = str(dispatch.get("owner_role") or "").strip()
    if state["claims"].get(role) == dispatch_id:
        state["claims"].pop(role, None)
    write_json(state_path, state)
    sync_broker_work_order(
        broker_state_path,
        dispatch,
        status="completed",
        when=when,
        result_message=message,
        delivery=delivery,
    )
    return {
        "status": "completed",
        "dispatch_id": dispatch_id,
        "notifications_file": str(notifications_path),
        "broker_state": str(broker_state_path),
    }


def fail_dispatch(args: argparse.Namespace) -> dict[str, Any]:
    dispatches_path = resolve_path(args.dispatches_file)
    notifications_path = resolve_path(args.notifications_file)
    state_path = resolve_path(args.state_file)
    broker_state_path = resolve_path(args.broker_state)
    ensure_runtime_files(dispatches_path, state_path)
    entries = load_dispatches(dispatches_path)
    state = ensure_state(load_json(state_path))
    dispatch_id = str(args.dispatch_id or "").strip()
    dispatch = find_dispatch(entries, dispatch_id)
    if dispatch is None:
        return {"status": "missing", "dispatch_id": dispatch_id}

    when = resolve_now()
    message = str(args.message or "").strip() or f"codex agent failed {dispatch_id}"
    delivery = {
        "mode": "codex_agent",
        "dispatch_id": dispatch_id,
        "risk_notes": [str(item).strip() for item in args.risk_note if str(item).strip()],
    }
    append_jsonl(notifications_path, build_notification(dispatch, state="errored", message=message, when=when, delivery=delivery))

    dispatch_state = state["dispatches"].get(dispatch_id, {})
    if not isinstance(dispatch_state, dict):
        dispatch_state = {}
    dispatch_state.update({"status": "errored", "errored_at": when.isoformat(), "updated_at": when.isoformat()})
    state["dispatches"][dispatch_id] = dispatch_state
    role = str(dispatch.get("owner_role") or "").strip()
    if state["claims"].get(role) == dispatch_id:
        state["claims"].pop(role, None)
    write_json(state_path, state)
    sync_broker_work_order(
        broker_state_path,
        dispatch,
        status="errored",
        when=when,
        result_message=message,
        delivery=delivery,
    )
    return {
        "status": "errored",
        "dispatch_id": dispatch_id,
        "notifications_file": str(notifications_path),
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
    if args.command == "init":
        return emit(init_runtime(args), args.json)
    if args.command == "claim":
        return emit(claim_dispatch(args), args.json)
    if args.command == "list":
        return emit(list_dispatches(args), args.json)
    if args.command == "status":
        return emit(status_dispatches(args), args.json)
    if args.command == "watch":
        return watch_loop(args)
    if args.command == "heartbeat":
        return emit(update_dispatch_runtime(args, str(args.dispatch_id), status="running", message=f"heartbeat for {args.dispatch_id}", lease_expires_at=str(getattr(args, 'lease_expires_at', '') or '').strip() or None, heartbeat_at=str(getattr(args, 'heartbeat_at', '') or '').strip() or None, attempt_id=str(getattr(args, 'attempt_id', '') or '').strip() or None), args.json)
    if args.command == "expire":
        return emit(update_dispatch_runtime(args, str(args.dispatch_id), status="lease_expired", message=str(getattr(args, 'reason', '') or '').strip() or f"lease expired for {args.dispatch_id}"), args.json)
    if args.command == "retry":
        return emit(update_dispatch_runtime(args, str(args.dispatch_id), status="retry_scheduled", message=str(getattr(args, 'message', '') or '').strip() or f"retry scheduled for {args.dispatch_id}"), args.json)
    if args.command == "complete":
        return emit(complete_dispatch(args), args.json)
    if args.command == "fail":
        return emit(fail_dispatch(args), args.json)
    return emit({"status": "unsupported_command"}, args.json)


if __name__ == "__main__":
    raise SystemExit(main())
