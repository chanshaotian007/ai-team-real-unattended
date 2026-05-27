#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNTIME_STATE = ROOT / "docs/ai-team/operations/AI_TEAM_RUNTIME_STATE.json"


RUNTIME_ACTIVE_STATUSES = {
    "preparing_workspace",
    "starting_session",
    "running",
    "collecting_results",
}
RUNTIME_TERMINAL_BACKENDS = {"simulation", "tmux", "pty"}


def resolve_path(raw: str | Path) -> Path:
    path = raw if isinstance(raw, Path) else Path(raw).expanduser()
    return path if path.is_absolute() else ROOT / path


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def ensure_runtime_state(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    state = payload if isinstance(payload, dict) else {}
    workers = state.get("workers")
    sessions = state.get("sessions")
    worktrees = state.get("worktrees")
    cleanup_queue = state.get("cleanup_queue")
    if not isinstance(workers, dict):
        workers = {}
    if not isinstance(sessions, dict):
        sessions = {}
    if not isinstance(worktrees, dict):
        worktrees = {}
    if not isinstance(cleanup_queue, list):
        cleanup_queue = []
    state["workers"] = workers
    state["sessions"] = sessions
    state["worktrees"] = worktrees
    state["cleanup_queue"] = cleanup_queue
    return state


def write_runtime_state(path: str | Path, payload: dict[str, Any]) -> None:
    resolved = resolve_path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_runtime_state(path: str | Path = DEFAULT_RUNTIME_STATE) -> dict[str, Any]:
    return ensure_runtime_state(load_json(resolve_path(path)))


def runtime_session_key(dispatch_id: str, attempt_id: str) -> str:
    return f"{dispatch_id}:{attempt_id}"


def register_attempt(
    path: str | Path,
    *,
    dispatch_id: str,
    task_id: str,
    attempt_id: str,
    owner_role: str,
    worktree_path: str,
    backend: str,
    status: str,
    heartbeat_at: str | None = None,
    lease_expires_at: str | None = None,
    retry_count: int = 0,
    max_attempts: int = 1,
) -> dict[str, Any]:
    state = load_runtime_state(path)
    normalized_backend = backend if backend in RUNTIME_TERMINAL_BACKENDS else "simulation"
    session_key = runtime_session_key(dispatch_id, attempt_id)
    payload = {
        "dispatch_id": dispatch_id,
        "task_id": task_id,
        "attempt_id": attempt_id,
        "owner_role": owner_role,
        "worktree_path": worktree_path,
        "backend": normalized_backend,
        "status": status,
        "heartbeat_at": heartbeat_at,
        "lease_expires_at": lease_expires_at,
        "retry_count": retry_count,
        "max_attempts": max_attempts,
    }
    state["workers"][task_id] = payload
    state["sessions"][session_key] = payload
    state["worktrees"][dispatch_id] = {
        "task_id": task_id,
        "attempt_id": attempt_id,
        "worktree_path": worktree_path,
        "status": status,
    }
    write_runtime_state(path, state)
    return payload


def update_attempt(
    path: str | Path,
    *,
    task_id: str,
    status: str | None = None,
    heartbeat_at: str | None = None,
    session_id: str | None = None,
    transcript_path: str | None = None,
    lease_expires_at: str | None = None,
    retry_count: int | None = None,
) -> dict[str, Any]:
    state = load_runtime_state(path)
    worker = state["workers"].get(task_id, {})
    if not isinstance(worker, dict) or not worker:
        return {}
    if status is not None:
        worker["status"] = status
    if heartbeat_at is not None:
        worker["heartbeat_at"] = heartbeat_at
    if session_id is not None:
        worker["session_id"] = session_id
    if transcript_path is not None:
        worker["transcript_path"] = transcript_path
    if lease_expires_at is not None:
        worker["lease_expires_at"] = lease_expires_at
    if retry_count is not None:
        worker["retry_count"] = retry_count
    state["workers"][task_id] = worker
    session_key = runtime_session_key(str(worker.get("dispatch_id") or ""), str(worker.get("attempt_id") or ""))
    if session_key in state["sessions"]:
        state["sessions"][session_key] = dict(worker)
    dispatch_id = str(worker.get("dispatch_id") or "")
    if dispatch_id and dispatch_id in state["worktrees"] and isinstance(state["worktrees"][dispatch_id], dict):
        state["worktrees"][dispatch_id]["status"] = worker.get("status")
    write_runtime_state(path, state)
    return worker


def expired_attempts(path: str | Path, now_iso: str) -> list[dict[str, Any]]:
    state = load_runtime_state(path)
    workers = state.get("workers", {}) if isinstance(state.get("workers"), dict) else {}
    expired: list[dict[str, Any]] = []
    for worker in workers.values():
        if not isinstance(worker, dict):
            continue
        lease_expires_at = str(worker.get("lease_expires_at") or "").strip()
        if lease_expires_at and lease_expires_at < now_iso and str(worker.get("status") or "") == "running":
            expired.append(worker)
    return expired


def mark_cleanup(path: str | Path, dispatch_id: str, reason: str) -> dict[str, Any]:
    state = load_runtime_state(path)
    state["cleanup_queue"].append({"dispatch_id": dispatch_id, "reason": reason})
    write_runtime_state(path, state)
    return {"dispatch_id": dispatch_id, "reason": reason}
