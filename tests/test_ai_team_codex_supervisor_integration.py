from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SUPERVISOR_PATH = ROOT / "scripts" / "ai_team_worker_supervisor.py"
SPEC = importlib.util.spec_from_file_location("ai_team_worker_supervisor", SUPERVISOR_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_supervisor_roundtrip_with_simulation_transcript(tmp_path: Path) -> None:
    dispatches = tmp_path / "dispatches.jsonl"
    notifications = tmp_path / "notifications.jsonl"
    state = tmp_path / "state.json"
    broker = tmp_path / "broker.json"
    runtime_state = tmp_path / "runtime.json"
    event_log = tmp_path / "events.jsonl"
    worktree_root = tmp_path / "worktrees"
    artifact_root = tmp_path / "artifacts"
    transcript_root = tmp_path / "transcripts"

    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "--initial-branch", "main", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "tester"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "tester@example.invalid"], check=True)
    (repo / "README.md").write_text("# demo\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "README.md"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "init"], check=True)

    dispatches.write_text(
        json.dumps(
            {
                "dispatch_id": "TASK-INT#codex#1",
                "task_id": "TASK-INT",
                "owner_role": "backend-agent",
                "summary": "integration",
                "task_ref": "TASK-INT",
                "task_contract": {
                    "task_type": "implementation",
                    "approval_gate": {"required": True, "status": "approved"},
                    "acceptance_commands": ["python3 -c 'print(1)'"],
                    "runtime": {"execution_backend": "simulation", "heartbeat_interval_seconds": 15, "provider": "simulation"},
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    broker.write_text(
        json.dumps({"work_orders": {"TASK-INT": {"status": "dispatched", "approval_gate": {"required": True, "status": "approved"}}}}),
        encoding="utf-8",
    )

    original_root = MODULE.ROOT
    original_run_json_command = MODULE.run_json_command
    MODULE.ROOT = repo
    try:
        def fake_run_json_command(command: list[str]) -> dict[str, object]:
            if command[1].endswith("ai_team_session_manager.py") and "start" in command:
                transcript = transcript_root / "ai-team-session.log"
                transcript.parent.mkdir(parents=True, exist_ok=True)
                transcript.write_text("AI_TEAM_RESULT_BEGIN\n{\"status\": \"completed\", \"summary\": \"integration done\", \"tests_run\": [], \"handover_notes\": [\"qa next\"]}\nAI_TEAM_RESULT_END\n", encoding="utf-8")
                return {"status": "started", "session_id": "ai-team-session", "transcript_path": str(transcript)}
            if command[1].endswith("ai_team_session_manager.py") and "status" in command:
                return {"status": "missing", "session_id": "ai-team-session"}
            if command[1].endswith("ai_team_codex_dispatch_runner.py"):
                return {"status": "completed"}
            return original_run_json_command(command)

        MODULE.run_json_command = fake_run_json_command
        args = type(
            "Args",
            (),
            {
                "dispatches_file": str(dispatches),
                "notifications_file": str(notifications),
                "state_file": str(state),
                "broker_state": str(broker),
                "runtime_state": str(runtime_state),
                "event_log": str(event_log),
                "worktree_root": str(worktree_root),
                "transcript_root": str(transcript_root),
                "artifact_root": str(artifact_root),
                "role": "backend-agent",
                "once": True,
                "json": True,
            },
        )()
        start_payload = MODULE.run_once(args)
        reconcile_payload = MODULE.reconcile_runtime(args)
    finally:
        MODULE.run_json_command = original_run_json_command
        MODULE.ROOT = original_root

    assert start_payload["status"] == "claimed"
    assert reconcile_payload["status"] == "ok"
    assert reconcile_payload["finalized"][0]["status"] == "completed"
    assert reconcile_payload["finalized"][0]["result"]["summary"] == "integration done"
