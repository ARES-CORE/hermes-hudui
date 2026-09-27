"""Offline mode: block every endpoint that can open connections to external hosts.

Enabled with HERMES_HUD_OFFLINE=1. The HUD itself only reads local files and
localhost; these actions are the ones that reach the network (updates, plugin
installs from remote sources, messaging gateways, LLM providers via chat/cron).
"""

from __future__ import annotations

import os
import re

from starlette.responses import JSONResponse

# (method, path regex) pairs, matched against the full request path.
BLOCKED = [
    ("POST", re.compile(r"^/api/hermes/update$")),
    ("POST", re.compile(r"^/api/gateway/restart$")),
    ("POST", re.compile(r"^/api/plugins/install$")),
    ("POST", re.compile(r"^/api/plugins/[^/]+/update$")),
    ("POST", re.compile(r"^/api/chat/sessions/[^/]+/(send|message)$")),
    ("POST", re.compile(r"^/api/cron$")),
    ("POST", re.compile(r"^/api/cron/[^/]+/run$")),
]


def offline_enabled() -> bool:
    return os.environ.get("HERMES_HUD_OFFLINE", "").strip().lower() in ("1", "true", "yes", "on")


def is_blocked(method: str, path: str) -> bool:
    return any(method == m and rx.match(path) for m, rx in BLOCKED)


class OfflineMiddleware:
    """ASGI middleware returning 403 for egress-capable endpoints when offline."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and offline_enabled() and is_blocked(scope["method"], scope["path"]):
            response = JSONResponse(
                {"detail": "Offline mode: this action would contact external hosts and is disabled "
                           "(HERMES_HUD_OFFLINE=1)."},
                status_code=403,
            )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)
