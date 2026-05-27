from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "ai_team_runtime_policy.py"
SPEC = importlib.util.spec_from_file_location("ai_team_runtime_policy", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_validate_changed_files_detects_scope_violations() -> None:
    payload = MODULE.validate_changed_files([" M scripts/example.py", " M docs/out.md"], ["scripts/**"])
    assert payload["ok"] is False
    assert payload["changed_files"] == ["scripts/example.py", "docs/out.md"]
    assert payload["violations"] == ["docs/out.md"]


def test_validate_commands_detects_destructive_git() -> None:
    payload = MODULE.validate_commands(["git add scripts/example.py", "git reset --hard HEAD"])
    assert payload["ok"] is False
    assert payload["violations"][0]["category"] == "destructive"
