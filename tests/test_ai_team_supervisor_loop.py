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


def test_run_acceptance_commands_collects_pass_fail(tmp_path: Path) -> None:
    workdir = tmp_path / "repo"
    workdir.mkdir()
    args = type("Args", (), {})()
    payload = MODULE.run_acceptance_commands(
        args,
        {"acceptance_commands": ["python3 -c 'print(1)'", "python3 -c 'import sys; sys.exit(1)'"]},
        str(workdir),
    )
    assert payload[0]["status"] == "passed"
    assert payload[1]["status"] == "failed"


def test_watch_loop_uses_reconcile(monkeypatch=None) -> None:
    calls = {"count": 0}
    original_reconcile = MODULE.reconcile_runtime
    original_emit = MODULE.emit
    original_sleep = MODULE.time.sleep
    try:
        def fake_reconcile(args):
            calls["count"] += 1
            if calls["count"] > 1:
                raise KeyboardInterrupt()
            return {"status": "ok"}

        MODULE.reconcile_runtime = fake_reconcile
        MODULE.emit = lambda payload, as_json: 0
        MODULE.time.sleep = lambda seconds: None
        args = type("Args", (), {"json": True})()
        try:
            MODULE.watch_loop(args)
        except KeyboardInterrupt:
            pass
    finally:
        MODULE.reconcile_runtime = original_reconcile
        MODULE.emit = original_emit
        MODULE.time.sleep = original_sleep

    assert calls["count"] >= 2
