from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "ai_team_gitlab_flow.py"
SPEC = importlib.util.spec_from_file_location("ai_team_gitlab_flow", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_plan_mr_payload_uses_provided_target(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    MODULE.run_git(repo, "init", "--initial-branch", "feature")
    (repo / "README.md").write_text("# repo\n", encoding="utf-8")
    MODULE.run_git(repo, "config", "user.name", "tester")
    MODULE.run_git(repo, "config", "user.email", "tester@example.invalid")
    MODULE.run_git(repo, "add", "--all")
    MODULE.run_git(repo, "commit", "-m", "init")

    payload = MODULE.planned_mr_payload(
        repo,
        {"GITLAB_HOST": "192.168.0.186", "GITLAB_PORT": "80", "GITLAB_PROJECT_PATH": "chenjihui/kernel-sense"},
        source_branch=None,
        target_branch="main",
        title=None,
        description=None,
        remove_source_branch=False,
        draft=True,
    )

    assert payload["source_branch"] == "feature"
    assert payload["target_branch"] == "main"
    assert payload["payload"]["title"].startswith("Draft:")
