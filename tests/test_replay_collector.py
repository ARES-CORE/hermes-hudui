import sqlite3
from pathlib import Path

from backend.collectors.replay import get_replay_detail, list_replay_runs


def _make_state_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE sessions (
            id TEXT PRIMARY KEY,
            source TEXT,
            title TEXT,
            started_at REAL,
            ended_at REAL,
            message_count INTEGER DEFAULT 0,
            tool_call_count INTEGER DEFAULT 0,
            input_tokens INTEGER DEFAULT 0,
            output_tokens INTEGER DEFAULT 0,
            cache_read_tokens INTEGER DEFAULT 0,
            cache_write_tokens INTEGER DEFAULT 0,
            reasoning_tokens INTEGER DEFAULT 0,
            estimated_cost_usd REAL DEFAULT 0,
            model_config TEXT,
            model TEXT,
            parent_session_id TEXT,
            end_reason TEXT
        );
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            role TEXT,
            content TEXT,
            timestamp REAL,
            tool_calls TEXT,
            reasoning TEXT,
            token_count INTEGER DEFAULT 0
        );
        """
    )
    conn.commit()
    conn.close()


def _insert_session(path: Path, **values) -> None:
    defaults = {
        "id": "session-1",
        "source": "cli",
        "title": "Build feature",
        "started_at": 1_700_000_000,
        "ended_at": 1_700_000_120,
        "message_count": 2,
        "tool_call_count": 1,
        "input_tokens": 10,
        "output_tokens": 20,
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
        "reasoning_tokens": 0,
        "estimated_cost_usd": 0.01,
        "model_config": None,
        "model": "claude-sonnet",
        "parent_session_id": None,
        "end_reason": None,
    }
    defaults.update(values)
    columns = ", ".join(defaults)
    placeholders = ", ".join("?" for _ in defaults)
    with sqlite3.connect(path) as conn:
        conn.execute(f"INSERT INTO sessions ({columns}) VALUES ({placeholders})", list(defaults.values()))


def _insert_message(path: Path, **values) -> None:
    defaults = {
        "session_id": "session-1",
        "role": "user",
        "content": "Add Replay",
        "timestamp": 1_700_000_001,
        "tool_calls": None,
        "reasoning": None,
        "token_count": 5,
    }
    defaults.update(values)
    columns = ", ".join(defaults)
    placeholders = ", ".join("?" for _ in defaults)
    with sqlite3.connect(path) as conn:
        conn.execute(f"INSERT INTO messages ({columns}) VALUES ({placeholders})", list(defaults.values()))


def test_list_replay_runs_returns_latest_session_metadata(tmp_path: Path) -> None:
    db = tmp_path / "state.db"
    _make_state_db(db)
    _insert_session(db, id="older", title="Older", started_at=100)
    _insert_session(db, id="newer", title="Newer", started_at=200)

    runs = list_replay_runs(hermes_dir=str(tmp_path))

    assert [run.source_session_id for run in runs] == ["newer", "older"]
    assert runs[0].title == "Newer"
    assert runs[0].primary_model == "claude-sonnet"
    assert runs[0].counts.messages == 2


def test_get_replay_detail_handles_missing_messages(tmp_path: Path) -> None:
    db = tmp_path / "state.db"
    _make_state_db(db)
    _insert_session(db)

    detail = get_replay_detail("session-1", hermes_dir=str(tmp_path))

    assert detail is not None
    assert detail.run.source_session_id == "session-1"
    assert detail.events == []
    assert detail.missing_data == ["No message history found for this session."]


def test_get_replay_detail_returns_none_for_unknown_session(tmp_path: Path) -> None:
    db = tmp_path / "state.db"
    _make_state_db(db)

    assert get_replay_detail("missing", hermes_dir=str(tmp_path)) is None

