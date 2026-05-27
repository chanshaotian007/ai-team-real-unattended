from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "ai_team_worker_entry.py"
SPEC = importlib.util.spec_from_file_location("ai_team_worker_entry", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_build_entry_payload_writes_summary(tmp_path: Path) -> None:
    task_contract = {
        "task_id": "TASK-1",
        "owner_role": "backend-agent",
        "goal": "implement feature",
        "constraints": ["keep tests green"],
        "read_scopes": ["scripts/**"],
        "write_scopes": ["scripts/**"],
        "artifacts": ["docs/out.json"],
        "acceptance_commands": ["python3 -V"],
        "runtime": {"execution_backend": "tmux", "provider": "claude"},
    }
    artifact_root = tmp_path / "artifacts"
    payload = MODULE.build_entry_payload(task_contract, "TASK-1#codex#1", "attempt-001", artifact_root, provider="claude")
    assert payload["task_id"] == "TASK-1"
    assert payload["provider"] == "claude"
    assert "claude -p" in payload["provider_command"]
    assert "dispatch_id" in payload["orchestration_prompt"]
    assert payload["result_schema"]["status"] == "completed|failed"
    assert "acceptance_commands" in payload["orchestration_prompt"]
    summary_path = artifact_root / "TASK-1#codex#1" / "attempt-001" / "worker-entry.json"
    saved = json.loads(summary_path.read_text(encoding="utf-8"))
    assert saved["goal"] == "implement feature"


def test_simulation_provider_command_emits_result_markers(tmp_path: Path) -> None:
    command = MODULE.provider_command("simulation", tmp_path / "payload.json", None, "prompt")
    assert "AI_TEAM_RESULT_BEGIN" in command
    assert "AI_TEAM_RESULT_END" in command


def test_codex_provider_command_uses_orchestration_prompt(tmp_path: Path) -> None:
    command = MODULE.provider_command("codex", tmp_path / "payload.json", None, '{"goal":"ship"}')
    assert command.startswith("codex exec '")
