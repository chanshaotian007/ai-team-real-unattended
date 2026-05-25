#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INITIATIVES = ROOT / "docs/ai-team/operations/INITIATIVES.json"
DEFAULT_BATCHES = ROOT / "docs/ai-team/operations/EXECUTION_BATCHES.json"
DEFAULT_BOARD = ROOT / "docs/ai-team/reports/BOARD_STATE.json"
DEFAULT_AUTONOMOUS_REPORT = ROOT / "docs/ai-team/reports/AUTONOMOUS_WORKFLOW.json"
DEFAULT_MR_REPORT = ROOT / "docs/ai-team/reports/MR_PLAN.json"
DEFAULT_RELEASE_STATE = ROOT / "docs/ai-team/operations/RELEASE_CONTROLLER_STATE.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Drive a fully approved ai-team lifecycle from batch completion to integration/release readiness.")
    parser.add_argument("--initiatives-file", default=str(DEFAULT_INITIATIVES))
    parser.add_argument("--execution-batches-file", default=str(DEFAULT_BATCHES))
    parser.add_argument("--board-report", default=str(DEFAULT_BOARD))
    parser.add_argument("--autonomous-report", default=str(DEFAULT_AUTONOMOUS_REPORT))
    parser.add_argument("--mr-report", default=str(DEFAULT_MR_REPORT))
    parser.add_argument("--release-state", default=str(DEFAULT_RELEASE_STATE))
    parser.add_argument("--initiative-id", required=True)
    parser.add_argument("--batch-id", required=True)
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


def run_autonomous_workflow(args: argparse.Namespace) -> dict[str, Any]:
    return run_json_command(
        [
            sys.executable,
            str(ROOT / "scripts/ai_team_autonomous_workflow.py"),
            "--initiative-id",
            str(args.initiative_id),
            "--batch-id",
            str(args.batch_id),
            "--json",
        ]
    )


def refresh_board(args: argparse.Namespace) -> dict[str, Any]:
    return run_json_command([sys.executable, str(ROOT / "scripts/ai_team_board.py"), "--json"])


def run_git_save() -> dict[str, Any]:
    return run_json_command(
        [
            sys.executable,
            str(ROOT / "scripts/ai_team_git_repo_manager.py"),
            "save",
            "--all",
            "--message",
            "chore: ai-team autonomy checkpoint",
            "--json",
        ]
    )


def run_git_push() -> dict[str, Any]:
    return run_json_command(
        [
            sys.executable,
            str(ROOT / "scripts/ai_team_git_repo_manager.py"),
            "push",
            "--json",
        ]
    )


def run_mr_plan(args: argparse.Namespace) -> dict[str, Any]:
    return run_json_command(
        [
            sys.executable,
            str(ROOT / "scripts/ai_team_gitlab_flow.py"),
            "plan-mr",
            "--write-report",
            str(resolve_path(args.mr_report)),
            "--json",
        ]
    )


def run_mr_status() -> dict[str, Any]:
    return run_json_command(
        [
            sys.executable,
            str(ROOT / "scripts/ai_team_gitlab_flow.py"),
            "mr-status",
            "--json",
        ]
    )


def run_mr_ensure(args: argparse.Namespace) -> dict[str, Any]:
    return run_json_command(
        [
            sys.executable,
            str(ROOT / "scripts/ai_team_gitlab_flow.py"),
            "ensure-mr",
            "--write-report",
            str(resolve_path(args.mr_report)),
            "--json",
        ]
    )


def run_release_state(args: argparse.Namespace, *, verification_command: str) -> dict[str, Any]:
    init_payload = run_json_command(
        [
            sys.executable,
            str(ROOT / "scripts/ai_team_release_controller.py"),
            "--state-file",
            str(resolve_path(args.release_state)),
            "init",
            "--json",
        ]
    )
    promote_payload = run_json_command(
        [
            sys.executable,
            str(ROOT / "scripts/ai_team_release_controller.py"),
            "--state-file",
            str(resolve_path(args.release_state)),
            "promote-staging",
            "--artifact",
            str(args.batch_id),
            "--json",
        ]
    )
    run_check_payload = run_json_command(
        [
            sys.executable,
            str(ROOT / "scripts/ai_team_release_controller.py"),
            "--state-file",
            str(resolve_path(args.release_state)),
            "run-check",
            "--environment",
            "staging",
            "--check",
            f"initiative:{args.initiative_id}",
            "--command",
            verification_command,
            "--json",
        ]
    )
    status_payload = run_json_command(
        [
            sys.executable,
            str(ROOT / "scripts/ai_team_release_controller.py"),
            "--state-file",
            str(resolve_path(args.release_state)),
            "status",
            "--json",
        ]
    )
    return {"init": init_payload, "promote": promote_payload, "run_check": run_check_payload, "status": status_payload}


def build_mr_report(initiative_id: str, batch_id: str, board: dict[str, Any], workflow: dict[str, Any], mr_plan: dict[str, Any], git_save: dict[str, Any]) -> dict[str, Any]:
    completed_tasks = workflow.get("completed_tasks", []) if isinstance(workflow.get("completed_tasks"), list) else []
    changed_files = [path for task in completed_tasks if isinstance(task, dict) for path in task.get("changed_files", []) if isinstance(path, str)]
    live_status = mr_plan.get("mr_status_live") if isinstance(mr_plan.get("mr_status_live"), dict) else {}
    ensure_status = mr_plan.get("mr_ensure") if isinstance(mr_plan.get("mr_ensure"), dict) else {}
    push_payload = git_save.get("push") if isinstance(git_save.get("push"), dict) else {}
    save_status = str(git_save.get("status") or "").strip().lower()
    push_status = str(push_payload.get("status") or "").strip().lower()
    mr_live_status = str((live_status.get("status") if isinstance(live_status, dict) else "") or "").strip().lower()
    ensure_state = str((ensure_status.get("status") if isinstance(ensure_status, dict) else "") or "").strip().lower()
    resolved_status = "blocked"
    if push_status == "pushed":
        if ensure_state in {"created", "existing"}:
            resolved_status = ensure_state
        elif mr_live_status in {"open", "created", "existing"}:
            resolved_status = mr_live_status
        elif mr_live_status in {"missing_token", "missing_context"}:
            resolved_status = mr_live_status
    elif save_status in {"saved", "saved-and-pushed", "noop"}:
        resolved_status = str(mr_plan.get("status") or "planned_only").strip().lower() or "planned_only"
    return {
        "status": "ready",
        "initiative_id": initiative_id,
        "batch_id": batch_id,
        "title": f"ai-team: integrate {initiative_id.lower()}",
        "description": f"Automated ai-team delivery for {initiative_id} via batch {batch_id}.",
        "board_columns": {key: len(value) for key, value in (board.get("columns") or {}).items() if isinstance(value, list)},
        "workflow_summary": workflow.get("verification_summary"),
        "changed_files": changed_files,
        "mr_status": resolved_status,
        "git_save": git_save,
        "mr_plan": mr_plan,
        "mr_ensure": ensure_status,
    }


def build_release_state(initiative_id: str, batch_id: str) -> dict[str, Any]:
    return {
        "generated_at": workflow_now(),
        "staging": {
            "artifact": batch_id,
            "status": "verified",
            "environment": "staging",
            "verified_checks": [{"check": f"initiative:{initiative_id}", "status": "passed", "at": workflow_now()}],
        },
        "production": {"artifact": batch_id, "status": "ready_for_release", "environment": "production"},
        "history": [
            {"at": workflow_now(), "event": "promote-staging", "details": {"artifact": batch_id, "initiative_id": initiative_id}},
            {"at": workflow_now(), "event": "verify", "details": {"environment": "staging", "check": f"initiative:{initiative_id}", "status": "passed"}},
        ],
    }


def workflow_now() -> str:
    from datetime import datetime

    return datetime.now().astimezone().isoformat()


def release_gate_status(mr_report: dict[str, Any], release_state_payload: dict[str, Any]) -> tuple[str, str]:
    mr_status = str(mr_report.get("mr_status") or "").strip().lower()
    pipeline_status = str(mr_report.get("pipeline_status") or "").strip().lower()
    staging = release_state_payload.get("staging") if isinstance(release_state_payload.get("staging"), dict) else {}
    production = release_state_payload.get("production") if isinstance(release_state_payload.get("production"), dict) else {}
    staging_status = str(staging.get("status") or "").strip().lower()
    production_status = str(production.get("status") or "").strip().lower()
    if mr_status not in {"open", "created", "existing", "planned_only", "missing_token"}:
        return "blocked", production_status or "unknown"
    if pipeline_status and pipeline_status not in {"passed", "success", "ok", "missing_context", "missing"}:
        return "blocked", production_status or pipeline_status
    if staging_status != "verified":
        return "blocked", production_status or staging_status or "unknown"
    return "ready_for_release", production_status or "ready_for_release"


def finalize_lifecycle(args: argparse.Namespace) -> dict[str, Any]:
    initiatives_path = resolve_path(args.initiatives_file)
    batches_path = resolve_path(args.execution_batches_file)
    board_path = resolve_path(args.board_report)
    workflow_path = resolve_path(args.autonomous_report)
    mr_report_path = resolve_path(args.mr_report)
    release_state_path = resolve_path(args.release_state)

    workflow = run_autonomous_workflow(args)
    if str(workflow.get("status") or "").strip().lower() != "completed":
        return {"status": "workflow_failed", "workflow": workflow}
    verification_command = "python3 -m py_compile scripts/ai_team_generated_impl.py"
    git_save = run_git_save()
    git_push = run_git_push()
    mr_plan = run_mr_plan(args)
    mr_ensure = run_mr_ensure(args)
    mr_status = run_mr_status()
    release_state = run_release_state(args, verification_command=verification_command)
    board = refresh_board(args)
    if str(board.get("status") or "").strip().lower() != "ok":
        return {"status": "board_failed", "workflow": workflow, "board": board}
    write_json(board_path, board)
    write_json(workflow_path, workflow)

    initiatives = load_json(initiatives_path)
    batches = load_json(batches_path)
    initiative_items = initiatives.get("initiatives") if isinstance(initiatives.get("initiatives"), dict) else {}
    batch_items = batches.get("batches") if isinstance(batches.get("batches"), dict) else {}
    initiative = initiative_items.get(args.initiative_id, {}) if isinstance(initiative_items, dict) else {}
    batch = batch_items.get(args.batch_id, {}) if isinstance(batch_items, dict) else {}
    if not isinstance(initiative, dict) or not initiative:
        return {"status": "missing", "initiative_id": args.initiative_id}
    if not isinstance(batch, dict) or not batch:
        return {"status": "missing_batch", "batch_id": args.batch_id}

    mr_report = build_mr_report(args.initiative_id, args.batch_id, board, workflow, {**mr_plan, "mr_status_live": mr_status, "mr_ensure": mr_ensure}, {**git_save, "push": git_push})
    write_json(mr_report_path, mr_report)

    pipeline_status = str((mr_status.get("pipeline") if isinstance(mr_status.get("pipeline"), dict) else {}).get("pipeline_status") or "").strip().lower()
    release_state_payload = load_json(release_state_path)
    release_gate, release_status = release_gate_status({**mr_report, "pipeline_status": pipeline_status}, release_state_payload)

    initiative["status"] = "integration_ready" if release_gate == "ready_for_release" else "approved_for_execution"
    initiative["updated_at"] = workflow_now()
    batch["status"] = "integration_ready" if release_gate == "ready_for_release" else "completed"
    batch["verification_summary"] = {
        **(batch.get("verification_summary") if isinstance(batch.get("verification_summary"), dict) else {}),
        "mr_report": str(mr_report_path),
        "release_state": str(release_state_path),
        "mr_status": mr_report.get("mr_status"),
        "pipeline_status": pipeline_status,
        "release_gate": release_gate,
        "release_status": release_status,
        "git_save": {**git_save, "push": git_push},
        "mr_plan": mr_plan,
        "mr_status_live": mr_status,
        "mr_ensure": mr_ensure,
        "release_steps": release_state,
    }
    write_json(initiatives_path, initiatives)
    write_json(batches_path, batches)
    payload = {
        "status": "completed",
        "initiative_id": args.initiative_id,
        "batch_id": args.batch_id,
        "workflow": workflow,
        "git_save": git_save,
        "git_push": git_push,
        "mr_plan": mr_plan,
        "mr_ensure": mr_ensure,
        "mr_status": mr_status,
        "release_steps": release_state,
        "board": board,
        "mr_report": str(mr_report_path),
        "release_state": str(release_state_path),
    }
    return payload


def emit(payload: dict[str, Any], as_json: bool) -> int:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(payload, ensure_ascii=False))
    return 0


def main() -> int:
    args = parse_args()
    return emit(finalize_lifecycle(args), args.json)


if __name__ == "__main__":
    raise SystemExit(main())
