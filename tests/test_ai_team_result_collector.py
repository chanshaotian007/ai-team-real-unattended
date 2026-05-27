from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "ai_team_result_collector.py"
SPEC = importlib.util.spec_from_file_location("ai_team_result_collector", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_collect_result_and_write_manifest(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "--initial-branch", "main", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "tester"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "tester@example.invalid"], check=True)
    (repo / "README.md").write_text("# demo\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "README.md"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "init"], check=True)
    (repo / "README.md").write_text("# demo changed\n", encoding="utf-8")
    artifact_dir = repo / "artifacts"
    artifact_dir.mkdir()
    (artifact_dir / "result.txt").write_text("ok\n", encoding="utf-8")
    transcript = repo / "transcript.log"
    transcript.write_text("AI_TEAM_RESULT_BEGIN\n{\"status\": \"completed\", \"summary\": \"done\", \"tests_run\": []}\nAI_TEAM_RESULT_END\n", encoding="utf-8")

    payload = MODULE.collect_result(
        repo=repo,
        dispatch_id="TASK-1#codex#1",
        task_id="TASK-1",
        attempt_id="attempt-001",
        artifact_dir=artifact_dir,
        write_scopes=["README.md"],
        tests_run=[{"command": "python3 -V", "status": "passed"}],
        transcript_path=transcript,
    )
    assert payload["dispatch_id"] == "TASK-1#codex#1"
    assert payload["status"] == "failed_validation"
    assert "artifacts/result.txt" in payload["validation"]["violations"]
    assert payload["summary"] == "done"
    assert payload["tests_run"][0]["status"] == "passed"

    manifest = tmp_path / "manifest.json"
    MODULE.write_manifest(manifest, payload)
    saved = json.loads(manifest.read_text(encoding="utf-8"))
    assert saved["task_id"] == "TASK-1"


def test_read_transcript_summary_detects_missing_result(tmp_path: Path) -> None:
    transcript = tmp_path / "transcript.log"
    transcript.write_text("plain output\n", encoding="utf-8")
    payload = MODULE.read_transcript_summary(transcript)
    assert payload["status"] == "failed"


def test_parse_result_block_handles_invalid_json() -> None:
    payload = MODULE.parse_result_block("AI_TEAM_RESULT_BEGIN\n{bad json}\nAI_TEAM_RESULT_END")
    assert payload["status"] == "failed"


def test_parse_result_block_reads_handover_notes() -> None:
    payload = MODULE.parse_result_block(
        'AI_TEAM_RESULT_BEGIN\n{"status":"completed","summary":"done","handover_notes":["qa next"],"tests_run":[]}\nAI_TEAM_RESULT_END'
    )
    assert payload["handover_notes"][0] == "qa next"
