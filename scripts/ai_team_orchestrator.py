#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INITIATIVES = ROOT / "docs/ai-team/operations/INITIATIVES.json"
DEFAULT_INITIATIVE_TASKS = ROOT / "docs/ai-team/operations/INITIATIVE_TASKS.json"


ROLE_RULES = [
    {
        "pattern": re.compile(r"frontend|ui|page|dashboard|chart|visual", re.IGNORECASE),
        "owner_role": "frontend-agent",
        "write_scopes": ["frontend/**", "scripts/ai_team_generated_impl.py"],
        "implementation_files": ["frontend/generated_feature.py", "scripts/ai_team_generated_impl.py"],
    },
    {
        "pattern": re.compile(r"qa|test|verification|validate|uat", re.IGNORECASE),
        "owner_role": "qa-agent",
        "write_scopes": ["tests/**", "docs/ai-team/reviews/qa/**"],
        "implementation_files": ["tests/generated_feature_check.py"],
    },
    {
        "pattern": re.compile(r"release|deploy|pipeline|ops|staging|production", re.IGNORECASE),
        "owner_role": "devops-agent",
        "write_scopes": ["scripts/ai_team_git_repo_manager.py", "scripts/ai_team_gitlab_flow.py", "scripts/ai_team_release_controller.py", "docs/ai-team/operations/**"],
        "implementation_files": ["scripts/ai_team_generated_impl.py", "docs/ai-team/operations/generated_release_note.json"],
    },
]


PHASE_TASKS = [
    {"suffix": "ANALYSIS", "task_type": "analysis", "phase": "planning", "owner_role": "orchestrator", "summary": "requirement analysis", "goal_prefix": "将需求整理为结构化分析", "write_scopes": ["docs/ai-team/operations/**"], "artifacts_suffix": "analysis.json"},
    {"suffix": "DESIGN", "task_type": "design", "phase": "planning", "owner_role": "orchestrator", "summary": "system design", "goal_prefix": "整理系统设计与影响范围", "write_scopes": ["docs/ai-team/operations/**"], "artifacts_suffix": "design.json"},
    {"suffix": "PLAN", "task_type": "planning", "phase": "planning", "owner_role": "orchestrator", "summary": "execution planning", "goal_prefix": "生成任务拆解、依赖和执行计划", "write_scopes": ["docs/ai-team/operations/**", "PLANS.md"], "artifacts_suffix": "plan.json"},
    {"suffix": "IMPLEMENT", "task_type": "implementation", "phase": "execution", "summary": "implementation", "goal_prefix": "按计划完成首轮实现", "artifacts_suffix": "implementation.json"},
    {"suffix": "VERIFY", "task_type": "qa", "phase": "verification", "owner_role": "qa-agent", "summary": "verification", "goal_prefix": "验证实现产物、测试和风险说明", "write_scopes": ["tests/**", "docs/ai-team/reviews/qa/**"], "artifacts_suffix": "verification.json"},
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create initiative records and dynamic planning tasks for ai-team.")
    parser.add_argument("--initiatives-file", default=str(DEFAULT_INITIATIVES))
    parser.add_argument("--initiative-tasks-file", default=str(DEFAULT_INITIATIVE_TASKS))
    parser.add_argument("--json", action="store_true")

    subparsers = parser.add_subparsers(dest="command", required=True)

    create_cmd = subparsers.add_parser("create")
    create_cmd.add_argument("--initiative-id")
    create_cmd.add_argument("--title", required=True)
    create_cmd.add_argument("--request-text", required=True)
    create_cmd.add_argument("--requester", default="user")
    create_cmd.add_argument("--priority", default="medium")
    create_cmd.add_argument("--risk-level", default="medium")
    create_cmd.add_argument("--constraint", action="append", default=[])
    create_cmd.add_argument("--acceptance", action="append", default=[])
    create_cmd.add_argument("--json", action="store_true")

    list_cmd = subparsers.add_parser("list")
    list_cmd.add_argument("--json", action="store_true")

    show_cmd = subparsers.add_parser("show")
    show_cmd.add_argument("--initiative-id", required=True)
    show_cmd.add_argument("--json", action="store_true")

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


def slugify(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-").lower()
    return normalized or "initiative"


def next_initiative_id(initiatives: dict[str, Any], title: str) -> str:
    base = slugify(title).upper()[:32]
    existing = initiatives.get("initiatives", {}) if isinstance(initiatives.get("initiatives"), dict) else {}
    count = 1
    while True:
        candidate = f"INIT-{base}-{count:03d}"
        if candidate not in existing:
            return candidate
        count += 1


def choose_role(request_text: str) -> tuple[str, list[str], list[str]]:
    for rule in ROLE_RULES:
        if rule["pattern"].search(request_text):
            return str(rule["owner_role"]), list(rule["write_scopes"]), list(rule.get("implementation_files") or [])
    return "backend-agent", ["scripts/**", "docs/ai-team/operations/**"], ["scripts/ai_team_generated_impl.py"]


def acceptance_commands_for(task_type: str) -> list[str]:
    if task_type in {"analysis", "design", "planning"}:
        return ["python3 scripts/ai_team_plans_status_sync.py --json"]
    if task_type == "qa":
        return ["python3 -m py_compile scripts/ai_team_generated_impl.py"]
    if task_type == "implementation":
        return ["python3 -m py_compile scripts/ai_team_generated_impl.py"]
    return ["python3 scripts/ai_team_codex_dispatch_runner.py status --json"]


def build_tasks(initiative: dict[str, Any]) -> list[dict[str, Any]]:
    initiative_id = str(initiative["initiative_id"])
    request_text = str(initiative["request_text"])
    implementation_owner, implementation_scopes, implementation_files = choose_role(request_text)
    tasks: list[dict[str, Any]] = []
    previous_task_ref: str | None = None
    for item in PHASE_TASKS:
        task_ref = f"{initiative_id}-{item['suffix']}"
        owner_role = str(item.get("owner_role") or implementation_owner)
        write_scopes = list(item.get("write_scopes") or implementation_scopes)
        task = {
            "task_id": task_ref,
            "task_ref": task_ref,
            "initiative_id": initiative_id,
            "parent_task_id": initiative_id,
            "owner_role": owner_role,
            "priority": 100,
            "summary": f"{initiative['title']} {item['summary']}",
            "goal": f"{item['goal_prefix']}：{initiative['title']}",
            "task_type": item["task_type"],
            "phase": item["phase"],
            "business_paths": implementation_files if item["task_type"] == "implementation" else [],
            "approval_gate": {
                "required": item["task_type"] in {"implementation", "qa"},
                "status": "pending" if item["task_type"] in {"implementation", "qa"} else "approved",
                "reason": "await initiative approval before execution" if item["task_type"] in {"implementation", "qa"} else None,
            },
            "execution_mode": "codex_agent",
            "batch_id": None,
            "depends_on_task_refs": [previous_task_ref] if previous_task_ref else [],
            "constraints": list(initiative.get("constraints") or []),
            "read_scopes": ["docs/**", "scripts/**", "AGENTS.md", "PLANS.md"],
            "write_scopes": write_scopes,
            "artifacts": [f"docs/ai-team/operations/{initiative_id.lower()}_{item['artifacts_suffix']}"] ,
            "acceptance_commands": acceptance_commands_for(item["task_type"]),
            "rollback_hint": f"revisit {initiative['title']} {item['summary']} output if evidence becomes stale",
            "risk_notes_required": True,
            "collaborators": ["orchestrator"] if owner_role != "orchestrator" else [],
            "model_hint": None,
            "source_refs": [initiative_id],
            "plan_links": ["PLANS.md"],
            "produces": [item["task_type"]],
            "consumes": [previous_task_ref] if previous_task_ref else [],
        }
        tasks.append(task)
        previous_task_ref = task_ref
    return tasks


def create_initiative(args: argparse.Namespace) -> dict[str, Any]:
    initiatives_path = resolve_path(args.initiatives_file)
    tasks_path = resolve_path(args.initiative_tasks_file)
    initiatives = ensure_mapping(load_json(initiatives_path), "initiatives")
    tasks_state = ensure_mapping(load_json(tasks_path), "tasks")

    initiative_id = str(args.initiative_id or "").strip() or next_initiative_id(initiatives, args.title)
    acceptance = [str(item).strip() for item in args.acceptance if str(item).strip()]
    constraints = [str(item).strip() for item in args.constraint if str(item).strip()]
    created_at = now_iso()
    initiative = {
        "initiative_id": initiative_id,
        "title": str(args.title).strip(),
        "request_text": str(args.request_text).strip(),
        "requester": str(args.requester).strip() or "user",
        "priority": str(args.priority).strip() or "medium",
        "risk_level": str(args.risk_level).strip() or "medium",
        "status": "planned",
        "constraints": constraints,
        "acceptance_criteria": acceptance,
        "analysis_artifact_refs": [],
        "design_artifact_refs": [],
        "plan_artifact_refs": [],
        "approval": {
            "required": True,
            "status": "pending",
            "approved_by": None,
            "approved_at": None,
            "approval_notes": [],
        },
        "execution_batch_ids": [],
        "created_at": created_at,
        "updated_at": created_at,
    }
    initiatives["initiatives"][initiative_id] = initiative
    initiatives["updated_at"] = created_at

    generated_tasks = build_tasks(initiative)
    for task in generated_tasks:
        tasks_state["tasks"][task["task_id"]] = task
    tasks_state["updated_at"] = created_at

    write_json(initiatives_path, initiatives)
    write_json(tasks_path, tasks_state)
    return {
        "status": "created",
        "initiative": initiative,
        "tasks_created": len(generated_tasks),
        "task_refs": [task["task_ref"] for task in generated_tasks],
        "initiatives_file": str(initiatives_path),
        "initiative_tasks_file": str(tasks_path),
    }


def list_initiatives(args: argparse.Namespace) -> dict[str, Any]:
    initiatives = ensure_mapping(load_json(resolve_path(args.initiatives_file)), "initiatives")
    items = list(initiatives["initiatives"].values()) if isinstance(initiatives.get("initiatives"), dict) else []
    return {"status": "ok", "initiative_count": len(items), "initiatives": items}


def show_initiative(args: argparse.Namespace) -> dict[str, Any]:
    initiatives = ensure_mapping(load_json(resolve_path(args.initiatives_file)), "initiatives")
    tasks_state = ensure_mapping(load_json(resolve_path(args.initiative_tasks_file)), "tasks")
    initiative = initiatives["initiatives"].get(args.initiative_id, {}) if isinstance(initiatives.get("initiatives"), dict) else {}
    if not isinstance(initiative, dict) or not initiative:
        return {"status": "missing", "initiative_id": args.initiative_id}
    tasks = [
        task
        for task in tasks_state["tasks"].values()
        if isinstance(task, dict) and str(task.get("initiative_id") or "") == args.initiative_id
    ]
    return {"status": "ok", "initiative": initiative, "tasks": tasks}


def emit(payload: dict[str, Any], as_json: bool) -> int:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(payload, ensure_ascii=False))
    return 0


def main() -> int:
    args = parse_args()
    if args.command == "create":
        return emit(create_initiative(args), args.json)
    if args.command == "list":
        return emit(list_initiatives(args), args.json)
    if args.command == "show":
        return emit(show_initiative(args), args.json)
    return emit({"status": "unsupported_command"}, args.json)


if __name__ == "__main__":
    raise SystemExit(main())
