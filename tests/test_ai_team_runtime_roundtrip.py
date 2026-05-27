from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "ai_team_codex_unattended.py"
SPEC = importlib.util.spec_from_file_location("ai_team_codex_unattended", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_unattended_main_roundtrip_summary(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    original_round = MODULE.unattended_round
    original_status = MODULE.status_dispatches
    try:
        MODULE.unattended_round = lambda args: {"progress": False, "claims": [], "executions": [{"result": "supervised"}], "seed": {"requested": []}, "dispatch_status": {"counts": {"pending": 0, "errored": 0}}}
        MODULE.status_dispatches = lambda args: {"counts": {"pending": 0, "errored": 0}}
        args = type("Args", (), {"max_rounds": 1, "round_sleep_seconds": 0.0, "report": str(report), "json": True})()
        rounds = []
        round_payload = MODULE.unattended_round(args)
        rounds.append(round_payload)
        payload = {"generated_at": MODULE.resolve_now().isoformat(), "rounds": rounds, "final_status": MODULE.status_dispatches(args), "summary": MODULE.summarize(rounds, MODULE.status_dispatches(args))}
        MODULE.write_json(report, payload)
    finally:
        MODULE.unattended_round = original_round
        MODULE.status_dispatches = original_status

    saved = json.loads(report.read_text(encoding="utf-8"))
    assert saved["summary"]["round_count"] == 1
