import asyncio
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from backend.api.token_costs import get_token_costs


def _make_state_db(path: Path, *, include_actual_cost: bool = True) -> None:
    actual_cost = "actual_cost_usd REAL," if include_actual_cost else ""
    conn = sqlite3.connect(path)
    conn.executescript(
        f"""
        CREATE TABLE sessions (
            id TEXT PRIMARY KEY,
            source TEXT,
            title TEXT,
            started_at REAL,
            model TEXT,
            message_count INTEGER DEFAULT 0,
            tool_call_count INTEGER DEFAULT 0,
            input_tokens INTEGER DEFAULT 0,
            output_tokens INTEGER DEFAULT 0,
            cache_read_tokens INTEGER DEFAULT 0,
            cache_write_tokens INTEGER DEFAULT 0,
            reasoning_tokens INTEGER DEFAULT 0,
            {actual_cost}
            estimated_cost_usd REAL DEFAULT 0
        );
        """
    )
    conn.commit()
    conn.close()


def _insert_session(path: Path, **values) -> None:
    columns = ", ".join(values)
    placeholders = ", ".join("?" for _ in values)
    with sqlite3.connect(path) as conn:
        conn.execute(
            f"INSERT INTO sessions ({columns}) VALUES ({placeholders})",
            list(values.values()),
        )


def test_token_costs_reports_actual_deltas_cache_savings_and_top_sessions(
    tmp_path: Path, monkeypatch
) -> None:
    hermes_dir = tmp_path / "hermes"
    hermes_dir.mkdir()
    db_path = hermes_dir / "state.db"
    _make_state_db(db_path)
    now = datetime.now()

    _insert_session(
        db_path,
        id="cheap",
        source="cli",
        title="Small request",
        started_at=(now - timedelta(days=9)).timestamp(),
        model="claude-sonnet-4-6",
        message_count=2,
        tool_call_count=1,
        input_tokens=100_000,
        output_tokens=10_000,
        cache_read_tokens=1_000_000,
        cache_write_tokens=10_000,
        reasoning_tokens=0,
        actual_cost_usd=0.99,
    )
    _insert_session(
        db_path,
        id="expensive",
        source="cli",
        title="Large request",
        started_at=now.timestamp(),
        model="claude-sonnet-4-6",
        message_count=4,
        tool_call_count=3,
        input_tokens=200_000,
        output_tokens=20_000,
        cache_read_tokens=2_000_000,
        cache_write_tokens=20_000,
        reasoning_tokens=10_000,
        actual_cost_usd=1.70,
    )
    _insert_session(
        db_path,
        id="estimated-only",
        source="cli",
        title="Estimated only",
        started_at=(now - timedelta(days=1)).timestamp(),
        model="gpt-4o-mini",
        message_count=1,
        input_tokens=1_000_000,
        output_tokens=100_000,
        actual_cost_usd=None,
    )

    monkeypatch.setenv("HERMES_HOME", str(hermes_dir))

    data = asyncio.run(get_token_costs())

    assert data["all_time"]["session_count"] == 3
    assert data["all_time"]["estimated_cost_usd"] == 2.6
    assert data["all_time"]["actual_cost_usd"] == 2.69
    assert data["all_time"]["billed_cost_usd"] == 2.90
    assert data["all_time"]["actual_estimated_cost_usd"] == 2.39
    assert data["all_time"]["actual_delta_usd"] == 0.3
    assert data["all_time"]["actual_coverage_pct"] == 66.7
    assert data["all_time"]["cache_savings_usd"] == 8.1
    assert data["top_sessions"][0]["id"] == "expensive"
    assert data["top_sessions"][0]["actual_cost_usd"] == 1.70
    assert data["top_sessions"][0]["estimated_cost_usd"] == 1.6
    assert data["top_sessions"][0]["billed_cost_usd"] == 1.70

    model = next(m for m in data["by_model"] if m["model"] == "claude-sonnet-4-6")
    assert model["estimated_cost_usd"] == 2.39
    assert model["actual_cost_usd"] == 2.69
    assert model["actual_delta_usd"] == 0.3
    assert model["cache_savings_usd"] == 8.1

    assert data["trend_summary"]["recent_7d_cost_usd"] == 1.91
    assert data["trend_summary"]["previous_7d_cost_usd"] == 0.99
    assert data["trend_summary"]["delta_usd"] == 0.92


def test_token_costs_handles_old_schema_without_actual_cost(
    tmp_path: Path, monkeypatch
) -> None:
    hermes_dir = tmp_path / "hermes"
    hermes_dir.mkdir()
    db_path = hermes_dir / "state.db"
    _make_state_db(db_path, include_actual_cost=False)
    _insert_session(
        db_path,
        id="legacy",
        source="cli",
        title="Legacy",
        started_at=datetime.now().timestamp(),
        model="gpt-4o-mini",
        input_tokens=1_000_000,
        output_tokens=100_000,
    )
    monkeypatch.setenv("HERMES_HOME", str(hermes_dir))

    data = asyncio.run(get_token_costs())

    assert data["all_time"]["estimated_cost_usd"] == 0.21
    assert data["all_time"]["actual_cost_usd"] == 0
    assert data["all_time"]["billed_cost_usd"] == 0.21
    assert data["all_time"]["actual_coverage_pct"] == 0
