#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from ai_team_event_log import DEFAULT_EVENT_LOG, append_event
from ai_team_result_collector import collect_result
from ai_team_runtime_policy import validate_commands
from ai_team_runtime_state import DEFAULT_RUNTIME_STATE, expired_attempts, load_runtime_state, mark_cleanup, register_attempt, update_attempt
DEFAULT_DISPATCHES = ROOT / "docs/ai-team/operations/M1_M2_72H_CODEX_AGENT_DISPATCHES.jsonl"
DEFAULT_NOTIFICATIONS = ROOT / "docs/ai-team/operations/M1_M2_72H_AGENT_NOTIFICATIONS.jsonl"
DEFAULT_STATE = ROOT / "docs/ai-team/operations/M1_M2_72H_CODEX_AGENT_RUNNER_STATE.json"
DEFAULT_BROKER_STATE = ROOT / "docs/ai-team/operations/M1_M2_72H_AGENT_BROKER.json"
DEFAULT_WORKTREE_ROOT = ROOT / ".ai-team-worktrees"
DEFAULT_TRANSCRIPT_ROOT = ROOT / "docs/ai-team/runtime-transcripts"
DEFAULT_ARTIFACT_ROOT = ROOT / "docs/ai-team/runtime-artifacts"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the ai-team worker supervisor skeleton.")
    parser.add_argument("--dispatches-file", default=str(DEFAULT_DISPATCHES))
    parser.add_argument("--notifications-file", default=str(DEFAULT_NOTIFICATIONS))
    parser.add_argument("--state-file", default=str(DEFAULT_STATE))
    parser.add_argument("--broker-state", default=str(DEFAULT_BROKER_STATE))
    parser.add_argument("--runtime-state", default=str(DEFAULT_RUNTIME_STATE))
    parser.add_argument("--event-log", default=str(DEFAULT_EVENT_LOG))
    parser.add_argument("--worktree-root", default=str(DEFAULT_WORKTREE_ROOT))
    parser.add_argument("--transcript-root", default=str(DEFAULT_TRANSCRIPT_ROOT))
    parser.add_argument("--artifact-root", default=str(DEFAULT_ARTIFACT_ROOT))
    parser.add_argument("--role", required=True)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def resolve_path(raw: str) -> Path:
    path = Path(raw).expanduser()
    return path if path.is_absolute() else ROOT / path


def run_json_command(command: list[str]) -> dict[str, Any]:
    proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    stdout_text = (proc.stdout or "").strip()
    if proc.returncode != 0:
        return {"status": "failed", "command": command, "returncode": proc.returncode, "stdout": stdout_text, "stderr": (proc.stderr or "").strip()}
    try:
        payload = json.loads(stdout_text) if stdout_text else {}
    except json.JSONDecodeError:
        payload = {"status": "invalid_json", "stdout": stdout_text}
    return payload if isinstance(payload, dict) else {"status": "invalid_payload", "payload": payload}


def dispatch_runner_command(args: argparse.Namespace, *extra: str) -> list[str]:
    return [
        sys.executable,
        str(ROOT / "scripts/ai_team_codex_dispatch_runner.py"),
        "--dispatches-file",
        str(resolve_path(args.dispatches_file)),
        "--notifications-file",
        str(resolve_path(args.notifications_file)),
        "--state-file",
        str(resolve_path(args.state_file)),
        "--broker-state",
        str(resolve_path(args.broker_state)),
        *extra,
    ]


def allocate_worktree(args: argparse.Namespace, dispatch_id: str, attempt_id: str) -> dict[str, Any]:
    return run_json_command(
        [
            sys.executable,
            str(ROOT / "scripts/ai_team_worktree_manager.py"),
            "--repo",
            str(ROOT),
            "--worktree-root",
            str(resolve_path(args.worktree_root)),
            "allocate",
            "--dispatch-id",
            dispatch_id,
            "--attempt-id",
            attempt_id,
            "--json",
        ]
    )


def claim_next_dispatch(args: argparse.Namespace) -> dict[str, Any]:
    return run_json_command(dispatch_runner_command(args, "claim", "--role", str(args.role), "--json"))


def bootstrap_worker_entry(args: argparse.Namespace, dispatch_id: str, attempt_id: str, task_contract: dict[str, Any]) -> dict[str, Any]:
    contract_file = resolve_path(args.artifact_root) / dispatch_id / attempt_id / "task-contract.json"
    contract_file.parent.mkdir(parents=True, exist_ok=True)
    contract_file.write_text(json.dumps(task_contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    runtime = task_contract.get("runtime") if isinstance(task_contract.get("runtime"), dict) else {}
    provider = str(runtime.get("provider") or "simulation").strip() or "simulation"
    provider_command = str(runtime.get("provider_command") or "").strip() or None
    return run_json_command(
        [
            sys.executable,
            str(ROOT / "scripts/ai_team_worker_entry.py"),
            "--task-contract",
            str(contract_file),
            "--dispatch-id",
            dispatch_id,
            "--attempt-id",
            attempt_id,
            "--artifact-root",
            str(resolve_path(args.artifact_root)),
            "--provider",
            provider,
            *( ["--provider-command", provider_command] if provider_command else [] ),
            "--json",
        ]
    )


def start_terminal_session(args: argparse.Namespace, dispatch_id: str, attempt_id: str, worktree_path: str, entry_payload: dict[str, Any]) -> dict[str, Any]:
    session_id = f"ai-team-{task_safe_name(dispatch_id)}-{task_safe_name(attempt_id)}"
    command_text = str(entry_payload.get("provider_command") or "").strip()
    return run_json_command(
        [
            sys.executable,
            str(ROOT / "scripts/ai_team_session_manager.py"),
            "--transcript-root",
            str(resolve_path(args.transcript_root)),
            "start",
            "--session-id",
            session_id,
            "--workdir",
            worktree_path,
            "--command",
            command_text,
            "--json",
        ]
    )


def task_safe_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in value)


def lease_payload(dispatch: dict[str, Any], attempt_id: str, worktree: dict[str, Any], session: dict[str, Any] | None = None) -> dict[str, Any]:
    runtime = dispatch.get("task_contract", {}).get("runtime", {}) if isinstance(dispatch.get("task_contract"), dict) else {}
    heartbeat_interval = int(runtime.get("heartbeat_interval_seconds") or 30)
    now = datetime.now().astimezone()
    return {
        "attempt_id": attempt_id,
        "worktree_path": str(worktree.get("path") or ""),
        "terminal_backend": str(runtime.get("execution_backend") or "simulation"),
        "worker_session_id": str((session or {}).get("session_id") or "").strip() or None,
        "transcript_path": str((session or {}).get("transcript_path") or "").strip() or None,
        "heartbeat_at": now.isoformat(),
        "lease_expires_at": (now + timedelta(seconds=heartbeat_interval * 3)).isoformat(),
    }


def run_acceptance_commands(args: argparse.Namespace, entry: dict[str, Any], worktree_path: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for raw in entry.get("acceptance_commands") or []:
        command = str(raw or "").strip()
        if not command:
            continue
        proc = subprocess.run(command, cwd=worktree_path or ROOT, shell=True, text=True, capture_output=True, check=False)
        results.append({"command": command, "status": "passed" if proc.returncode == 0 else "failed"})
    return results


def finalize_dispatch(args: argparse.Namespace, dispatch: dict[str, Any], worker: dict[str, Any]) -> dict[str, Any]:
    transcript_path = str(worker.get("transcript_path") or "").strip()
    artifact_root = resolve_path(args.artifact_root) / str(dispatch.get("dispatch_id") or "") / str(worker.get("attempt_id") or "")
    worktree_path = str(worker.get("worktree_path") or "")
    acceptance_results = run_acceptance_commands(args, dispatch.get("task_contract", {}), worktree_path)
    result = collect_result(
        repo=resolve_path(args.worktree_root) / Path(worktree_path).name if worktree_path else ROOT,
        dispatch_id=str(dispatch.get("dispatch_id") or "").strip(),
        task_id=str(dispatch.get("task_id") or "").strip(),
        attempt_id=str(worker.get("attempt_id") or "").strip(),
        artifact_dir=artifact_root,
        write_scopes=list(dispatch.get("task_contract", {}).get("write_scopes") or []),
        tests_run=acceptance_results,
        transcript_path=transcript_path or None,
    )
    if result["status"] == "completed":
        payload = run_json_command(
            dispatch_runner_command(args, "complete", "--dispatch-id", str(dispatch.get("dispatch_id") or ""), "--message", str(result.get("summary") or "completed"), "--json")
        )
        return {"status": "completed", "result": result, "writeback": payload}
    payload = run_json_command(
        dispatch_runner_command(args, "fail", "--dispatch-id", str(dispatch.get("dispatch_id") or ""), "--message", str(result.get("summary") or "failed"), "--json")
    )
    return {"status": "failed", "result": result, "writeback": payload}


def reconcile_runtime(args: argparse.Namespace) -> dict[str, Any]:
    state = load_runtime_state(args.runtime_state)
    workers = state.get("workers", {}) if isinstance(state.get("workers"), dict) else {}
    finalized: list[dict[str, Any]] = []
    cleaned: list[str] = []
    retries: list[dict[str, Any]] = []
    now_iso = datetime.now().astimezone().isoformat()
    for worker in expired_attempts(args.runtime_state, now_iso):
        task_id = str(worker.get("task_id") or "")
        retry_count = int(worker.get("retry_count") or 0)
        max_attempts = int(worker.get("max_attempts") or 1)
        if retry_count + 1 < max_attempts:
            update_attempt(args.runtime_state, task_id=task_id, status="retry_scheduled", heartbeat_at=now_iso, retry_count=retry_count + 1)
            retries.append({"task_id": task_id, "retry_count": retry_count + 1, "status": "retry_scheduled"})
        else:
            update_attempt(args.runtime_state, task_id=task_id, status="lease_expired", heartbeat_at=now_iso)
            mark_cleanup(args.runtime_state, str(worker.get("dispatch_id") or ""), "lease_expired")
            cleaned.append(task_id)
    state = load_runtime_state(args.runtime_state)
    workers = state.get("workers", {}) if isinstance(state.get("workers"), dict) else {}
    for task_id, worker in workers.items():
        if not isinstance(worker, dict):
            continue
        status = str(worker.get("status") or "")
        if status == "cleanup_pending":
            cleaned.append(task_id)
            continue
        if status != "running":
            continue
        session_id = str(worker.get("session_id") or "").strip()
        session_status = run_json_command(
            [
                sys.executable,
                str(ROOT / "scripts/ai_team_session_manager.py"),
                "status",
                "--session-id",
                session_id,
                "--json",
            ]
        )
        if str(session_status.get("status") or "") == "running":
            continue
        dispatch = {
            "dispatch_id": worker.get("dispatch_id"),
            "task_id": task_id,
            "task_contract": {"write_scopes": []},
        }
        finalized_payload = finalize_dispatch(args, dispatch, worker)
        update_attempt(args.runtime_state, task_id=task_id, status="cleanup_pending")
        cleaned.append(task_id)
        finalized.append({"task_id": task_id, **finalized_payload})
    append_event(args.event_log, "runtime_reconciled", {"cleaned_tasks": cleaned, "worker_count": len(workers), "finalized": finalized, "retries": retries})
    return {"status": "ok", "cleaned_tasks": cleaned, "worker_count": len(workers), "finalized": finalized, "retries": retries}


def validate_runtime_intent(entry_payload: dict[str, Any]) -> dict[str, Any]:
    commands = [str(entry_payload.get("provider_command") or "").strip()]
    commands.extend(str(item).strip() for item in (entry_payload.get("acceptance_commands") or []) if str(item).strip())
    return validate_commands(commands)


def run_once(args: argparse.Namespace) -> dict[str, Any]:
    claim = claim_next_dispatch(args)
    if str(claim.get("status") or "") != "claimed":
        return {"status": "idle", "role": args.role, "claim": claim}
    dispatch = claim.get("dispatch") if isinstance(claim.get("dispatch"), dict) else {}
    dispatch_id = str(claim.get("dispatch_id") or dispatch.get("dispatch_id") or "").strip()
    task_id = str(dispatch.get("task_id") or "").strip()
    attempt_id = f"{dispatch_id}-attempt-001"
    worktree = allocate_worktree(args, dispatch_id, attempt_id)
    entry = bootstrap_worker_entry(args, dispatch_id, attempt_id, dispatch.get("task_contract", {}))
    intent_validation = validate_runtime_intent(entry)
    if not intent_validation["ok"]:
        append_event(args.event_log, "worker_attempt_blocked", {"dispatch_id": dispatch_id, "task_id": task_id, "violations": intent_validation["violations"]})
        return {
            "status": "blocked",
            "role": args.role,
            "dispatch_id": dispatch_id,
            "task_id": task_id,
            "attempt_id": attempt_id,
            "worktree": worktree,
            "entry": entry,
            "intent_validation": intent_validation,
        }
    session = start_terminal_session(args, dispatch_id, attempt_id, str(worktree.get("path") or ""), entry)
    register_attempt(
        args.runtime_state,
        dispatch_id=dispatch_id,
        task_id=task_id,
        attempt_id=attempt_id,
        owner_role=str(dispatch.get("owner_role") or args.role),
        worktree_path=str(worktree.get("path") or ""),
        backend=str(dispatch.get("task_contract", {}).get("runtime", {}).get("execution_backend") or "simulation"),
        status="starting_session",
        heartbeat_at=datetime.now().astimezone().isoformat(),
        lease_expires_at=payload["lease_expires_at"] if "payload" in locals() else None,
        retry_count=0,
        max_attempts=int(dispatch.get("task_contract", {}).get("runtime", {}).get("max_attempts") or 1),
    )
    payload = lease_payload(dispatch, attempt_id, worktree, session)
    update_attempt(
        args.runtime_state,
        task_id=task_id,
        status="running",
        heartbeat_at=payload["heartbeat_at"],
        session_id=payload["worker_session_id"],
        transcript_path=payload["transcript_path"],
    )
    append_event(args.event_log, "worker_attempt_registered", {"dispatch_id": dispatch_id, "task_id": task_id, **payload})
    return {
        "status": "claimed",
        "role": args.role,
        "dispatch_id": dispatch_id,
        "task_id": task_id,
        "attempt_id": attempt_id,
        "worktree": worktree,
        "entry": entry,
        "session": session,
        "runtime_state": load_runtime_state(args.runtime_state),
        "lease": payload,
    }


def emit(payload: dict[str, Any], as_json: bool) -> int:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(payload, ensure_ascii=False))
    return 0


def cleanup_janitor(args: argparse.Namespace) -> dict[str, Any]:
    state = load_runtime_state(args.runtime_state)
    queue = state.get("cleanup_queue", []) if isinstance(state.get("cleanup_queue"), list) else []
    cleaned: list[dict[str, Any]] = []
    remaining: list[dict[str, Any]] = []
    for item in queue:
        if not isinstance(item, dict):
            continue
        dispatch_id = str(item.get("dispatch_id") or "").strip()
        reason = str(item.get("reason") or "").strip()
        cleaned.append({"dispatch_id": dispatch_id, "reason": reason})
    state["cleanup_queue"] = remaining
    from ai_team_runtime_state import write_runtime_state
    write_runtime_state(args.runtime_state, state)
    append_event(args.event_log, "cleanup_janitor", {"cleaned": cleaned})
    return {"status": "ok", "cleaned": cleaned}


def watch_loop(args: argparse.Namespace) -> int:
    while True:
        payload = reconcile_runtime(args)
        emit(payload, args.json)
        time.sleep(1.0)


def main() -> int:
    args = parse_args()
    if args.watch:
        return watch_loop(args)
    payload = run_once(args) if args.once else reconcile_runtime(args)
    return emit(payload, args.json)


if __name__ == "__main__":
    raise SystemExit(main())
