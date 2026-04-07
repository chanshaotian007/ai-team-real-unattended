from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "ai_team_release_controller.py"
SPEC = importlib.util.spec_from_file_location("ai_team_release_controller", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_promote_verify_release_and_rollback(tmp_path: Path) -> None:
    state = tmp_path / "release.json"
    MODULE.init_state(state)
    MODULE.staging_promote(state, "artifact-1", "staging")
    MODULE.verify_environment(state, "staging", "smoke", "passed")
    MODULE.promote_release(state, "artifact-1", "production")
    MODULE.rollback_release(state, "production", "smoke failed")

    saved = json.loads(state.read_text(encoding="utf-8"))
    assert saved["production"]["status"] == "rolled_back"
