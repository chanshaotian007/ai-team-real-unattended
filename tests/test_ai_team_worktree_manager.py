from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "ai_team_worktree_manager.py"
SPEC = importlib.util.spec_from_file_location("ai_team_worktree_manager", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_allocate_and_cleanup_worktree(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "--initial-branch", "main", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "tester"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "tester@example.invalid"], check=True)
    (repo / "README.md").write_text("# demo\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "README.md"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "init"], check=True)

    worktree_root = tmp_path / "worktrees"
    allocated = MODULE.allocate_worktree(repo, worktree_root, "TASK-1#codex#1", "attempt-001", "HEAD")
    assert allocated["status"] == "allocated"
    assert Path(allocated["path"]).exists()

    removed = MODULE.cleanup_worktree(repo, Path(allocated["path"]), True)
    assert removed["status"] == "removed"
