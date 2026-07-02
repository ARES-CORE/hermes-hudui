import json
import sqlite3
import time
from pathlib import Path

from backend.collectors.model_analytics import collect_model_analytics


def _make_state_db(path: Path, *, include_new_columns: bool = True) -> None:
    new_columns = """
        billing_provider TEXT,
        actual_cost_usd REAL,
        api_call_count INTEGER DEFAULT 0,
    """ if include_new_columns else ""
    conn = sqlite3.connect(path)
    conn.executescript(
        f"""
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
            {new_columns}
            model_config TEXT,
            model TEXT,
            parent_session_id TEXT
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


def test_model_analytics_groups_usage_and_cost_math(tmp_path: Path) -> None:
    hermes_dir = tmp_path / "hermes"
    hermes_dir.mkdir()
    db_path = hermes_dir / "state.db"
    _make_state_db(db_path)
    _insert_session(
        db_path,
        id="s1",
        source="cli",
        started_at=100,
        message_count=2,
        tool_call_count=3,
        input_tokens=100,
        output_tokens=50,
        cache_read_tokens=20,
        cache_write_tokens=10,
        reasoning_tokens=5,
        estimated_cost_usd=0.25,
        actual_cost_usd=0.21,
        billing_provider="anthropic",
        api_call_count=4,
        model="claude-sonnet-4-6",
    )
    _insert_session(
        db_path,
        id="s2",
        source="telegram",
        started_at=200,
        message_count=4,
        tool_call_count=1,
        input_tokens=200,
        output_tokens=150,
        cache_read_tokens=30,
        cache_write_tokens=20,
        reasoning_tokens=15,
        estimated_cost_usd=0.75,
        actual_cost_usd=0.69,
        billing_provider="anthropic",
        api_call_count=2,
        model="claude-sonnet-4-6",
    )
    _insert_session(
        db_path,
        id="tool",
        source="tool",
        started_at=250,
        message_count=9,
        input_tokens=999,
        output_tokens=999,
        estimated_cost_usd=9,
        actual_cost_usd=9,
        billing_provider="anthropic",
        api_call_count=9,
        model="claude-sonnet-4-6",
    )
    _insert_session(
        db_path,
        id="s3",
        source="cli",
        started_at=300,
        message_count=1,
        tool_call_count=0,
        input_tokens=10,
        output_tokens=20,
        estimated_cost_usd=0.05,
        actual_cost_usd=None,
        billing_provider="openai",
        api_call_count=1,
        model="gpt-5.1",
    )

    state = collect_model_analytics(hermes_dir=str(hermes_dir), days=None)
    by_model = {row.model: row for row in state.models}

    assert state.total_sessions == 3
    assert state.total_tokens == 630
    assert round(state.total_estimated_cost_usd, 4) == 1.05
    assert round(state.total_actual_cost_usd, 4) == 0.90
    assert by_model["claude-sonnet-4-6"].sessions == 2
    assert by_model["claude-sonnet-4-6"].provider == "anthropic"
    assert by_model["claude-sonnet-4-6"].input_tokens == 300
    assert by_model["claude-sonnet-4-6"].output_tokens == 200
    assert by_model["claude-sonnet-4-6"].cache_read_tokens == 50
    assert by_model["claude-sonnet-4-6"].cache_write_tokens == 30
    assert by_model["claude-sonnet-4-6"].reasoning_tokens == 20
    assert by_model["claude-sonnet-4-6"].total_tokens == 600
    assert by_model["claude-sonnet-4-6"].api_calls == 6
    assert by_model["claude-sonnet-4-6"].tool_calls == 4
    assert by_model["claude-sonnet-4-6"].avg_tokens_per_session == 300
    assert by_model["claude-sonnet-4-6"].estimated_cost_usd == 1.0
    assert by_model["claude-sonnet-4-6"].actual_cost_usd == 0.90
    assert by_model["gpt-5.1"].actual_cost_usd == 0


def test_model_analytics_filters_period_and_keeps_session_drilldown(tmp_path: Path) -> None:
    hermes_dir = tmp_path / "hermes"
    hermes_dir.mkdir()
    db_path = hermes_dir / "state.db"
    _make_state_db(db_path)
    now = time.time()
    old_started_at = now - 9 * 86400
    recent_started_at = now - 2 * 86400
    newest_started_at = now - 3600
    _insert_session(
        db_path,
        id="old",
        source="cli",
        title="Old run",
        started_at=old_started_at,
        ended_at=old_started_at + 120,
        message_count=1,
        input_tokens=100,
        output_tokens=50,
        estimated_cost_usd=0.10,
        actual_cost_usd=0.08,
        billing_provider="anthropic",
        api_call_count=1,
        model="claude-sonnet-4-6",
    )
    _insert_session(
        db_path,
        id="recent",
        source="cli",
        title="Recent run",
        started_at=recent_started_at,
        ended_at=recent_started_at + 60,
        message_count=2,
        tool_call_count=1,
        input_tokens=200,
        output_tokens=100,
        estimated_cost_usd=0.20,
        actual_cost_usd=0.16,
        billing_provider="anthropic",
        api_call_count=2,
        model="claude-sonnet-4-6",
    )
    _insert_session(
        db_path,
        id="newest",
        source="telegram",
        title="Newest run",
        started_at=newest_started_at,
        ended_at=newest_started_at + 30,
        message_count=3,
        tool_call_count=2,
        input_tokens=300,
        output_tokens=150,
        estimated_cost_usd=0.30,
        actual_cost_usd=0.24,
        billing_provider="anthropic",
        api_call_count=3,
        model="claude-sonnet-4-6",
    )

    state = collect_model_analytics(hermes_dir=str(hermes_dir), days=7)
    usage = state.models[0]

    assert state.period_days == 7
    assert usage.sessions == 2
    assert usage.total_tokens == 750
    assert [session.id for session in usage.session_details] == ["newest", "recent"]
    assert usage.session_details[0].title == "Newest run"
    assert usage.session_details[0].source == "telegram"
    assert usage.session_details[0].messages == 3
    assert usage.session_details[0].api_calls == 3
    assert usage.session_details[0].tool_calls == 2
    assert usage.session_details[0].total_tokens == 450
    assert usage.session_details[0].duration_seconds == 30


def test_model_analytics_enriches_capabilities_from_models_cache(tmp_path: Path) -> None:
    hermes_dir = tmp_path / "hermes"
    hermes_dir.mkdir()
    db_path = hermes_dir / "state.db"
    _make_state_db(db_path)
    _insert_session(
        db_path,
        id="s1",
        source="cli",
        started_at=100,
        input_tokens=10,
        output_tokens=20,
        estimated_cost_usd=0.01,
        billing_provider="openai",
        model="gpt-5.1",
    )
    (hermes_dir / "models_dev_cache.json").write_text(
        json.dumps({
            "openai": {
                "models": {
                    "gpt-5.1": {
                        "tool_call": True,
                        "attachment": True,
                        "reasoning": True,
                        "structured_output": True,
                        "limit": {"context": 400000, "output": 128000},
                    }
                }
            }
        }),
        encoding="utf-8",
    )

    state = collect_model_analytics(hermes_dir=str(hermes_dir), days=None)
    model = state.models[0]

    assert model.supports_tools is True
    assert model.supports_vision is True
    assert model.supports_reasoning is True
    assert model.supports_structured_output is True
    assert model.context_window == 400000
    assert model.max_output_tokens == 128000


def test_model_analytics_handles_old_session_schema(tmp_path: Path) -> None:
    hermes_dir = tmp_path / "hermes"
    hermes_dir.mkdir()
    db_path = hermes_dir / "state.db"
    _make_state_db(db_path, include_new_columns=False)
    _insert_session(
        db_path,
        id="s1",
        source="cli",
        started_at=100,
        input_tokens=10,
        output_tokens=20,
        estimated_cost_usd=0.01,
        model_config=json.dumps({"provider": "openrouter", "model": "legacy-model"}),
        model=None,
    )

    state = collect_model_analytics(hermes_dir=str(hermes_dir), days=None)

    assert state.models[0].model == "legacy-model"
    assert state.models[0].provider == "openrouter"
    assert state.models[0].actual_cost_usd == 0
    assert state.models[0].api_calls == 0
