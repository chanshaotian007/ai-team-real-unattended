#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from ai_team_runtime_policy import validate_changed_files


def git_output(repo: Path, *args: str) -> str:
    proc = subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True, check=False)
    return (proc.stdout or "").strip() if proc.returncode == 0 else ""


def parse_result_block(text: str) -> dict[str, Any]:
    raw = str(text or "")
    begin = raw.find("AI_TEAM_RESULT_BEGIN")
    end = raw.find("AI_TEAM_RESULT_END")
    if begin == -1 or end == -1 or end <= begin:
        return {"status": "failed", "summary": "transcript missing structured result", "tests_run": [], "risk_notes": ["transcript missing structured result"]}
    body = raw[begin + len("AI_TEAM_RESULT_BEGIN"):end].strip()
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return {"status": "failed", "summary": "transcript result is invalid json", "tests_run": [], "risk_notes": ["invalid transcript result json"]}
    if not isinstance(payload, dict):
        return {"status": "failed", "summary": "transcript result is not an object", "tests_run": [], "risk_notes": ["invalid transcript result payload"]}
    return {
        "status": str(payload.get("status") or "failed"),
        "summary": str(payload.get("summary") or "parsed transcript result"),
        "tests_run": payload.get("tests_run") if isinstance(payload.get("tests_run"), list) else [],
        "risk_notes": payload.get("risk_notes") if isinstance(payload.get("risk_notes"), list) else [],
        "handover_notes": payload.get("handover_notes") if isinstance(payload.get("handover_notes"), list) else [],
        "changed_files": payload.get("changed_files") if isinstance(payload.get("changed_files"), list) else [],
        "artifacts_produced": payload.get("artifacts_produced") if isinstance(payload.get("artifacts_produced"), list) else [],
    }


def read_transcript_summary(path: str | Path) -> dict[str, Any]:
    transcript_path = Path(path)
    if not transcript_path.exists():
        return {"status": "missing", "summary": "missing transcript", "tests_run": [], "risk_notes": ["missing transcript"]}
    text = transcript_path.read_text(encoding="utf-8")
    return parse_result_block(text)


def collect_result(
    *,
    repo: str | Path,
    dispatch_id: str,
    task_id: str,
    attempt_id: str,
    artifact_dir: str | Path,
    write_scopes: list[str] | None = None,
    tests_run: list[dict[str, Any]] | None = None,
    risk_notes: list[str] | None = None,
    handover_notes: list[str] | None = None,
    summary: str = "worker attempt completed",
    transcript_path: str | Path | None = None,
) -> dict[str, Any]:
    repo_path = Path(repo)
    artifacts_path = Path(artifact_dir)
    changed_files = [line.strip() for line in git_output(repo_path, "status", "--short").splitlines() if line.strip()]
    produced_artifacts = []
    if artifacts_path.exists() and artifacts_path.is_dir():
        produced_artifacts = [str(path.relative_to(repo_path)) for path in artifacts_path.rglob("*") if path.is_file() and path.is_relative_to(repo_path)]
    validation = validate_changed_files(changed_files, write_scopes or []) if write_scopes else {"ok": True, "changed_files": changed_files, "violations": []}
    transcript_summary = read_transcript_summary(transcript_path) if transcript_path else {"status": "completed", "summary": summary, "tests_run": [], "risk_notes": []}
    status = "completed" if validation["ok"] and transcript_summary["status"] == "completed" else "failed_validation"
    combined_risk_notes = list(risk_notes or []) + list(transcript_summary.get("risk_notes") or [])
    if validation["violations"]:
        combined_risk_notes.append(f"write_scope_violations={','.join(validation['violations'])}")
    return {
        "dispatch_id": dispatch_id,
        "task_id": task_id,
        "attempt_id": attempt_id,
        "status": status,
        "summary": str(transcript_summary.get("summary") or summary),
        "changed_files": validation["changed_files"],
        "artifacts_produced": produced_artifacts,
        "tests_run": list(tests_run or []) + list(transcript_summary.get("tests_run") or []),
        "risk_notes": combined_risk_notes,
        "handover_notes": handover_notes or [],
        "validation": validation,
    }


def write_manifest(path: str | Path, payload: dict[str, Any]) -> None:
    manifest_path = Path(path)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
