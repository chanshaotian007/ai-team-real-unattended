from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "ai_team_session_manager.py"
SPEC = importlib.util.spec_from_file_location("ai_team_session_manager", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_start_capture_status_and_stop_session(tmp_path: Path) -> None:
    tmux = subprocess.run(["bash", "-lc", "command -v tmux >/dev/null"], check=False)
    if tmux.returncode != 0:
        return

    transcript_root = tmp_path / "transcripts"
    workdir = tmp_path / "workdir"
    workdir.mkdir()
    session_id = "ai-team-test-session"

    try:
        start = MODULE.start_session(session_id, workdir, "printf 'hello-session\\n'", transcript_root)
        assert start["status"] in {"started", "existing"}
        status = MODULE.session_status(session_id)
        assert status["status"] == "running"
        capture = MODULE.capture_session(session_id)
        assert capture["status"] == "ok"
    finally:
        MODULE.stop_session(session_id)

    stopped = MODULE.session_status(session_id)
    assert stopped["status"] == "missing"
