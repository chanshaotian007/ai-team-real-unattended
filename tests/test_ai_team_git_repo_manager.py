from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "ai_team_git_repo_manager.py"
SPEC = importlib.util.spec_from_file_location("ai_team_git_repo_manager", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_init_save_and_push(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True)

    init_payload = MODULE.init_repo(repo, "main", str(remote), "ai-team-bot", "ai-team@example.invalid")
    assert init_payload["status"] == "initialized"

    (repo / "README.md").write_text("# standalone\n", encoding="utf-8")
    save_payload = MODULE.save_repo(repo, "chore: bootstrap", [], True, "ai-team-bot", "ai-team@example.invalid")
    assert save_payload["status"] == "saved"

    push_payload = MODULE.push_repo(repo, "origin", "main")
    assert push_payload["status"] == "pushed"
