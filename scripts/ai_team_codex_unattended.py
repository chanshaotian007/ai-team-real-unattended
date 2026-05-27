#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DISPATCHES = ROOT / "docs/ai-team/operations/M1_M2_72H_CODEX_AGENT_DISPATCHES.jsonl"
DEFAULT_NOTIFICATIONS = ROOT / "docs/ai-team/operations/M1_M2_72H_AGENT_NOTIFICATIONS.jsonl"
DEFAULT_STATE = ROOT / "docs/ai-team/operations/M1_M2_72H_CODEX_AGENT_RUNNER_STATE.json"
DEFAULT_BROKER_STATE = ROOT / "docs/ai-team/operations/M1_M2_72H_AGENT_BROKER.json"
DEFAULT_REPORT = ROOT / "docs/ai-team/reports/CODEX_UNATTENDED_ACCEPTANCE.json"
DEFAULT_INITIATIVE_TASKS = ROOT / "docs/ai-team/operations/INITIATIVE_TASKS.json"

if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from ai_team_worker_supervisor import run_json_command


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Drive Codex pilot tasks unattended in supervisor-backed mode: run workers, observe status, then seed downstream tasks."
    )
    parser.add_argument("--dispatches-file", default=str(DEFAULT_DISPATCHES))
    parser.add_argument("--notifications-file", default=str(DEFAULT_NOTIFICATIONS))
    parser.add_argument("--state-file", default=str(DEFAULT_STATE))
    parser.add_argument("--broker-state", default=str(DEFAULT_BROKER_STATE))
    parser.add_argument("--initiative-tasks-file", default=str(DEFAULT_INITIATIVE_TASKS))
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--max-rounds", type=int, default=10)
    parser.add_argument("--round-sleep-seconds", type=float, default=2.0)
    parser.add_argument("--command-timeout", type=float, default=900.0)
    parser.add_argument("--seed-source", choices=["catalog", "initiative"], default="catalog")
    parser.add_argument("--batch-id")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def resolve_path(raw: str) -> Path:
    path = Path(raw).expanduser()
    return path if path.is_absolute() else ROOT / path


def resolve_now() -> datetime:
    return datetime.now().astimezone()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def supervisor_command(args: argparse.Namespace, role: str) -> list[str]:
    return [
        sys.executable,
        str(ROOT / "scripts/ai_team_worker_supervisor.py"),
        "--dispatches-file",
        str(resolve_path(args.dispatches_file)),
        "--notifications-file",
        str(resolve_path(args.notifications_file)),
        "--state-file",
        str(resolve_path(args.state_file)),
        "--broker-state",
        str(resolve_path(args.broker_state)),
        "--role",
        role,
        "--once",
        "--json",
    ]


def run_supervisor(args: argparse.Namespace, role: str) -> dict[str, Any]:
    return run_json_command(supervisor_command(args, role))


def run_subprocess(command: list[str], *, timeout: float) -> dict[str, Any]:
    proc = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
    )
    stdout_text = (proc.stdout or "").strip()
    stderr_text = (proc.stderr or "").strip()
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
        "stderr_tail": stderr_text.splitlines()[-40:],
        "parsed": parsed,
    }


def run_shell_command(command: str, *, timeout: float) -> dict[str, Any]:
    proc = subprocess.run(
        command,
        cwd=ROOT,
        shell=True,
        executable=os.getenv("SHELL", "/bin/zsh"),
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
    )
    stdout_text = (proc.stdout or "").strip()
    stderr_text = (proc.stderr or "").strip()
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
        "stderr_tail": stderr_text.splitlines()[-40:],
        "parsed": parsed,
    }


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


def pilot_seed_command(*extra: str) -> list[str]:
    return [sys.executable, str(ROOT / "scripts/ai_team_codex_pilot_seed.py"), *extra]


def load_dispatch_catalog(path: Path) -> dict[str, dict[str, Any]]:
    catalog: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return catalog
    for raw in path.read_text(encoding="utf-8").splitlines():
        text = raw.strip()
        if not text:
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        dispatch_id = str(payload.get("dispatch_id") or "").strip()
        if dispatch_id:
            catalog[dispatch_id] = payload
    return catalog


def list_dispatches(args: argparse.Namespace) -> dict[str, Any]:
    return run_subprocess(dispatch_runner_command(args, "list", "--json"), timeout=args.command_timeout).get("parsed") or {}


def status_dispatches(args: argparse.Namespace) -> dict[str, Any]:
    return run_subprocess(dispatch_runner_command(args, "status", "--json"), timeout=args.command_timeout).get("parsed") or {}


def claim_dispatch_id(args: argparse.Namespace, role: str, dispatch_id: str) -> dict[str, Any]:
    return run_subprocess(
        dispatch_runner_command(args, "claim", "--role", role, "--dispatch-id", dispatch_id, "--json"),
        timeout=args.command_timeout,
    ).get("parsed") or {}


def complete_dispatch(
    args: argparse.Namespace,
    dispatch_id: str,
    *,
    message: str,
    changed_files: list[str],
    artifacts: list[str],
    risk_notes: list[str],
    test_results: list[dict[str, str]],
) -> dict[str, Any]:
    command = dispatch_runner_command(args, "complete", "--dispatch-id", dispatch_id, "--message", message)
    for item in changed_files:
        command.extend(["--changed-file", item])
    for item in artifacts:
        command.extend(["--artifact", item])
    for item in risk_notes:
        command.extend(["--risk-note", item])
    for item in test_results:
        command.extend(["--test-result", json.dumps(item, ensure_ascii=False)])
    command.append("--json")
    return run_subprocess(command, timeout=args.command_timeout).get("parsed") or {}


def fail_dispatch(args: argparse.Namespace, dispatch_id: str, *, message: str, risk_notes: list[str]) -> dict[str, Any]:
    command = dispatch_runner_command(args, "fail", "--dispatch-id", dispatch_id, "--message", message)
    for item in risk_notes:
        command.extend(["--risk-note", item])
    command.append("--json")
    return run_subprocess(command, timeout=args.command_timeout).get("parsed") or {}


def list_pilot_tasks(args: argparse.Namespace) -> dict[str, Any]:
    command = pilot_seed_command("list", "--source", str(getattr(args, "seed_source", "catalog") or "catalog"))
    batch_id = str(getattr(args, "batch_id", "") or "").strip()
    if batch_id:
        command.extend(["--batch-id", batch_id])
    command.append("--json")
    return run_subprocess(command, timeout=120.0).get("parsed") or {}


def seed_tasks(args: argparse.Namespace, task_refs: list[str]) -> dict[str, Any]:
    command = pilot_seed_command("seed", "--source", str(getattr(args, "seed_source", "catalog") or "catalog"))
    batch_id = str(getattr(args, "batch_id", "") or "").strip()
    if batch_id:
        command.extend(["--batch-id", batch_id])
    for task_ref in task_refs:
        command.extend(["--task-ref", task_ref])
    command.append("--json")
    return run_subprocess(command, timeout=120.0).get("parsed") or {}


def acceptance_passed(result: dict[str, Any]) -> bool:
    returncode = result.get("returncode", 1)
    try:
        normalized_returncode = int(returncode)
    except (TypeError, ValueError):
        normalized_returncode = 1
    if normalized_returncode != 0:
        return False
    parsed = result.get("parsed")
    if isinstance(parsed, dict):
        overall = parsed.get("overall")
        if isinstance(overall, dict):
            return str(overall.get("status") or "").strip().lower() == "ok"
        status = str(parsed.get("status") or "").strip().lower()
        if status:
            return status in {
                "ok",
                "completed",
                "initialized",
                "claimed",
                "promoted",
                "released",
                "rolled_back",
                "passed",
                "existing",
                "created",
                "open",
            }
    if isinstance(parsed, list):
        return not any(str(item.get("status") or "").strip().lower() == "failed" for item in parsed if isinstance(item, dict))
    return True


def build_markdown_review(
    dispatch: dict[str, Any],
    command_results: list[dict[str, Any]],
    *,
    generated_at: datetime,
) -> str:
    contract = dispatch.get("task_contract", {}) if isinstance(dispatch.get("task_contract"), dict) else {}
    task_ref = str(dispatch.get("task_ref") or dispatch.get("task_id") or "TASK").strip()
    lines = [
        f"# {task_ref}",
        "",
        f"- Generated at: `{generated_at.isoformat()}`",
        "- Mode: `codex-unattended-acceptance`",
        f"- Owner: `{str(dispatch.get('owner_role') or '').strip()}`",
        f"- Summary: {str(dispatch.get('summary') or '').strip()}",
        f"- Goal: {str(contract.get('goal') or '').strip()}",
        "",
        "## Acceptance",
        "",
    ]
    for item in command_results:
        status = "passed" if acceptance_passed(item) else "failed"
        command = str(item.get("command") or "").strip()
        lines.append(f"- `{command}` -> `{status}`")
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- This review note was synthesized by the unattended acceptance entry from current repository and runtime evidence.",
            "- If upstream implementation changes, rerun unattended acceptance before treating this note as current.",
            "",
        ]
    )
    return "\n".join(lines)


def ensure_artifacts(
    dispatch: dict[str, Any],
    command_results: list[dict[str, Any]],
    *,
    generated_at: datetime,
) -> tuple[list[str], list[str]]:
    contract = dispatch.get("task_contract", {}) if isinstance(dispatch.get("task_contract"), dict) else {}
    artifacts = contract.get("artifacts", [])
    if not isinstance(artifacts, list):
        return [], []
    changed_files: list[str] = []
    available_artifacts: list[str] = []
    for raw in artifacts:
        artifact = str(raw or "").strip()
        if not artifact:
            continue
        path = resolve_path(artifact)
        if path.exists():
            available_artifacts.append(artifact)
            continue
        if path.suffix.lower() == ".md":
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(build_markdown_review(dispatch, command_results, generated_at=generated_at), encoding="utf-8")
            changed_files.append(artifact)
            available_artifacts.append(artifact)
    return changed_files, available_artifacts


def risk_notes_for(dispatch: dict[str, Any], *, synthesized_files: list[str]) -> list[str]:
    notes = [
        "accepted by unattended codex entry against current repo/runtime evidence; rerun if upstream scope changes",
    ]
    rollback_hint = str(
        (dispatch.get("task_contract", {}) if isinstance(dispatch.get("task_contract"), dict) else {}).get("rollback_hint") or ""
    ).strip()
    if rollback_hint:
        notes.append(rollback_hint)
    if synthesized_files:
        notes.append("markdown review artifact was synthesized from current evidence rather than interactive reviewer narration")
    return notes


def execute_dispatch(args: argparse.Namespace, dispatch: dict[str, Any]) -> dict[str, Any]:
    role = str(dispatch.get("owner_role") or "").strip()
    payload = run_supervisor(args, role)
    if str(payload.get("status") or "") == "blocked":
        return {
            "dispatch_id": str(dispatch.get("dispatch_id") or "").strip(),
            "task_ref": str(dispatch.get("task_ref") or "").strip(),
            "owner_role": role,
            "result": "blocked",
            "runner_result": payload,
        }
    if str(payload.get("status") or "") != "claimed":
        return {
            "dispatch_id": str(dispatch.get("dispatch_id") or "").strip(),
            "task_ref": str(dispatch.get("task_ref") or "").strip(),
            "owner_role": role,
            "result": "idle",
            "runner_result": payload,
        }
    return {
        "dispatch_id": str(dispatch.get("dispatch_id") or payload.get("dispatch_id") or "").strip(),
        "task_ref": str(dispatch.get("task_ref") or "").strip(),
        "owner_role": role,
        "result": "supervised",
        "runner_result": payload,
    }


def select_ready_unseeded_tasks(payload: dict[str, Any]) -> list[str]:
    tasks = payload.get("tasks", [])
    if not isinstance(tasks, list):
        return []
    selected: list[str] = []
    for item in tasks:
        if not isinstance(item, dict):
            continue
        if str(item.get("broker_status") or "").strip().lower() != "unseeded":
            continue
        readiness = item.get("readiness", {})
        if not isinstance(readiness, dict) or readiness.get("dispatch_ready") is not True:
            continue
        task_ref = str(item.get("task_ref") or "").strip()
        if task_ref:
            selected.append(task_ref)
    return selected


def unattended_round(args: argparse.Namespace) -> dict[str, Any]:
    dispatch_catalog = load_dispatch_catalog(resolve_path(args.dispatches_file))
    listing = list_dispatches(args)
    dispatches = listing.get("dispatches", []) if isinstance(listing.get("dispatches"), list) else []
    pending_dispatches: list[dict[str, str]] = []
    for item in dispatches:
        if not isinstance(item, dict):
            continue
        if str(item.get("status") or "").strip().lower() not in {"pending", "queued"}:
            continue
        role = str(item.get("owner_role") or "").strip()
        dispatch_id = str(item.get("dispatch_id") or "").strip()
        if role and dispatch_id:
            pending_dispatches.append({"owner_role": role, "dispatch_id": dispatch_id})

    claims: list[dict[str, Any]] = []
    executions: list[dict[str, Any]] = []
    progress = False
    for item in pending_dispatches:
        role = item["owner_role"]
        dispatch_id = item["dispatch_id"]
        claim_payload = claim_dispatch_id(args, role, dispatch_id)
        claims.append(claim_payload)
        if str(claim_payload.get("status") or "").strip().lower() != "claimed":
            continue
        progress = True
        dispatch = claim_payload.get("dispatch")
        if not isinstance(dispatch, dict):
            dispatch_id = str(claim_payload.get("dispatch_id") or "").strip()
            dispatch = dispatch_catalog.get(dispatch_id, {})
        if not isinstance(dispatch, dict) or not dispatch:
            executions.append(
                {
                    "dispatch_id": str(claim_payload.get("dispatch_id") or "").strip(),
                    "owner_role": role,
                    "result": "failed",
                    "reason": "missing_dispatch_contract",
                }
            )
            fail_dispatch(
                args,
                str(claim_payload.get("dispatch_id") or "").strip(),
                message=f"unattended execution missing contract for {claim_payload.get('dispatch_id')}",
                risk_notes=["dispatch contract missing in codex dispatch catalog"],
            )
            continue
        executions.append(execute_dispatch(args, dispatch))

    pilot_payload = list_pilot_tasks(args)
    ready_unseeded = select_ready_unseeded_tasks(pilot_payload)
    seed_payload: dict[str, Any] = {"status": "idle", "requested": [], "source": str(getattr(args, "seed_source", "catalog") or "catalog")}
    if ready_unseeded:
        progress = True
        seed_payload = seed_tasks(args, ready_unseeded)
        seed_payload["requested"] = ready_unseeded

    return {
        "progress": progress,
        "claims": claims,
        "executions": executions,
        "seed": seed_payload,
        "dispatch_status": status_dispatches(args),
    }


def summarize(report_rounds: list[dict[str, Any]], final_status: dict[str, Any]) -> dict[str, Any]:
    completed = 0
    failed = 0
    seeded: list[str] = []
    for round_payload in report_rounds:
        for item in round_payload.get("executions", []):
            if str(item.get("result") or "").strip() == "completed":
                completed += 1
            elif str(item.get("result") or "").strip() == "failed":
                failed += 1
        seed_payload = round_payload.get("seed", {})
        if isinstance(seed_payload, dict):
            seeded.extend(str(item).strip() for item in seed_payload.get("requested", []) if str(item).strip())
    counts = final_status.get("counts", {}) if isinstance(final_status.get("counts"), dict) else {}
    pending = int(counts.get("pending", 0) or 0)
    errored = int(counts.get("errored", 0) or 0)
    return {
        "status": "ok" if pending == 0 and errored == 0 and failed == 0 else "conditional",
        "round_count": len(report_rounds),
        "completed_dispatches": completed,
        "failed_dispatches": failed,
        "seeded_task_refs": seeded,
        "pending_dispatches": pending,
        "errored_dispatches": errored,
    }


def emit(payload: dict[str, Any], as_json: bool) -> int:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(payload, ensure_ascii=False))
    return 0


def main() -> int:
    args = parse_args()
    rounds: list[dict[str, Any]] = []
    for _ in range(max(1, int(args.max_rounds or 1))):
        round_payload = unattended_round(args)
        rounds.append(round_payload)
        if not round_payload.get("progress"):
            break
        time.sleep(max(0.0, float(args.round_sleep_seconds or 0.0)))

    final_status = status_dispatches(args)
    payload = {
        "generated_at": resolve_now().isoformat(),
        "rounds": rounds,
        "final_status": final_status,
        "summary": summarize(rounds, final_status),
    }
    write_json(resolve_path(args.report), payload)
    return emit(payload, args.json)


if __name__ == "__main__":
    raise SystemExit(main())
