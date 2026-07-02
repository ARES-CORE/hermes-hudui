"""Shared utilities for Hermes HUD collectors."""

import os
from datetime import datetime
from typing import Optional

try:
    import yaml as _yaml
except ImportError:
    _yaml = None


def load_yaml(text: str) -> dict:
    """Parse YAML text, falling back to a simple key:value parser."""
    if _yaml:
        try:
            data = _yaml.safe_load(text)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    result: dict = {}
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" in stripped:
            key, _, val = stripped.partition(":")
            val = val.strip()
            if val:
                result[key.strip()] = val
    return result


def default_hermes_dir(hermes_dir: str | None = None) -> str:
    """Return the hermes directory.

    Priority: explicit arg > HERMES_HOME env var > ~/.hermes
    """
    if hermes_dir:
        return hermes_dir
    return os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes"))


def default_projects_dir(projects_dir: str | None = None) -> str:
    """Return the projects directory.

    Priority: explicit arg > HERMES_HUD_PROJECTS_DIR env var > ~/projects
    """
    if projects_dir:
        return projects_dir
    return os.environ.get("HERMES_HUD_PROJECTS_DIR", os.path.expanduser("~/projects"))


def safe_get(row, key, default=None):
    """Safely access a column from a sqlite3.Row or tuple.

    Returns default if the column is missing, access fails, or value is None.
    """
    try:
        val = row[key]
        return val if val is not None else default
    except (IndexError, KeyError):
        return default


def parse_timestamp(value) -> Optional[datetime]:
    """Parse a timestamp (unix seconds, unix milliseconds, or ISO string)
    into a naive local datetime. Returns None on failure."""
    if value is None:
        return None
    try:
        if isinstance(value, (int, float)):
            v = float(value)
            if v > 1e12:  # milliseconds
                v /= 1000.0
            return datetime.fromtimestamp(v)
        if isinstance(value, str):
            try:
                v = float(value)
                if v > 1e12:
                    v /= 1000.0
                return datetime.fromtimestamp(v)
            except ValueError:
                dt = datetime.fromisoformat(value)
                if dt.tzinfo is not None:
                    dt = dt.astimezone().replace(tzinfo=None)
                return dt
    except (ValueError, TypeError, OSError):
        pass
    return None
