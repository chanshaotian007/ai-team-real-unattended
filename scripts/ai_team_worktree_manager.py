#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORKTREE_ROOT = ROOT / ".ai-team-worktrees"


SLUG_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage isolated worktrees for ai-team runtime attempts.")
    parser.add_argument("--repo", default=str(ROOT))
    parser.add_argument("--worktree-root", default=str(DEFAULT_WORKTREE_ROOT))
    parser.add_argument("--json", action="store_true")

    subparsers = parser.add_subparsers(dest="command", required=True)

    alloc = subparsers.add_parser("allocate")
    alloc.add_argument("--dispatch-id", required=True)
    alloc.add_argument("--attempt-id", required=True)
    alloc.add_argument("--base-ref", default="HEAD")
    alloc.add_argument("--json", action="store_true")

    cleanup = subparsers.add_parser("cleanup")
    cleanup.add_argument("--path", required=True)
    cleanup.add_argument("--force", action="store_true")
    cleanup.add_argument("--json", action="store_true")
    return parser.parse_args()


def resolve_path(raw: str) -> Path:
    path = Path(raw).expanduser()
    return path if path.is_absolute() else ROOT / path


def slugify(value: str) -> str:
    normalized = SLUG_PATTERN.sub("-", value).strip("-._")
    return normalized or "attempt"


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True, check=check)


def allocate_worktree(repo: Path, worktree_root: Path, dispatch_id: str, attempt_id: str, base_ref: str) -> dict[str, Any]:
    worktree_root.mkdir(parents=True, exist_ok=True)
    branch = slugify(f"{dispatch_id}-{attempt_id}").lower()
    path = worktree_root / branch
    if path.exists():
        return {"status": "existing", "branch": branch, "path": str(path), "base_ref": base_ref}
    git(repo, "worktree", "add", "-b", branch, str(path), base_ref)
    return {"status": "allocated", "branch": branch, "path": str(path), "base_ref": base_ref}


def cleanup_worktree(repo: Path, path: Path, force: bool) -> dict[str, Any]:
    command = ["worktree", "remove"]
    if force:
        command.append("--force")
    command.append(str(path))
    git(repo, *command)
    return {"status": "removed", "path": str(path), "forced": force}


def reconcile_worktrees(worktree_root: Path) -> dict[str, Any]:
    items = []
    if worktree_root.exists():
        items = [str(path) for path in worktree_root.iterdir() if path.is_dir()]
    return {"status": "ok", "worktrees": items}


def emit(payload: dict[str, Any], as_json: bool) -> int:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(payload, ensure_ascii=False))
    return 0


def main() -> int:
    args = parse_args()
    repo = resolve_path(args.repo)
    worktree_root = resolve_path(args.worktree_root)
    if args.command == "allocate":
        return emit(allocate_worktree(repo, worktree_root, args.dispatch_id, args.attempt_id, args.base_ref), args.json)
    if args.command == "cleanup":
        return emit(cleanup_worktree(repo, resolve_path(args.path), bool(args.force)), args.json)
    return emit({"status": "unsupported_command"}, args.json)


if __name__ == "__main__":
    raise SystemExit(main())
