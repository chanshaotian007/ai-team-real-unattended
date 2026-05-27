#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EVENT_LOG = ROOT / "docs/ai-team/operations/AI_TEAM_RUNTIME_EVENTS.jsonl"


def resolve_path(raw: str | Path) -> Path:
    path = raw if isinstance(raw, Path) else Path(raw).expanduser()
    return path if path.is_absolute() else ROOT / path


def append_event(path: str | Path, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    resolved = resolve_path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "emitted_at": datetime.now().astimezone().isoformat(),
        "event_type": event_type,
        "payload": payload,
    }
    with resolved.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
    return event
