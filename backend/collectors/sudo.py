"""Collect sudo command history and configuration."""

from __future__ import annotations

import json
import re
import sqlite3
from collections import Counter, deque
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import SudoCommand, SudoConfig, SudoState, SudoStats
from .utils import default_hermes_dir, load_yaml, safe_get

_SUDO_RE = re.compile(r"(sudo\s+\S+(?:\s+\S+){0,5})")
_PASSWORD_ERR = re.compile(r"sudo:.*terminal.*required|sudo:.*password", re.IGNORECASE)
_APPROVE_RE = re.compile(r"User approved dangerous command via /approve:\s*(sudo\S*(?:\s+\S+)*)")


def _collect_config(hermes_dir: str) -> SudoConfig:
    config_path = Path(hermes_dir) / "config.yaml"
    if not config_path.exists():
        return SudoConfig()

    data = load_yaml(config_path.read_text(encoding="utf-8"))
    approvals = data.get("approvals", {})
    security = data.get("security", {})

    return SudoConfig(
        approval_mode=approvals.get("mode", "manual") if isinstance(approvals, dict) else "manual",
        approval_timeout=approvals.get("timeout", 60) if isinstance(approvals, dict) else 60,
        command_allowlist=data.get("command_allowlist") or [],
        redact_secrets=security.get("redact_secrets", True) if isinstance(security, dict) else True,
        tirith_enabled=security.get("tirith_enabled", True) if isinstance(security, dict) else True,
    )


def _extract_command(text: str) -> Optional[str]:
    m = _SUDO_RE.search(text)
    return m.group(1).strip() if m else None


def _subcommand_type(command: str) -> str:
    parts = command.split()
    idx = 1
    while idx < len(parts) and parts[idx].startswith("-"):
        idx += 1
    return parts[idx] if idx < len(parts) else "unknown"


def _collect_commands(hermes_dir: str) -> list[SudoCommand]:
    db_path = Path(hermes_dir) / "state.db"
    if not db_path.exists():
        return []

    commands: list[SudoCommand] = []
    conn = None
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT m.content, m.timestamp, m.session_id, s.title
            FROM messages m
            JOIN messages_fts ON messages_fts.rowid = m.id
            LEFT JOIN sessions s ON m.session_id = s.id
            WHERE messages_fts MATCH 'sudo'
              AND m.role = 'tool'
            ORDER BY m.timestamp DESC
            LIMIT 200
        """)

        for row in cursor.fetchall():
            content = safe_get(row, "content", "") or ""
            ts_raw = safe_get(row, "timestamp")
            session_id = safe_get(row, "session_id", "") or ""
            session_title = safe_get(row, "title")

            try:
                data = json.loads(content)
            except (json.JSONDecodeError, ValueError):
                continue

            output = data.get("output", "") or ""
            error = data.get("error", "") or ""
            exit_code = data.get("exit_code")

            cmd = _extract_command(f"{output}\n{error}")
            if not cmd:
                continue

            if exit_code == -1 and ("approval" in error.lower() or "approve" in error.lower()):
                outcome = "blocked"
            elif _PASSWORD_ERR.search(output) or _PASSWORD_ERR.search(error):
                outcome = "failed"
            elif exit_code == 0:
                outcome = "success"
            elif exit_code is not None and exit_code != 0:
                outcome = "failed"
            else:
                outcome = "unknown"

            ts = datetime.fromtimestamp(ts_raw) if ts_raw else None
            commands.append(SudoCommand(
                timestamp=ts,
                command=cmd,
                outcome=outcome,
                session_id=session_id,
                session_title=session_title,
            ))
    except Exception:
        pass
    finally:
        if conn:
            conn.close()

    return commands


def _collect_approved_from_log(hermes_dir: str) -> list[SudoCommand]:
    log_path = Path(hermes_dir) / "logs" / "gateway.log"
    if not log_path.exists():
        return []

    commands: list[SudoCommand] = []
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            lines = deque(f, maxlen=500)
        for line in lines:
            m = _APPROVE_RE.search(line)
            if not m:
                continue
            cmd_text = m.group(1)[:200]
            ts = None
            ts_m = re.match(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", line)
            if ts_m:
                try:
                    ts = datetime.strptime(ts_m.group(1), "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    pass
            commands.append(SudoCommand(timestamp=ts, command=cmd_text, outcome="success"))
    except Exception:
        pass

    return commands


def _compute_stats(commands: list[SudoCommand]) -> SudoStats:
    by_type: Counter[str] = Counter()
    by_date: Counter[str] = Counter()
    approved = failed = blocked = 0

    for cmd in commands:
        if cmd.outcome == "success":
            approved += 1
        elif cmd.outcome == "failed":
            failed += 1
        elif cmd.outcome == "blocked":
            blocked += 1
        by_type[_subcommand_type(cmd.command)] += 1
        if cmd.timestamp:
            by_date[cmd.timestamp.strftime("%Y-%m-%d")] += 1

    return SudoStats(
        total_commands=len(commands),
        approved_count=approved,
        failed_count=failed,
        blocked_count=blocked,
        commands_by_type=dict(by_type.most_common(10)),
        daily_counts=[{"date": d, "count": c} for d, c in sorted(by_date.items())],
    )


def collect_sudo(hermes_dir: str | None = None) -> SudoState:
    """Collect sudo configuration, usage statistics, and command history."""
    hermes_dir = default_hermes_dir(hermes_dir)

    sudo_config = _collect_config(hermes_dir)
    db_commands = _collect_commands(hermes_dir)
    log_commands = _collect_approved_from_log(hermes_dir)

    seen: set[tuple] = {(c.timestamp, c.command[:50]) for c in db_commands}
    for lc in log_commands:
        key = (lc.timestamp, lc.command[:50])
        if key not in seen:
            db_commands.append(lc)
            seen.add(key)

    db_commands.sort(key=lambda c: (
        0 if c.timestamp else 1,
        -(c.timestamp.timestamp() if c.timestamp else 0),
    ))

    return SudoState(
        config=sudo_config,
        stats=_compute_stats(db_commands),
        commands=db_commands,
    )
