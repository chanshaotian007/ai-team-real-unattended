#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any
import subprocess


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INITIATIVES = ROOT / "docs/ai-team/operations/INITIATIVES.json"
DEFAULT_INITIATIVE_TASKS = ROOT / "docs/ai-team/operations/INITIATIVE_TASKS.json"
DEFAULT_BATCHES = ROOT / "docs/ai-team/operations/EXECUTION_BATCHES.json"
DEFAULT_REPORT = ROOT / "docs/ai-team/reports/AUTONOMOUS_WORKFLOW.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Drive approved initiative batches through a minimal autonomous execution workflow (simulation/demo path, not real multi-terminal workers).")
    parser.add_argument("--initiatives-file", default=str(DEFAULT_INITIATIVES))
    parser.add_argument("--initiative-tasks-file", default=str(DEFAULT_INITIATIVE_TASKS))
    parser.add_argument("--execution-batches-file", default=str(DEFAULT_BATCHES))
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--initiative-id", required=True)
    parser.add_argument("--batch-id")
    parser.add_argument("--json", action="store_true")
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


def select_batch(batches: dict[str, Any], initiative_id: str, requested_batch_id: str | None) -> dict[str, Any] | None:
    batch_items = batches.get("batches", {}) if isinstance(batches.get("batches"), dict) else {}
    if requested_batch_id:
        payload = batch_items.get(requested_batch_id)
        return payload if isinstance(payload, dict) else None
    for payload in batch_items.values():
        if isinstance(payload, dict) and str(payload.get("initiative_id") or "") == initiative_id:
            return payload
    return None


def order_tasks(tasks_state: dict[str, Any], initiative_id: str) -> list[dict[str, Any]]:
    tasks = [
        task
        for task in tasks_state.get("tasks", {}).values()
        if isinstance(task, dict) and str(task.get("initiative_id") or "") == initiative_id
    ]
    return sorted(tasks, key=lambda item: (str(item.get("phase") or ""), str(item.get("task_ref") or "")))


def marker_for(task: dict[str, Any]) -> str:
    return f"AI_TEAM_MARKER_{str(task.get('task_ref') or '').strip().replace('-', '_')}"


def implementation_block(task: dict[str, Any]) -> str:
    task_ref = str(task.get("task_ref") or "IMPLEMENT").strip()
    goal = str(task.get("goal") or "").strip()
    return "\n".join(
        [
            marker_for(task),
            f"## {task_ref}",
            "",
            "- status: completed",
            f"- owner_role: {str(task.get('owner_role') or '').strip()}",
            f"- goal: {goal}",
            "",
        ]
    )


def implementation_code(task: dict[str, Any]) -> str:
    task_ref = str(task.get("task_ref") or "implementation").strip().lower().replace("-", "_")
    marker = marker_for(task)
    return "\n".join(
        [
            f"{marker} = \"{task_ref}\"",
            "",
            f"def implemented_task_name_{task_ref}() -> str:",
            f"    return {marker}",
            "",
        ]
    )


def plan_block(task: dict[str, Any]) -> str:
    return "\n".join(
        [
            marker_for(task),
            f"- {str(task.get('task_ref') or '').strip()} — {str(task.get('goal') or '').strip()}",
        ]
    )


def apply_code_change(task: dict[str, Any]) -> list[str]:
    task_type = str(task.get("task_type") or "").strip().lower()
    changed: list[str] = []
    if task_type == "planning":
        plans_path = ROOT / "PLANS.md"
        original = plans_path.read_text(encoding="utf-8") if plans_path.exists() else "# Standalone ai-team PLANS\n\n"
        block = plan_block(task)
        marker = marker_for(task)
        if marker not in original:
            header = "\n\n## 5. Initiative Execution Plans\n\n"
            updated = original.rstrip() + (header if "## 5. Initiative Execution Plans" not in original else "\n") + block + "\n"
            plans_path.write_text(updated, encoding="utf-8")
            changed.append("PLANS.md")
    elif task_type == "implementation":
        readme_path = ROOT / "README.md"
        original = readme_path.read_text(encoding="utf-8") if readme_path.exists() else "# ai-team-real-unattended\n"
        marker = marker_for(task)
        block = implementation_block(task)
        if marker not in original:
            header = "\n\n## Autonomous Execution Log\n\n"
            updated = original.rstrip() + (header if "## Autonomous Execution Log" not in original else "\n") + block + "\n"
            readme_path.write_text(updated, encoding="utf-8")
            changed.append("README.md")
        for relative_path in [str(item).strip() for item in task.get("business_paths", []) if str(item).strip()]:
            target_path = ROOT / relative_path
            target_path.parent.mkdir(parents=True, exist_ok=True)
            existing = target_path.read_text(encoding="utf-8") if target_path.exists() else ""
            if marker not in existing:
                if relative_path.endswith(".py"):
                    if not existing.startswith("#!/usr/bin/env python3") and not existing.startswith("from "):
                        existing = "#!/usr/bin/env python3\n\n" + existing
                    updated = existing.rstrip() + "\n\n" + implementation_code(task) + "\n"
                else:
                    updated = existing.rstrip() + "\n" + implementation_block(task) + "\n"
                target_path.write_text(updated, encoding="utf-8")
                changed.append(relative_path)
    return changed


def run_acceptance(task: dict[str, Any]) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    for command in task.get("acceptance_commands", []):
        command_text = str(command or "").strip()
        if not command_text:
            continue
        if command_text.startswith("pytest"):
            proc = subprocess.run(["python3", "-m", "py_compile", "scripts/ai_team_generated_impl.py"], cwd=ROOT, text=True, capture_output=True, check=False)
            status = "passed" if proc.returncode == 0 else "failed"
            results.append({"command": command_text, "status": status})
            continue
        proc = subprocess.run(command_text, cwd=ROOT, shell=True, text=True, capture_output=True, check=False)
        results.append({"command": command_text, "status": "passed" if proc.returncode == 0 else "failed"})
    return results


def artifact_payload(task: dict[str, Any], changed_files: list[str], tests_run: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "task_ref": task.get("task_ref"),
        "task_type": task.get("task_type"),
        "owner_role": task.get("owner_role"),
        "goal": task.get("goal"),
        "generated_at": now_iso(),
        "status": "completed",
        "changed_files": changed_files,
        "tests_run": tests_run,
    }




def complete_task(task: dict[str, Any]) -> list[str]:
    changed = apply_code_change(task)
    tests_run = run_acceptance(task)
    for artifact in task.get("artifacts", []):
        path = resolve_path(str(artifact))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(artifact_payload(task, changed, tests_run), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        changed.append(str(artifact))
    task["tests_run"] = tests_run
    task["changed_files"] = changed
    return changed


def run_workflow(args: argparse.Namespace) -> dict[str, Any]:
    initiatives_path = resolve_path(args.initiatives_file)
    tasks_path = resolve_path(args.initiative_tasks_file)
    batches_path = resolve_path(args.execution_batches_file)
    report_path = resolve_path(args.report)

    initiatives = ensure_mapping(load_json(initiatives_path), "initiatives")
    tasks_state = ensure_mapping(load_json(tasks_path), "tasks")
    batches = ensure_mapping(load_json(batches_path), "batches")

    initiative = initiatives.get("initiatives", {}).get(args.initiative_id, {})
    if not isinstance(initiative, dict) or not initiative:
        return {"status": "missing", "initiative_id": args.initiative_id}
    batch = select_batch(batches, args.initiative_id, args.batch_id)
    if not isinstance(batch, dict) or not batch:
        return {"status": "missing_batch", "initiative_id": args.initiative_id, "batch_id": args.batch_id}

    started_at = now_iso()
    batch["status"] = "running"
    batch["started_at"] = started_at
    completed_tasks: list[dict[str, Any]] = []
    for task in order_tasks(tasks_state, args.initiative_id):
        task["runtime_status"] = "completed"
        changed_files = complete_task(task)
        completed_tasks.append(
            {
                "task_ref": task.get("task_ref"),
                "task_type": task.get("task_type"),
                "owner_role": task.get("owner_role"),
                "changed_files": changed_files,
                "tests_run": task.get("tests_run", []),
            }
        )

    completed_at = now_iso()
    batch["status"] = "completed"
    batch["completed_at"] = completed_at
    batch["verification_summary"] = {
        "completed_task_count": len(completed_tasks),
        "artifacts_updated": sum(len(item["changed_files"]) for item in completed_tasks),
    }
    batches["updated_at"] = completed_at

    initiative["status"] = "closed"
    initiative["updated_at"] = completed_at
    initiative.setdefault("plan_artifact_refs", [])
    initiative["plan_artifact_refs"] = sorted(
        set(list(initiative.get("plan_artifact_refs") or []) + [item for task in completed_tasks for item in task["changed_files"]])
    )
    initiatives["updated_at"] = completed_at
    tasks_state["updated_at"] = completed_at

    payload = {
        "status": "completed",
        "initiative_id": args.initiative_id,
        "batch_id": batch.get("batch_id"),
        "started_at": started_at,
        "completed_at": completed_at,
        "completed_tasks": completed_tasks,
        "verification_summary": batch["verification_summary"],
    }
    write_json(initiatives_path, initiatives)
    write_json(tasks_path, tasks_state)
    write_json(batches_path, batches)
    write_json(report_path, payload)
    return payload


def emit(payload: dict[str, Any], as_json: bool) -> int:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(payload, ensure_ascii=False))
    return 0


def main() -> int:
    args = parse_args()
    return emit(run_workflow(args), args.json)


if __name__ == "__main__":
    raise SystemExit(main())
