#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import urllib.parse
from pathlib import Path
from typing import Any, Optional


DEFAULT_USER_NAME = "ai-team-bot"
DEFAULT_USER_EMAIL = "ai-team@example.invalid"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage git save/push flow for an unattended ai-team repository.")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--json", action="store_true")

    subparsers = parser.add_subparsers(dest="command", required=True)

    init_cmd = subparsers.add_parser("init")
    init_cmd.add_argument("--branch", default="main")
    init_cmd.add_argument("--remote")
    init_cmd.add_argument("--user-name", default=DEFAULT_USER_NAME)
    init_cmd.add_argument("--user-email", default=DEFAULT_USER_EMAIL)
    init_cmd.add_argument("--json", action="store_true")

    status_cmd = subparsers.add_parser("status")
    status_cmd.add_argument("--remote", default="origin")
    status_cmd.add_argument("--json", action="store_true")

    save_cmd = subparsers.add_parser("save")
    save_cmd.add_argument("--message", default="chore: unattended ai-team savepoint")
    save_cmd.add_argument("--all", action="store_true")
    save_cmd.add_argument("--path", action="append", default=[])
    save_cmd.add_argument("--user-name", default=DEFAULT_USER_NAME)
    save_cmd.add_argument("--user-email", default=DEFAULT_USER_EMAIL)
    save_cmd.add_argument("--json", action="store_true")

    push_cmd = subparsers.add_parser("push")
    push_cmd.add_argument("--remote", default="origin")
    push_cmd.add_argument("--branch")
    push_cmd.add_argument("--remote-url")
    push_cmd.add_argument("--http-user")
    push_cmd.add_argument("--http-token")
    push_cmd.add_argument("--json", action="store_true")

    save_push_cmd = subparsers.add_parser("save-and-push")
    save_push_cmd.add_argument("--message", default="chore: unattended ai-team savepoint")
    save_push_cmd.add_argument("--all", action="store_true")
    save_push_cmd.add_argument("--path", action="append", default=[])
    save_push_cmd.add_argument("--remote", default="origin")
    save_push_cmd.add_argument("--branch")
    save_push_cmd.add_argument("--remote-url")
    save_push_cmd.add_argument("--http-user")
    save_push_cmd.add_argument("--http-token")
    save_push_cmd.add_argument("--user-name", default=DEFAULT_USER_NAME)
    save_push_cmd.add_argument("--user-email", default=DEFAULT_USER_EMAIL)
    save_push_cmd.add_argument("--json", action="store_true")

    return parser.parse_args()


def resolve_repo(raw: str) -> Path:
    return Path(raw).expanduser().resolve()


def run_git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        capture_output=True,
        check=check,
    )


def git_output(repo: Path, *args: str) -> str:
    result = run_git(repo, *args, check=False)
    if result.returncode != 0:
        return ""
    return (result.stdout or "").strip()


def repo_exists(repo: Path) -> bool:
    return repo.exists() and repo.is_dir()


def is_git_repo(repo: Path) -> bool:
    if not repo_exists(repo):
        return False
    result = run_git(repo, "rev-parse", "--is-inside-work-tree", check=False)
    return result.returncode == 0 and (result.stdout or "").strip() == "true"


def ensure_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)


def ensure_identity(repo: Path, user_name: str, user_email: str) -> dict[str, str]:
    name = git_output(repo, "config", "user.name")
    email = git_output(repo, "config", "user.email")
    changed: dict[str, str] = {}
    if not name:
        run_git(repo, "config", "user.name", user_name)
        changed["user.name"] = user_name
    if not email:
        run_git(repo, "config", "user.email", user_email)
        changed["user.email"] = user_email
    return changed


def current_branch(repo: Path) -> str:
    return git_output(repo, "branch", "--show-current")


def remote_url(repo: Path, remote: str) -> str:
    return git_output(repo, "remote", "get-url", remote)


def authenticated_remote_url(raw_remote_url: str, http_user: Optional[str], http_token: Optional[str]) -> str:
    remote_url_value = str(raw_remote_url or "").strip()
    token = str(http_token or "").strip()
    if not remote_url_value or not token:
        return remote_url_value
    parsed = urllib.parse.urlparse(remote_url_value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return remote_url_value
    username = str(http_user or "oauth2").strip() or "oauth2"
    netloc = f"{urllib.parse.quote(username, safe='')}:{urllib.parse.quote(token, safe='')}@{parsed.netloc}"
    return urllib.parse.urlunparse(parsed._replace(netloc=netloc))


def status_lines(repo: Path) -> list[str]:
    output = git_output(repo, "status", "--short")
    return [line for line in output.splitlines() if line.strip()]


def init_repo(repo: Path, branch: str, remote: Optional[str], user_name: str, user_email: str) -> dict[str, Any]:
    ensure_repo(repo)
    created = False
    if not is_git_repo(repo):
        run_git(repo, "init", "--initial-branch", branch)
        created = True
    changed_identity = ensure_identity(repo, user_name, user_email)
    if remote:
        existing_remote = remote_url(repo, "origin")
        if existing_remote and existing_remote != remote:
            run_git(repo, "remote", "set-url", "origin", remote)
        elif not existing_remote:
            run_git(repo, "remote", "add", "origin", remote)
    return {
        "status": "initialized",
        "repo": str(repo),
        "created": created,
        "branch": current_branch(repo) or branch,
        "remote": remote_url(repo, "origin"),
        "identity_updated": changed_identity,
    }


def stage_changes(repo: Path, paths: list[str], stage_all: bool) -> dict[str, Any]:
    normalized = [item for item in paths if item]
    if stage_all or not normalized:
        run_git(repo, "add", "--all")
        return {"mode": "all", "paths": []}
    run_git(repo, "add", "--", *normalized)
    return {"mode": "paths", "paths": normalized}


def has_staged_changes(repo: Path) -> bool:
    result = run_git(repo, "diff", "--cached", "--quiet", check=False)
    return result.returncode == 1


def save_repo(repo: Path, message: str, paths: list[str], stage_all: bool, user_name: str, user_email: str) -> dict[str, Any]:
    if not is_git_repo(repo):
        raise RuntimeError(f"not a git repository: {repo}")
    changed_identity = ensure_identity(repo, user_name, user_email)
    staged = stage_changes(repo, paths, stage_all)
    dirty = status_lines(repo)
    if not has_staged_changes(repo):
        return {
            "status": "noop",
            "repo": str(repo),
            "branch": current_branch(repo),
            "staged": staged,
            "identity_updated": changed_identity,
            "working_tree": dirty,
        }
    run_git(repo, "commit", "-m", message)
    head = git_output(repo, "rev-parse", "HEAD")
    return {
        "status": "saved",
        "repo": str(repo),
        "branch": current_branch(repo),
        "commit": head,
        "staged": staged,
        "identity_updated": changed_identity,
        "working_tree": status_lines(repo),
    }


def push_repo(
    repo: Path,
    remote: str,
    branch: Optional[str],
    *,
    explicit_remote_url: Optional[str] = None,
    http_user: Optional[str] = None,
    http_token: Optional[str] = None,
) -> dict[str, Any]:
    if not is_git_repo(repo):
        raise RuntimeError(f"not a git repository: {repo}")
    push_branch = branch or current_branch(repo)
    if not push_branch:
        raise RuntimeError("unable to determine branch to push")
    target = str(explicit_remote_url or "").strip() or remote
    target_for_push = authenticated_remote_url(target, http_user, http_token)
    run_git(repo, "push", "-u", target_for_push, push_branch)
    return {
        "status": "pushed",
        "repo": str(repo),
        "branch": push_branch,
        "remote": remote,
        "remote_url": remote_url(repo, remote),
        "push_target": target,
        "head": git_output(repo, "rev-parse", "HEAD"),
    }


def status_repo(repo: Path, remote: str) -> dict[str, Any]:
    return {
        "status": "ok",
        "repo": str(repo),
        "git_repo": is_git_repo(repo),
        "branch": current_branch(repo),
        "remote": remote,
        "remote_url": remote_url(repo, remote),
        "working_tree": status_lines(repo),
    }


def emit(payload: dict[str, Any], as_json: bool) -> int:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(payload, ensure_ascii=False))
    return 0


def main() -> int:
    args = parse_args()
    repo = resolve_repo(args.repo)

    if args.command == "init":
        payload = init_repo(repo, args.branch, args.remote, args.user_name, args.user_email)
    elif args.command == "status":
        payload = status_repo(repo, args.remote)
    elif args.command == "save":
        payload = save_repo(repo, args.message, list(args.path), bool(args.all), args.user_name, args.user_email)
    elif args.command == "push":
        payload = push_repo(
            repo,
            args.remote,
            args.branch,
            explicit_remote_url=args.remote_url,
            http_user=args.http_user,
            http_token=args.http_token,
        )
    elif args.command == "save-and-push":
        save_payload = save_repo(repo, args.message, list(args.path), bool(args.all), args.user_name, args.user_email)
        push_payload = push_repo(
            repo,
            args.remote,
            args.branch,
            explicit_remote_url=args.remote_url,
            http_user=args.http_user,
            http_token=args.http_token,
        )
        payload = {
            "status": "saved-and-pushed",
            "save": save_payload,
            "push": push_payload,
        }
    else:
        raise RuntimeError(f"unsupported command: {args.command}")

    return emit(payload, args.json)


if __name__ == "__main__":
    raise SystemExit(main())
