"""Dataclass → dict serialization for Hermes HUD models."""

from __future__ import annotations

import dataclasses
from datetime import datetime
from typing import Any


def to_dict(obj: Any) -> Any:
    """Recursively convert dataclasses to dicts, handling datetime."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        result = {}
        for f in dataclasses.fields(obj):
            value = getattr(obj, f.name)
            result[f.name] = to_dict(value)
        # Include @property values
        for name in dir(type(obj)):
            if isinstance(getattr(type(obj), name, None), property):
                try:
                    result[name] = to_dict(getattr(obj, name))
                except (AttributeError, TypeError, ValueError):
                    pass
        return result
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, list):
        return [to_dict(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items()}
    elif isinstance(obj, tuple):
        return [to_dict(item) for item in obj]
    return obj
