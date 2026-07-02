"""Collect Replay runs from Hermes session data."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any

from backend.collectors.models import SessionInfo
from backend.collectors.sessions import collect_sessions
from backend.collectors.utils import default_hermes_dir, parse_timestamp, safe_get
from backend.models.replay import ReplayDetail, ReplayRun
from backend.services.replay_normalizer import build_replay_run, normalize_session

logger = logging.getLogger(__name__)


def _db_path(hermes_dir: str | None = None) -> Path:
    return Path(default_hermes_dir(hermes_dir)) / "state.db"


def list_replay_runs(limit: int = 50, hermes_dir: str | None = None) -> list[ReplayRun]:
    state = collect_sessions(hermes_dir)
    return [build_replay_run(session) for session in state.sessions[:limit]]


def _session_by_id(session_id: str, hermes_dir: str | None = None) -> SessionInfo | None:
    state = collect_sessions(hermes_dir)
    return next((session for session in state.sessions if session.id == session_id), None)


def _load_messages(session_id: str, hermes_dir: str | None = None, limit: int = 500) -> list[dict[str, Any]]:
    db = _db_path(hermes_dir)
    if not db.exists():
        return []

    try:
        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT id, role, content, timestamp, tool_calls, reasoning, token_count
            FROM messages
            WHERE session_id = ?
            ORDER BY timestamp ASC
            LIMIT ?
            """,
            (session_id, limit),
        ).fetchall()
        conn.close()
    except sqlite3.OperationalError:
        logger.debug("Replay message load failed; messages table may be missing", exc_info=True)
        return []
    except Exception:
        logger.warning("Replay message load failed", exc_info=True)
        return []

    messages: list[dict[str, Any]] = []
    for row in rows:
        messages.append({
            "id": safe_get(row, "id"),
            "role": safe_get(row, "role", "unknown"),
            "content": safe_get(row, "content", ""),
            "timestamp": safe_get(row, "timestamp"),
            "tool_calls": safe_get(row, "tool_calls"),
            "reasoning": safe_get(row, "reasoning"),
            "token_count": safe_get(row, "token_count", 0),
        })
    return messages


def _fallback_session(session_id: str, hermes_dir: str | None = None) -> SessionInfo | None:
    db = _db_path(hermes_dir)
    if not db.exists():
        return None
    try:
        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT id, source, title, started_at, ended_at, message_count,
                   tool_call_count, input_tokens, output_tokens,
                   cache_read_tokens, cache_write_tokens, reasoning_tokens,
                   estimated_cost_usd, model
            FROM sessions
            WHERE id = ?
            """,
            (session_id,),
        ).fetchone()
        conn.close()
    except Exception:
        logger.debug("Replay fallback session load failed", exc_info=True)
        return None
    if not row:
        return None
    started = parse_timestamp(safe_get(row, "started_at"))
    if started is None:
        return None
    return SessionInfo(
        id=safe_get(row, "id", session_id),
        source=safe_get(row, "source", "unknown"),
        title=safe_get(row, "title"),
        started_at=started,
        ended_at=parse_timestamp(safe_get(row, "ended_at")),
        message_count=safe_get(row, "message_count", 0),
        tool_call_count=safe_get(row, "tool_call_count", 0),
        input_tokens=safe_get(row, "input_tokens", 0),
        output_tokens=safe_get(row, "output_tokens", 0),
        cache_read_tokens=safe_get(row, "cache_read_tokens", 0),
        cache_write_tokens=safe_get(row, "cache_write_tokens", 0),
        reasoning_tokens=safe_get(row, "reasoning_tokens", 0),
        estimated_cost_usd=safe_get(row, "estimated_cost_usd", 0.0),
        model=safe_get(row, "model"),
    )


def get_replay_detail(session_id: str, hermes_dir: str | None = None) -> ReplayDetail | None:
    session = _session_by_id(session_id, hermes_dir) or _fallback_session(session_id, hermes_dir)
    if not session:
        return None
    messages = _load_messages(session_id, hermes_dir)
    return normalize_session(session, messages)

