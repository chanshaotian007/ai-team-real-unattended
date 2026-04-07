from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "ai_team_plans_status_sync.py"
SPEC = importlib.util.spec_from_file_location("ai_team_plans_status_sync", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_sync_updates_ready_row(tmp_path: Path) -> None:
    plans = tmp_path / "PLANS.md"
    mapping = tmp_path / "map.yaml"
    broker = tmp_path / "broker.json"
    evidence = tmp_path / "evidence.txt"

    plans.write_text("| 5.1 | dispatch | x | x | x | Pending |\n", encoding="utf-8")
    evidence.write_text("ok\n", encoding="utf-8")
    mapping.write_text(
        f"items:\n"
        f"  - plan_ref: \"5.1\"\n"
        f"    target_status: \"Verified-Local\"\n"
        f"    task_refs: [\"TASK-TEAM-DISPATCH-001\"]\n"
        f"    evidence_files: [\"{evidence}\"]\n",
        encoding="utf-8",
    )
    broker.write_text(
        json.dumps({"work_orders": {"TASK-TEAM-DISPATCH-001": {"status": "completed", "task_ref": "TASK-TEAM-DISPATCH-001"}}}),
        encoding="utf-8",
    )

    payload = MODULE.sync_statuses(
        type(
            "Args",
            (),
            {
                "plans": str(plans),
                "mapping": str(mapping),
                "broker_state": str(broker),
                "apply": True,
                "write_report": None,
                "json": True,
            },
        )()
    )

    assert payload["summary"]["updated_count"] == 1
    assert "Verified-Local" in plans.read_text(encoding="utf-8")
