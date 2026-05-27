from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "ai_team_session_manager.py"
SPEC = importlib.util.spec_from_file_location("ai_team_session_manager", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_reconcile_sessions_reports_missing_when_no_tmux() -> None:
    payload = MODULE.reconcile_sessions(["missing-session"])
    assert payload["status"] == "ok"
    assert payload["sessions"][0]["session_id"] == "missing-session"
