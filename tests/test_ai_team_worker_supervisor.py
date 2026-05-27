from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "ai_team_worker_supervisor.py"
SPEC = importlib.util.spec_from_file_location("ai_team_worker_supervisor", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_run_once_claims_dispatch_and_registers_runtime(tmp_path: Path) -> None:
    dispatches = tmp_path / "dispatches.jsonl"
    notifications = tmp_path / "notifications.jsonl"
    state = tmp_path / "state.json"
    broker = tmp_path / "broker.json"
    runtime_state = tmp_path / "runtime.json"
    event_log = tmp_path / "events.jsonl"
    worktree_root = tmp_path / "worktrees"

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
                "dispatch_id": "TASK-1#codex#1",
                "task_id": "TASK-1",
                "owner_role": "backend-agent",
                "summary": "impl",
                "task_ref": "TASK-1",
                "task_contract": {
                    "task_type": "implementation",
                    "approval_gate": {"required": True, "status": "approved"},
                    "runtime": {"execution_backend": "simulation", "heartbeat_interval_seconds": 15, "provider": "simulation"},
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    broker.write_text(
        json.dumps({"work_orders": {"TASK-1": {"status": "dispatched", "approval_gate": {"required": True, "status": "approved"}}}}),
        encoding="utf-8",
    )

    original_root = MODULE.ROOT
    original_run_json_command = MODULE.run_json_command
    MODULE.ROOT = repo
    try:
        def fake_run_json_command(command: list[str]) -> dict[str, object]:
            if command[1].endswith("ai_team_session_manager.py"):
                return {"status": "started", "session_id": "ai-team-session", "transcript_path": str(tmp_path / "transcript.log")}
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
                "transcript_root": str(tmp_path / "transcripts"),
                "artifact_root": str(tmp_path / "artifacts"),
                "role": "backend-agent",
                "once": True,
                "json": True,
            },
        )()

        payload = MODULE.run_once(args)
    finally:
        MODULE.run_json_command = original_run_json_command
        MODULE.ROOT = original_root

    assert payload["status"] == "claimed"
    assert payload["dispatch_id"] == "TASK-1#codex#1"
    saved_runtime = json.loads(runtime_state.read_text(encoding="utf-8"))
    assert saved_runtime["workers"]["TASK-1"]["status"] == "running"
    assert saved_runtime["workers"]["TASK-1"]["session_id"] == "ai-team-session"
    assert event_log.exists()


def test_run_once_blocks_destructive_runtime_intent(tmp_path: Path) -> None:
    dispatches = tmp_path / "dispatches.jsonl"
    notifications = tmp_path / "notifications.jsonl"
    state = tmp_path / "state.json"
    broker = tmp_path / "broker.json"
    runtime_state = tmp_path / "runtime.json"
    event_log = tmp_path / "events.jsonl"
    worktree_root = tmp_path / "worktrees"

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
                "dispatch_id": "TASK-2#codex#1",
                "task_id": "TASK-2",
                "owner_role": "backend-agent",
                "summary": "unsafe",
                "task_ref": "TASK-2",
                "task_contract": {
                    "task_type": "implementation",
                    "approval_gate": {"required": True, "status": "approved"},
                    "acceptance_commands": ["git reset --hard HEAD"],
                    "runtime": {"execution_backend": "simulation", "heartbeat_interval_seconds": 15, "provider": "simulation"},
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    broker.write_text(
        json.dumps({"work_orders": {"TASK-2": {"status": "dispatched", "approval_gate": {"required": True, "status": "approved"}}}}),
        encoding="utf-8",
    )

    original_root = MODULE.ROOT
    MODULE.ROOT = repo
    try:
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
                "transcript_root": str(tmp_path / "transcripts"),
                "artifact_root": str(tmp_path / "artifacts"),
                "role": "backend-agent",
                "once": True,
                "json": True,
            },
        )()
        payload = MODULE.run_once(args)
    finally:
        MODULE.ROOT = original_root

    assert payload["status"] == "blocked"
    assert payload["intent_validation"]["ok"] is False


def test_reconcile_runtime_finalizes_missing_session(tmp_path: Path) -> None:
    runtime_state = tmp_path / "runtime.json"
    event_log = tmp_path / "events.jsonl"
    transcript = tmp_path / "transcript.log"
    transcript.write_text("AI_TEAM_RESULT_BEGIN\n{}\nAI_TEAM_RESULT_END\n", encoding="utf-8")
    MODULE.register_attempt(
        runtime_state,
        dispatch_id="TASK-3#codex#1",
        task_id="TASK-3",
        attempt_id="attempt-003",
        owner_role="backend-agent",
        worktree_path=str(tmp_path),
        backend="simulation",
        status="running",
        heartbeat_at="2026-01-01T00:00:00+00:00",
    )
    MODULE.update_attempt(runtime_state, task_id="TASK-3", status="running", session_id="missing-session", transcript_path=str(transcript))

    original_run_json_command = MODULE.run_json_command
    try:
        def fake_run_json_command(command: list[str]) -> dict[str, object]:
            if command[1].endswith("ai_team_session_manager.py"):
                return {"status": "missing", "session_id": "missing-session"}
            if command[1].endswith("ai_team_codex_dispatch_runner.py"):
                return {"status": "completed"}
            return original_run_json_command(command)

        MODULE.run_json_command = fake_run_json_command
        args = type(
            "Args",
            (),
            {
                "runtime_state": str(runtime_state),
                "event_log": str(event_log),
                "artifact_root": str(tmp_path / "artifacts"),
                "worktree_root": str(tmp_path),
                "dispatches_file": "",
                "notifications_file": "",
                "state_file": "",
                "broker_state": "",
                "role": "backend-agent",
            },
        )()
        payload = MODULE.reconcile_runtime(args)
    finally:
        MODULE.run_json_command = original_run_json_command

    assert payload["status"] == "ok"
    assert payload["finalized"][0]["status"] == "completed"
