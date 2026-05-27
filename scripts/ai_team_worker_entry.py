#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARTIFACT_ROOT = ROOT / "docs/ai-team/runtime-artifacts"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap a worker attempt inside an isolated workspace.")
    parser.add_argument("--task-contract", required=True)
    parser.add_argument("--dispatch-id", required=True)
    parser.add_argument("--attempt-id", required=True)
    parser.add_argument("--provider", choices=["simulation", "claude", "codex"], default="simulation")
    parser.add_argument("--provider-command")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def resolve_path(raw: str) -> Path:
    path = Path(raw).expanduser()
    return path if path.is_absolute() else ROOT / path


def load_contract(raw: str) -> dict[str, Any]:
    path = resolve_path(raw)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return json.loads(raw)


def artifact_dir(root: Path, dispatch_id: str, attempt_id: str) -> Path:
    return root / dispatch_id / attempt_id


def result_schema() -> dict[str, Any]:
    return {
        "status": "completed|failed",
        "summary": "short summary",
        "changed_files": ["path/to/file"],
        "artifacts_produced": ["docs/result.json"],
        "tests_run": [{"command": "pytest ...", "status": "passed"}],
        "risk_notes": ["notable risk"],
        "handover_notes": ["next actor guidance"],
    }


def orchestration_prompt(task_contract: dict[str, Any], dispatch_id: str, attempt_id: str, payload_path: Path, provider: str) -> str:
    payload = {
        "dispatch_id": dispatch_id,
        "attempt_id": attempt_id,
        "task_id": task_contract.get("task_id"),
        "owner_role": task_contract.get("owner_role"),
        "goal": task_contract.get("goal"),
        "constraints": task_contract.get("constraints") or [],
        "read_scopes": task_contract.get("read_scopes") or [],
        "write_scopes": task_contract.get("write_scopes") or [],
        "artifacts": task_contract.get("artifacts") or [],
        "acceptance_commands": task_contract.get("acceptance_commands") or [],
        "rollback_hint": task_contract.get("rollback_hint"),
        "result_schema": result_schema(),
        "payload_path": str(payload_path),
        "provider": provider,
    }
    return json.dumps(payload, ensure_ascii=False)


def provider_command(provider: str, payload_path: Path, explicit_command: str | None = None, prompt: str | None = None) -> str:
    override = str(explicit_command or "").strip()
    if override:
        return override
    prompt_text = str(prompt or "Read and execute task context").replace("'", "\\'")
    if provider == "claude":
        return f"claude -p '{prompt_text}'"
    if provider == "codex":
        return f"codex exec '{prompt_text}'"
    return "python3 -c \"import json; print('AI_TEAM_RESULT_BEGIN'); print(json.dumps({'status': 'completed', 'summary': 'simulation completed', 'changed_files': [], 'artifacts_produced': [], 'tests_run': [], 'risk_notes': [], 'handover_notes': []}, ensure_ascii=False)); print('AI_TEAM_RESULT_END')\""


def build_entry_payload(task_contract: dict[str, Any], dispatch_id: str, attempt_id: str, artifact_root: Path, provider: str = "simulation", explicit_command: str | None = None) -> dict[str, Any]:
    target_dir = artifact_dir(artifact_root, dispatch_id, attempt_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "dispatch_id": dispatch_id,
        "attempt_id": attempt_id,
        "task_id": task_contract.get("task_id"),
        "owner_role": task_contract.get("owner_role"),
        "goal": task_contract.get("goal"),
        "constraints": task_contract.get("constraints") or [],
        "read_scopes": task_contract.get("read_scopes") or [],
        "write_scopes": task_contract.get("write_scopes") or [],
        "artifacts": task_contract.get("artifacts") or [],
        "acceptance_commands": task_contract.get("acceptance_commands") or [],
        "artifact_dir": str(target_dir),
        "runtime": task_contract.get("runtime") if isinstance(task_contract.get("runtime"), dict) else {},
        "provider": provider,
        "provider_command": None,
    }
    summary_path = target_dir / "worker-entry.json"
    prompt = orchestration_prompt(task_contract, dispatch_id, attempt_id, summary_path, provider)
    payload["orchestration_prompt"] = prompt
    payload["result_schema"] = result_schema()
    payload["provider_command"] = provider_command(provider, summary_path, explicit_command, prompt)
    summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def emit(payload: dict[str, Any], as_json: bool) -> int:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(payload, ensure_ascii=False))
    return 0


def main() -> int:
    args = parse_args()
    payload = build_entry_payload(
        load_contract(args.task_contract),
        args.dispatch_id,
        args.attempt_id,
        resolve_path(args.artifact_root),
        provider=str(args.provider or "simulation"),
        explicit_command=args.provider_command,
    )
    return emit(payload, args.json)


if __name__ == "__main__":
    raise SystemExit(main())
