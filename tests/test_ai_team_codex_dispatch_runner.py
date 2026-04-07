from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "ai_team_codex_dispatch_runner.py"
SPEC = importlib.util.spec_from_file_location("ai_team_codex_dispatch_runner", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_init_creates_zero_state(tmp_path: Path, monkeypatch) -> None:
    dispatches = tmp_path / "dispatches.jsonl"
    state = tmp_path / "state.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ai_team_codex_dispatch_runner.py",
            "--dispatches-file",
            str(dispatches),
            "--state-file",
            str(state),
            "init",
            "--json",
        ],
    )

    payload = MODULE.init_runtime(MODULE.parse_args())

    assert payload["status"] == "initialized"
    assert dispatches.exists()
    assert state.exists()
    assert json.loads(state.read_text(encoding="utf-8")) == {"dispatches": {}, "claims": {}}
