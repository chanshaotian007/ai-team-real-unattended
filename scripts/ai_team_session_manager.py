#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TRANSCRIPT_ROOT = ROOT / "docs/ai-team/runtime-transcripts"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage tmux-backed ai-team worker sessions.")
    parser.add_argument("--transcript-root", default=str(DEFAULT_TRANSCRIPT_ROOT))
    parser.add_argument("--json", action="store_true")

    subparsers = parser.add_subparsers(dest="command", required=True)

    start_cmd = subparsers.add_parser("start")
    start_cmd.add_argument("--session-id", required=True)
    start_cmd.add_argument("--workdir", required=True)
    start_cmd.add_argument("--command", dest="command_text", required=True)
    start_cmd.add_argument("--json", action="store_true")

    capture_cmd = subparsers.add_parser("capture")
    capture_cmd.add_argument("--session-id", required=True)
    capture_cmd.add_argument("--json", action="store_true")

    status_cmd = subparsers.add_parser("status")
    status_cmd.add_argument("--session-id", required=True)
    status_cmd.add_argument("--json", action="store_true")

    stop_cmd = subparsers.add_parser("stop")
    stop_cmd.add_argument("--session-id", required=True)
    stop_cmd.add_argument("--json", action="store_true")
    return parser.parse_args()


def resolve_path(raw: str) -> Path:
    path = Path(raw).expanduser()
    return path if path.is_absolute() else ROOT / path


def tmux(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["tmux", *args], cwd=ROOT, text=True, capture_output=True, check=check)


def transcript_path(transcript_root: Path, session_id: str) -> Path:
    transcript_root.mkdir(parents=True, exist_ok=True)
    return transcript_root / f"{session_id}.log"


def has_session(session_id: str) -> bool:
    proc = tmux("has-session", "-t", session_id, check=False)
    return proc.returncode == 0


def start_session(session_id: str, workdir: Path, command_text: str, transcript_root: Path) -> dict[str, Any]:
    if has_session(session_id):
        return {"status": "existing", "session_id": session_id, "transcript_path": str(transcript_path(transcript_root, session_id))}
    transcript = transcript_path(transcript_root, session_id)
    tmux("new-session", "-d", "-s", session_id, "-c", str(workdir), command_text)
    tmux("pipe-pane", "-t", session_id, f"cat >> {transcript}")
    return {"status": "started", "session_id": session_id, "workdir": str(workdir), "command": command_text, "transcript_path": str(transcript)}


def capture_session(session_id: str) -> dict[str, Any]:
    proc = tmux("capture-pane", "-t", session_id, "-p", check=False)
    if proc.returncode != 0:
        return {"status": "missing", "session_id": session_id, "output": ""}
    return {"status": "ok", "session_id": session_id, "output": proc.stdout}


def session_status(session_id: str) -> dict[str, Any]:
    return {"status": "running" if has_session(session_id) else "missing", "session_id": session_id}


def stop_session(session_id: str) -> dict[str, Any]:
    proc = tmux("kill-session", "-t", session_id, check=False)
    return {"status": "stopped" if proc.returncode == 0 else "missing", "session_id": session_id}


def reconcile_sessions(session_ids: list[str]) -> dict[str, Any]:
    return {
        "status": "ok",
        "sessions": [session_status(session_id) for session_id in session_ids],
    }


def emit(payload: dict[str, Any], as_json: bool) -> int:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(payload, ensure_ascii=False))
    return 0


def main() -> int:
    args = parse_args()
    transcript_root = resolve_path(args.transcript_root)
    if args.command == "start":
        return emit(start_session(args.session_id, resolve_path(args.workdir), args.command_text, transcript_root), args.json)
    if args.command == "capture":
        return emit(capture_session(args.session_id), args.json)
    if args.command == "status":
        return emit(session_status(args.session_id), args.json)
    if args.command == "stop":
        return emit(stop_session(args.session_id), args.json)
    return emit({"status": "unsupported_command"}, args.json)


if __name__ == "__main__":
    raise SystemExit(main())
