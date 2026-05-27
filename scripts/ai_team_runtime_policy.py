#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from typing import Any


DANGEROUS_GIT_COMMAND_FRAGMENTS = {
    "git reset --hard",
    "git clean -f",
    "git checkout .",
    "git restore .",
    "git push --force",
    "git branch -D",
}


def normalize_changed_files(changed_files: list[str]) -> list[str]:
    normalized: list[str] = []
    for item in changed_files:
        text = str(item or "").strip()
        if not text:
            continue
        if len(text) > 3 and text[0] != "?" and text[1] != "?" and text[2] == " ":
            text = text[3:].strip()
        normalized.append(text)
    return normalized


def scope_prefix(pattern: str) -> str:
    value = str(pattern or "").strip()
    if not value:
        return ""
    return value.split("**", 1)[0].split("*", 1)[0].rstrip("/")


def path_within_scopes(path: str, write_scopes: list[str]) -> bool:
    candidate = str(path or "").strip().lstrip("./")
    if not candidate:
        return False
    for scope in write_scopes:
        prefix = scope_prefix(scope)
        if not prefix:
            continue
        if candidate == prefix or candidate.startswith(prefix + "/"):
            return True
    return False


def validate_changed_files(changed_files: list[str], write_scopes: list[str]) -> dict[str, Any]:
    normalized = normalize_changed_files(changed_files)
    violations = [path for path in normalized if not path_within_scopes(path, write_scopes)]
    return {
        "ok": not violations,
        "changed_files": normalized,
        "violations": violations,
    }


def classify_command(command: str) -> str:
    text = str(command or "").strip().lower()
    if not text:
        return "read_only"
    if any(fragment in text for fragment in DANGEROUS_GIT_COMMAND_FRAGMENTS):
        return "destructive"
    if text.startswith("git push"):
        return "network"
    if text.startswith("git commit") or text.startswith("git add"):
        return "repo_write"
    if text.startswith("rm ") or " rm " in text:
        return "destructive"
    return "read_only"


def validate_commands(commands: list[str]) -> dict[str, Any]:
    classified = [{"command": str(command), "category": classify_command(str(command))} for command in commands if str(command).strip()]
    violations = [item for item in classified if item["category"] == "destructive"]
    return {"ok": not violations, "commands": classified, "violations": violations}
