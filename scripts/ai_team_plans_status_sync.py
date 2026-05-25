#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PLANS = ROOT / "PLANS.md"
DEFAULT_MAPPING = ROOT / "docs/ai-team/operations/PLANS_CLOSURE_MAP.yaml"
DEFAULT_BROKER = ROOT / "docs/ai-team/operations/M1_M2_72H_AGENT_BROKER.json"
DEFAULT_INITIATIVES = ROOT / "docs/ai-team/operations/INITIATIVES.json"
DEFAULT_APPROVALS = ROOT / "docs/ai-team/operations/APPROVALS.json"
DEFAULT_EXECUTION_BATCHES = ROOT / "docs/ai-team/operations/EXECUTION_BATCHES.json"
COMPLETED_WORK_ORDER_STATUSES = {"completed", "accepted", "closed"}
STATUS_PRIORITY = {
    "completed": 50,
    "accepted": 50,
    "closed": 50,
    "running": 40,
    "claimed": 40,
    "dispatched": 35,
    "queued": 30,
    "pending": 20,
    "reopened": 20,
    "errored": 10,
    "failed": 10,
    "blocked": 10,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync PLANS.md status rows from completed Codex pilot tasks and concrete repo evidence.")
    parser.add_argument("--plans", default=str(DEFAULT_PLANS))
    parser.add_argument("--mapping", default=str(DEFAULT_MAPPING))
    parser.add_argument("--broker-state", default=str(DEFAULT_BROKER))
    parser.add_argument("--initiatives-file", default=str(DEFAULT_INITIATIVES))
    parser.add_argument("--approvals-file", default=str(DEFAULT_APPROVALS))
    parser.add_argument("--execution-batches-file", default=str(DEFAULT_EXECUTION_BATCHES))
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--write-report")
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


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return {}
    return payload if isinstance(payload, dict) else {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def broker_task_statuses(broker: dict[str, Any]) -> dict[str, str]:
    statuses: dict[str, str] = {}
    work_orders = broker.get("work_orders")
    if not isinstance(work_orders, dict):
        return statuses

    def merge(key: str, status: str) -> None:
        current = statuses.get(key, "")
        if STATUS_PRIORITY.get(status, 0) >= STATUS_PRIORITY.get(current, 0):
            statuses[key] = status

    for task_id, payload in work_orders.items():
        if not isinstance(payload, dict):
            continue
        status = str(payload.get("status") or "").strip().lower()
        merge(str(task_id), status)
        task_ref = str(payload.get("task_ref") or "").strip()
        if task_ref:
            merge(task_ref, status)
        source_task_ref = str(payload.get("source_task_ref") or "").strip()
        if source_task_ref:
            merge(source_task_ref, status)
    return statuses


def load_mapping_items(path: Path) -> list[dict[str, Any]]:
    payload = load_yaml(path)
    items = payload.get("items")
    if not isinstance(items, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        normalized.append(
            {
                "plan_ref": str(item.get("plan_ref") or "").strip(),
                "target_status": str(item.get("target_status") or "Verified-Local").strip(),
                "task_refs": [str(raw).strip() for raw in item.get("task_refs", []) if str(raw).strip()],
                "evidence_files": [str(raw).strip() for raw in item.get("evidence_files", []) if str(raw).strip()],
            }
        )
    return [item for item in normalized if item["plan_ref"]]


def extract_plan_rows(text: str) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for line_no, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line.startswith("|") or line.startswith("|---"):
            continue
        cells = [cell.strip() for cell in raw.split("|")[1:-1]]
        if len(cells) < 2:
            continue
        plan_ref = cells[0]
        status = cells[-1]
        rows[plan_ref] = {"line_no": line_no, "cells": cells, "status": status}
    return rows


def item_report(item: dict[str, Any], plan_rows: dict[str, dict[str, Any]], task_statuses: dict[str, str]) -> dict[str, Any]:
    plan_ref = item["plan_ref"]
    row = plan_rows.get(plan_ref, {})
    current_status = str(row.get("status") or "").strip()
    missing_task_refs = [
        task_ref
        for task_ref in item["task_refs"]
        if task_statuses.get(task_ref, "") not in COMPLETED_WORK_ORDER_STATUSES
    ]
    missing_evidence_files = [path for path in item["evidence_files"] if not resolve_path(path).exists()]
    ready = not missing_task_refs and not missing_evidence_files and bool(row)
    return {
        "plan_ref": plan_ref,
        "current_status": current_status,
        "target_status": item["target_status"],
        "task_refs": item["task_refs"],
        "missing_task_refs": missing_task_refs,
        "evidence_files": item["evidence_files"],
        "missing_evidence_files": missing_evidence_files,
        "plan_row_found": bool(row),
        "ready": ready,
    }


def initiative_summary(path: Path, approvals_path: Path, batches_path: Path) -> dict[str, Any]:
    initiatives = load_json(path)
    approvals = load_json(approvals_path)
    batches = load_json(batches_path)
    initiative_items = initiatives.get("initiatives") if isinstance(initiatives.get("initiatives"), dict) else {}
    approval_items = approvals.get("approvals") if isinstance(approvals.get("approvals"), dict) else {}
    batch_items = batches.get("batches") if isinstance(batches.get("batches"), dict) else {}
    status_counts: dict[str, int] = {}
    for payload in initiative_items.values():
        if not isinstance(payload, dict):
            continue
        status = str(payload.get("status") or "unknown").strip().lower() or "unknown"
        status_counts[status] = status_counts.get(status, 0) + 1
    return {
        "initiative_count": len(initiative_items),
        "approval_count": len(approval_items),
        "batch_count": len(batch_items),
        "status_counts": status_counts,
    }


    text = plans_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    updated_refs: list[str] = []
    by_ref = {item["plan_ref"]: item for item in reports if item["ready"]}
    for index, raw in enumerate(lines):
        line = raw.strip()
        if not line.startswith("|") or line.startswith("|---"):
            continue
        cells = [cell.strip() for cell in raw.split("|")[1:-1]]
        if len(cells) < 2:
            continue
        plan_ref = cells[0]
        report = by_ref.get(plan_ref)
        if not report:
            continue
        target_status = report["target_status"]
        if cells[-1] == target_status:
            continue
        cells[-1] = target_status
        lines[index] = "| " + " | ".join(cells) + " |"
        updated_refs.append(plan_ref)
    if updated_refs:
        plans_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return updated_refs


def sync_statuses(args: argparse.Namespace) -> dict[str, Any]:
    plans_path = resolve_path(args.plans)
    mapping_path = resolve_path(args.mapping)
    broker_path = resolve_path(args.broker_state)
    initiatives_path = resolve_path(args.initiatives_file)
    approvals_path = resolve_path(args.approvals_file)
    batches_path = resolve_path(args.execution_batches_file)

    plans_text = plans_path.read_text(encoding="utf-8")
    mapping_items = load_mapping_items(mapping_path)
    broker = load_json(broker_path)
    task_statuses = broker_task_statuses(broker)
    plan_rows = extract_plan_rows(plans_text)
    reports = [item_report(item, plan_rows, task_statuses) for item in mapping_items]
    updated_refs = apply_updates(plans_path, reports) if args.apply else []
    unresolved = [item for item in reports if not item["ready"]]

    payload = {
        "status": "ok",
        "plans_path": str(plans_path),
        "mapping_path": str(mapping_path),
        "broker_state_path": str(broker_path),
        "initiative_summary": initiative_summary(initiatives_path, approvals_path, batches_path),
        "summary": {
            "mapped_count": len(reports),
            "ready_count": sum(1 for item in reports if item["ready"]),
            "updated_count": len(updated_refs),
            "unresolved_count": len(unresolved),
        },
        "updated_plan_refs": updated_refs,
        "unresolved_plan_refs": [item["plan_ref"] for item in unresolved],
        "items": reports,
    }
    if args.write_report:
        write_json(resolve_path(args.write_report), payload)
    return payload


def main() -> int:
    args = parse_args()
    payload = sync_statuses(args)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"mapped={payload['summary']['mapped_count']} updated={payload['summary']['updated_count']} unresolved={payload['summary']['unresolved_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
