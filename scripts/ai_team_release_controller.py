#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE = ROOT / "docs/ai-team/operations/RELEASE_CONTROLLER_STATE.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage unattended staging/release/rollback state for ai-team.")
    parser.add_argument("--state-file", default=str(DEFAULT_STATE))
    parser.add_argument("--json", action="store_true")

    subparsers = parser.add_subparsers(dest="command", required=True)

    init_cmd = subparsers.add_parser("init")
    init_cmd.add_argument("--json", action="store_true")

    status_cmd = subparsers.add_parser("status")
    status_cmd.add_argument("--json", action="store_true")

    stage_cmd = subparsers.add_parser("promote-staging")
    stage_cmd.add_argument("--artifact", required=True)
    stage_cmd.add_argument("--environment", default="staging")
    stage_cmd.add_argument("--command", dest="command_text")
    stage_cmd.add_argument("--json", action="store_true")

    verify_cmd = subparsers.add_parser("verify")
    verify_cmd.add_argument("--environment", default="staging")
    verify_cmd.add_argument("--check", required=True)
    verify_cmd.add_argument("--status", choices=["passed", "failed"], required=True)
    verify_cmd.add_argument("--json", action="store_true")

    run_cmd = subparsers.add_parser("run-check")
    run_cmd.add_argument("--environment", default="staging")
    run_cmd.add_argument("--check", required=True)
    run_cmd.add_argument("--command", dest="command_text", required=True)
    run_cmd.add_argument("--json", action="store_true")

    release_cmd = subparsers.add_parser("promote-release")
    release_cmd.add_argument("--artifact", required=True)
    release_cmd.add_argument("--environment", default="production")
    release_cmd.add_argument("--command", dest="command_text")
    release_cmd.add_argument("--json", action="store_true")

    rollback_cmd = subparsers.add_parser("rollback")
    rollback_cmd.add_argument("--environment", default="production")
    rollback_cmd.add_argument("--reason", required=True)
    rollback_cmd.add_argument("--command", dest="command_text")
    rollback_cmd.add_argument("--json", action="store_true")

    return parser.parse_args()


def now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def resolve_path(raw: str) -> Path:
    path = Path(raw).expanduser()
    return path if path.is_absolute() else ROOT / path


def empty_state() -> dict[str, Any]:
    return {
        "generated_at": now_iso(),
        "staging": {"artifact": None, "status": "idle", "verified_checks": []},
        "production": {"artifact": None, "status": "idle"},
        "history": [],
    }


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return empty_state()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return empty_state()
    if not isinstance(payload, dict):
        return empty_state()
    return payload


def write_state(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def append_history(state: dict[str, Any], event: str, details: dict[str, Any]) -> None:
    history = state.get("history")
    if not isinstance(history, list):
        history = []
        state["history"] = history
    history.append({"at": now_iso(), "event": event, "details": details})


def run_shell_command(command: str) -> dict[str, Any]:
    proc = subprocess.run(
        command,
        shell=True,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        executable="/bin/zsh",
    )
    stdout_text = (proc.stdout or "").strip()
    parsed: Any = None
    if stdout_text:
        try:
            parsed = json.loads(stdout_text)
        except json.JSONDecodeError:
            parsed = None
    return {
        "command": command,
        "returncode": proc.returncode,
        "stdout_tail": stdout_text.splitlines()[-40:],
        "stderr_tail": (proc.stderr or "").strip().splitlines()[-40:],
        "parsed": parsed,
    }


def command_passed(result: dict[str, Any]) -> bool:
    returncode = result.get("returncode", 1)
    if returncode is None:
        returncode = 1
    if int(returncode) != 0:
        return False
    parsed = result.get("parsed")
    if isinstance(parsed, dict):
        status = str(parsed.get("status") or "").strip().lower()
        if status:
            return status in {
                "ok",
                "completed",
                "success",
                "passed",
                "promoted",
                "released",
                "rolled_back",
                "open",
                "existing",
                "created",
            }
    return True


def init_state(path: Path) -> dict[str, Any]:
    state = empty_state()
    write_state(path, state)
    return {"status": "initialized", "state_file": str(path), "state": state}


def staging_promote(path: Path, artifact: str, environment: str, command: str | None = None) -> dict[str, Any]:
    state = load_state(path)
    command_result = run_shell_command(command) if command else None
    if command_result is not None and not command_passed(command_result):
        append_history(state, "promote-staging-failed", {"artifact": artifact, "environment": environment, "command_result": command_result})
        write_state(path, state)
        return {"status": "failed", "stage": "staging", "artifact": artifact, "environment": environment, "command_result": command_result}
    state["staging"] = {"artifact": artifact, "status": "promoted", "environment": environment, "verified_checks": []}
    append_history(state, "promote-staging", {"artifact": artifact, "environment": environment, "command_result": command_result})
    write_state(path, state)
    return {"status": "promoted", "stage": "staging", "artifact": artifact, "environment": environment, "command_result": command_result}


def verify_environment(path: Path, environment: str, check: str, status: str) -> dict[str, Any]:
    state = load_state(path)
    target = state.get(environment)
    if not isinstance(target, dict):
        raise RuntimeError(f"unknown environment: {environment}")
    checks = target.get("verified_checks")
    if not isinstance(checks, list):
        checks = []
        target["verified_checks"] = checks
    checks.append({"check": check, "status": status, "at": now_iso()})
    if environment == "staging":
        target["status"] = "verified" if status == "passed" else "blocked"
    append_history(state, "verify", {"environment": environment, "check": check, "status": status})
    write_state(path, state)
    return {"status": status, "environment": environment, "check": check}


def run_check(path: Path, environment: str, check: str, command: str) -> dict[str, Any]:
    result = run_shell_command(command)
    status = "passed" if command_passed(result) else "failed"
    verify_result = verify_environment(path, environment, check, status)
    payload = {
        "status": verify_result["status"],
        "environment": environment,
        "check": check,
        "command_result": result,
    }
    state = load_state(path)
    append_history(state, "run-check", payload)
    write_state(path, state)
    return payload


def promote_release(path: Path, artifact: str, environment: str, command: str | None = None) -> dict[str, Any]:
    state = load_state(path)
    staging = state.get("staging")
    if not isinstance(staging, dict) or staging.get("status") != "verified":
        raise RuntimeError("staging_not_verified")
    command_result = run_shell_command(command) if command else None
    if command_result is not None and not command_passed(command_result):
        append_history(state, "promote-release-failed", {"artifact": artifact, "environment": environment, "command_result": command_result})
        write_state(path, state)
        return {"status": "failed", "environment": environment, "artifact": artifact, "command_result": command_result}
    state["production"] = {"artifact": artifact, "status": "released", "environment": environment}
    append_history(state, "promote-release", {"artifact": artifact, "environment": environment, "command_result": command_result})
    write_state(path, state)
    return {"status": "released", "environment": environment, "artifact": artifact, "command_result": command_result}


def rollback_release(path: Path, environment: str, reason: str, command: str | None = None) -> dict[str, Any]:
    state = load_state(path)
    command_result = run_shell_command(command) if command else None
    if command_result is not None and not command_passed(command_result):
        append_history(state, "rollback-command-failed", {"environment": environment, "reason": reason, "command_result": command_result})
        write_state(path, state)
        return {"status": "failed", "environment": environment, "reason": reason, "command_result": command_result}
    production = state.get("production")
    if not isinstance(production, dict):
        production = {}
        state["production"] = production
    production["status"] = "rolled_back"
    production["rollback_reason"] = reason
    production["rolled_back_at"] = now_iso()
    append_history(state, "rollback", {"environment": environment, "reason": reason, "command_result": command_result})
    write_state(path, state)
    return {"status": "rolled_back", "environment": environment, "reason": reason, "command_result": command_result}


def status_state(path: Path) -> dict[str, Any]:
    return {"status": "ok", "state_file": str(path), "state": load_state(path)}


def emit(payload: dict[str, Any], as_json: bool) -> int:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(payload, ensure_ascii=False))
    return 0


def main() -> int:
    args = parse_args()
    path = resolve_path(args.state_file)
    if args.command == "init":
        payload = init_state(path)
    elif args.command == "status":
        payload = status_state(path)
    elif args.command == "promote-staging":
        payload = staging_promote(path, args.artifact, args.environment, args.command_text)
    elif args.command == "verify":
        payload = verify_environment(path, args.environment, args.check, args.status)
    elif args.command == "run-check":
        payload = run_check(path, args.environment, args.check, args.command_text)
    elif args.command == "promote-release":
        payload = promote_release(path, args.artifact, args.environment, args.command_text)
    elif args.command == "rollback":
        payload = rollback_release(path, args.environment, args.reason, args.command_text)
    else:
        raise RuntimeError(f"unsupported command: {args.command}")
    return emit(payload, bool(getattr(args, "json", False) or args.json))


if __name__ == "__main__":
    raise SystemExit(main())
