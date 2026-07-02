"""Collect Hermes plugin and dashboard extension metadata."""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from .models import PluginInfo, PluginsState
from .utils import default_hermes_dir, load_yaml

try:
    import yaml as _yaml
except ImportError:
    _yaml = None

_PLUGIN_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _read_agent_manifest(plugin_dir: Path) -> dict[str, Any]:
    for filename in ("plugin.yaml", "plugin.yml"):
        path = plugin_dir / filename
        if path.exists():
            return load_yaml(path.read_text(encoding="utf-8"))
    path = plugin_dir / "manifest.json"
    if path.exists():
        return _read_json(path)
    return {}


def _runtime_status(manifest: dict[str, Any]) -> str:
    if not manifest:
        return "inactive"
    enabled = manifest.get("enabled")
    if enabled is False:
        return "disabled"
    if enabled is True:
        return "enabled"
    return "inactive"


def _list_tools(manifest: dict[str, Any]) -> list[str]:
    tools = manifest.get("provides_tools") or manifest.get("tools") or []
    if isinstance(tools, list):
        return [str(tool) for tool in tools if tool]
    return []


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    if _yaml:
        text = _yaml.safe_dump(data, sort_keys=False)
    else:
        lines: list[str] = []
        for key, value in data.items():
            if isinstance(value, bool):
                value = "true" if value else "false"
            if isinstance(value, list):
                lines.append(f"{key}:")
                lines.extend(f"  - {item}" for item in value)
            else:
                lines.append(f"{key}: {value}")
        text = "\n".join(lines) + "\n"
    path.write_text(text, encoding="utf-8")


def _plugin_from_dir(plugin_dir: Path, source: str) -> PluginInfo | None:
    dashboard_manifest = _read_json(plugin_dir / "dashboard" / "manifest.json")
    agent_manifest = _read_agent_manifest(plugin_dir)
    if not dashboard_manifest and not agent_manifest:
        return None

    name = str(
        dashboard_manifest.get("name")
        or agent_manifest.get("name")
        or plugin_dir.name
    )
    label = str(dashboard_manifest.get("label") or agent_manifest.get("label") or name)
    description = str(
        dashboard_manifest.get("description")
        or agent_manifest.get("description")
        or ""
    )
    version = str(dashboard_manifest.get("version") or agent_manifest.get("version") or "")
    raw_tab = dashboard_manifest.get("tab", {}) if isinstance(dashboard_manifest.get("tab"), dict) else {}
    slots = dashboard_manifest.get("slots") or []

    return PluginInfo(
        name=name,
        label=label,
        description=description,
        version=version,
        source=source,
        path=str(plugin_dir),
        runtime_status=_runtime_status(agent_manifest),
        has_dashboard_manifest=bool(dashboard_manifest),
        has_api=bool(dashboard_manifest.get("api")),
        user_hidden=bool(raw_tab.get("hidden")),
        entry=str(dashboard_manifest.get("entry") or ""),
        css=dashboard_manifest.get("css") if isinstance(dashboard_manifest.get("css"), str) else None,
        icon=str(dashboard_manifest.get("icon") or "Puzzle"),
        tab_path=str(raw_tab.get("path") or f"/{name}"),
        tab_position=str(raw_tab.get("position") or "end"),
        slots=[str(slot) for slot in slots if isinstance(slot, str) and slot],
        provides_tools=_list_tools(agent_manifest),
        auth_required=bool(agent_manifest.get("auth_required")),
        auth_command=str(agent_manifest.get("auth_command") or ""),
        can_update_git=source == "user" and (plugin_dir / ".git").exists(),
    )


def _candidate_dirs(
    hermes_dir: str,
    bundled_plugins_dir: str | None,
    project_dir: str | None,
    include_project_plugins: bool,
) -> list[tuple[Path, str]]:
    dirs: list[tuple[Path, str]] = [(Path(hermes_dir) / "plugins", "user")]

    if bundled_plugins_dir:
        bundled_root = Path(bundled_plugins_dir)
        dirs.extend([(bundled_root / "memory", "bundled"), (bundled_root, "bundled")])
    else:
        for parent in Path(__file__).resolve().parents:
            candidate = parent / "plugins"
            if candidate.exists():
                dirs.extend([(candidate / "memory", "bundled"), (candidate, "bundled")])
                break

    if include_project_plugins and project_dir:
        dirs.append((Path(project_dir) / ".hermes" / "plugins", "project"))

    return dirs


def collect_plugins(
    hermes_dir: str | None = None,
    bundled_plugins_dir: str | None = None,
    project_dir: str | None = None,
    include_project_plugins: bool | None = None,
) -> PluginsState:
    """Discover installed plugin metadata.

    User plugins take precedence over bundled/project plugins with the same
    manifest name, matching Hermes' dashboard discovery behavior.
    """
    hermes_dir = default_hermes_dir(hermes_dir)
    if include_project_plugins is None:
        include_project_plugins = bool(os.environ.get("HERMES_ENABLE_PROJECT_PLUGINS"))
    if project_dir is None:
        project_dir = os.getcwd()

    plugins: list[PluginInfo] = []
    seen: set[str] = set()

    for root, source in _candidate_dirs(
        hermes_dir,
        bundled_plugins_dir,
        project_dir,
        include_project_plugins,
    ):
        if not root.is_dir():
            continue
        for child in sorted(root.iterdir()):
            if not child.is_dir():
                continue
            plugin = _plugin_from_dir(child, source)
            if not plugin or plugin.name in seen:
                continue
            seen.add(plugin.name)
            plugins.append(plugin)

    return PluginsState(plugins=plugins)


def _validate_plugin_name(name: str) -> str:
    if not name or not _PLUGIN_NAME_RE.match(name):
        raise ValueError("Invalid plugin name")
    return name


def _find_user_plugin(name: str, hermes_dir: str | None = None) -> Path:
    name = _validate_plugin_name(name)
    plugin_dir = Path(default_hermes_dir(hermes_dir)) / "plugins" / name
    if not plugin_dir.is_dir():
        raise FileNotFoundError(f"User plugin not found: {name}")
    return plugin_dir


def set_plugin_enabled(
    name: str,
    enabled: bool,
    hermes_dir: str | None = None,
) -> dict[str, Any]:
    """Enable or disable a user plugin by updating its manifest."""
    plugin_dir = _find_user_plugin(name, hermes_dir)
    for filename in ("plugin.yaml", "plugin.yml"):
        path = plugin_dir / filename
        if path.exists():
            data = load_yaml(path.read_text(encoding="utf-8"))
            data["enabled"] = bool(enabled)
            _write_yaml(path, data)
            return {"ok": True, "name": name, "enabled": bool(enabled)}

    path = plugin_dir / "manifest.json"
    if path.exists():
        data = _read_json(path)
        data["enabled"] = bool(enabled)
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        return {"ok": True, "name": name, "enabled": bool(enabled)}

    raise FileNotFoundError(f"Plugin manifest not found: {name}")


def set_dashboard_plugin_hidden(
    name: str,
    hidden: bool,
    hermes_dir: str | None = None,
) -> dict[str, Any]:
    """Hide or show a user dashboard plugin tab by updating its manifest."""
    plugin_dir = _find_user_plugin(name, hermes_dir)
    path = plugin_dir / "dashboard" / "manifest.json"
    if not path.exists():
        raise FileNotFoundError(f"Dashboard manifest not found: {name}")
    data = _read_json(path)
    tab = data.get("tab") if isinstance(data.get("tab"), dict) else {}
    tab["hidden"] = bool(hidden)
    data["tab"] = tab
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return {"ok": True, "name": name, "hidden": bool(hidden)}


def _plugin_name_from_identifier(identifier: str) -> str:
    raw = identifier.rstrip("/").rsplit("/", 1)[-1]
    if raw.endswith(".git"):
        raw = raw[:-4]
    return _validate_plugin_name(raw)


def install_plugin(
    identifier: str,
    hermes_dir: str | None = None,
    runner=subprocess.run,
) -> dict[str, Any]:
    """Install a plugin from a git URL/path into ~/.hermes/plugins."""
    identifier = identifier.strip()
    if not identifier:
        raise ValueError("Plugin identifier is required")
    name = _plugin_name_from_identifier(identifier)
    plugins_dir = Path(default_hermes_dir(hermes_dir)) / "plugins"
    plugins_dir.mkdir(parents=True, exist_ok=True)
    destination = plugins_dir / name
    if destination.exists():
        raise FileExistsError(f"Plugin already exists: {name}")

    result = runner(
        ["git", "clone", identifier, str(destination)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout or "git clone failed")
    return {"ok": True, "name": name, "path": str(destination)}


def update_plugin(
    name: str,
    hermes_dir: str | None = None,
    runner=subprocess.run,
) -> dict[str, Any]:
    """Update a user-installed git plugin with fast-forward pull."""
    plugin_dir = _find_user_plugin(name, hermes_dir)
    if not (plugin_dir / ".git").exists():
        raise RuntimeError(f"Plugin is not git-backed: {name}")
    result = runner(
        ["git", "pull", "--ff-only"],
        cwd=str(plugin_dir),
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout or "git pull failed")
    return {"ok": True, "name": name, "path": str(plugin_dir), "output": result.stdout}
