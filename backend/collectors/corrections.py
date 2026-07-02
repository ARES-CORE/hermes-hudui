"""Collect correction events — times Hermes was wrong and learned from it."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from .utils import default_hermes_dir, safe_get


@dataclass
class Correction:
    timestamp: Optional[datetime]
    source: str  # memory, user, session
    summary: str
    detail: str = ""
    session_title: Optional[str] = None
    severity: str = "minor"  # minor, major, critical


@dataclass
class CorrectionsState:
    corrections: list[Correction] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.corrections)

    def by_source(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for c in self.corrections:
            counts[c.source] = counts.get(c.source, 0) + 1
        return counts

    def by_severity(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for c in self.corrections:
            counts[c.severity] = counts.get(c.severity, 0) + 1
        return counts


# Patterns that indicate corrections in memory
CORRECTION_KEYWORDS = [
    (r"gotcha", "major"),
    (r"don't .+ as a problem", "major"),
    (r"caught me", "critical"),
    (r"verify before", "critical"),
    (r"Read .+ before making", "major"),
    (r"supersedes", "minor"),
    (r"not usable", "minor"),
    (r"doesn't work", "minor"),
    (r"won't help", "minor"),
    (r"not yet confirmed", "minor"),
    (r"was stuck", "minor"),
    (r"may need manual", "minor"),
    (r"blocks patches", "minor"),
]

# Keywords used to find correction-adjacent messages in session transcripts
SESSION_KEYWORDS = [
    "wrong", "incorrect", "verify", "actually",
    "not right", "not correct", "not true", "push back",
]


def _extract_memory_corrections(hermes_dir: str) -> list[Correction]:
    """Extract corrections from memory files."""
    from .memory import collect_memory

    memory_state, user_state = collect_memory(hermes_dir)
    corrections = []

    for state, source in [(memory_state, "memory"), (user_state, "user")]:
        for entry in state.entries:
            if entry.category != "correction":
                continue
            for pattern, severity in CORRECTION_KEYWORDS:
                if re.search(pattern, entry.text, re.IGNORECASE):
                    summary = entry.text[:80]
                    if len(entry.text) > 80:
                        summary += "..."
                    corrections.append(Correction(
                        timestamp=None,
                        source=source,
                        summary=summary,
                        detail=entry.text,
                        severity=severity,
                    ))
                    break

    return corrections


def _extract_session_corrections(hermes_dir: str) -> list[Correction]:
    """Mine session transcripts for correction events."""
    corrections = []
    db_path = Path(hermes_dir) / "state.db"

    if not db_path.exists():
        return corrections

    conn = None
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        conditions = " OR ".join("m.content LIKE ?" for _ in SESSION_KEYWORDS)
        params = [f"%{kw}%" for kw in SESSION_KEYWORDS]
        cursor.execute(f"""
            SELECT m.content, m.timestamp, s.title
            FROM messages m
            JOIN sessions s ON m.session_id = s.id
            WHERE m.role = 'user'
            AND ({conditions})
            ORDER BY m.timestamp DESC
            LIMIT 20
        """, params)

        for row in cursor.fetchall():
            try:
                content = safe_get(row, "content", "") or ""
                if len(content) < 10 or len(content) > 2000:
                    continue

                lower = content.lower()
                matched_kw = next((kw for kw in SESSION_KEYWORDS if kw in lower), None)
                if matched_kw:
                    idx = lower.find(matched_kw)
                    start = max(0, idx - 40)
                    end = min(len(content), idx + len(matched_kw) + 60)
                    context = content[start:end].strip()
                    if start > 0:
                        context = "..." + context
                    if end < len(content):
                        context += "..."
                else:
                    context = content[:100]

                ts_raw = safe_get(row, "timestamp")
                corrections.append(Correction(
                    timestamp=datetime.fromtimestamp(ts_raw) if ts_raw else None,
                    source="session",
                    summary=context,
                    detail=content[:300],
                    session_title=safe_get(row, "title"),
                    severity="minor",
                ))
            except Exception:
                continue
    except Exception:
        pass
    finally:
        if conn:
            conn.close()

    return corrections


def collect_corrections(hermes_dir: str | None = None) -> CorrectionsState:
    """Collect all correction events."""
    hermes_dir = default_hermes_dir(hermes_dir)

    corrections = []
    corrections.extend(_extract_memory_corrections(hermes_dir))
    corrections.extend(_extract_session_corrections(hermes_dir))

    # Sort: timestamped first (newest), then un-timestamped
    corrections.sort(key=lambda c: (
        0 if c.timestamp else 1,
        -(c.timestamp.timestamp() if c.timestamp else 0),
    ))

    return CorrectionsState(corrections=corrections)
