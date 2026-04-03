from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AgentSessionStore:
    session_id: str
    user_id: str
    messages: tuple[str, ...]
    tool_results: tuple[dict[str, Any], ...]
    input_tokens: int
    output_tokens: int
    created_at: str
    updated_at: str


DEFAULT_SESSION_DIR = Path(".agent_sessions")


def save_agent_session(session: AgentSessionStore, directory: Path | None = None) -> Path:
    target_dir = directory or DEFAULT_SESSION_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"{session.session_id}.json"
    path.write_text(json.dumps(asdict(session), indent=2))
    return path


def load_agent_session(session_id: str, directory: Path | None = None) -> AgentSessionStore | None:
    target_dir = directory or DEFAULT_SESSION_DIR
    try:
        data = json.loads((target_dir / f"{session_id}.json").read_text())
        return AgentSessionStore(
            session_id=data["session_id"],
            user_id=data["user_id"],
            messages=tuple(data["messages"]),
            tool_results=tuple(data["tool_results"]),
            input_tokens=data.get("input_tokens", 0),
            output_tokens=data.get("output_tokens", 0),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return None


def create_agent_session(session_id: str, user_id: str) -> AgentSessionStore:
    now = datetime.now().isoformat()
    return AgentSessionStore(
        session_id=session_id,
        user_id=user_id,
        messages=(),
        tool_results=(),
        input_tokens=0,
        output_tokens=0,
        created_at=now,
        updated_at=now,
    )


def list_agent_sessions(user_id: str | None = None, directory: Path | None = None) -> list[str]:
    target_dir = directory or DEFAULT_SESSION_DIR
    if not target_dir.exists():
        return []
    sessions = []
    for json_file in target_dir.glob("*.json"):
        try:
            data = json.loads(json_file.read_text())
            if user_id is None or data.get("user_id") == user_id:
                sessions.append(json_file.stem)
        except (json.JSONDecodeError, KeyError):
            continue
    return sorted(sessions)
