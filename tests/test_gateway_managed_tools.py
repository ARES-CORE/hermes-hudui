from pathlib import Path

from backend.collectors.gateway import collect_managed_tools


def test_collect_managed_tools_reports_gateway_route_when_opted_in_and_nous_auth_present(
    tmp_path: Path,
) -> None:
    hermes_dir = tmp_path / "hermes"
    hermes_dir.mkdir()
    (hermes_dir / "config.yaml").write_text(
        """
web:
  use_gateway: true
image_gen:
  use_gateway: true
tts:
  use_gateway: true
browser:
  use_gateway: true
""".strip(),
        encoding="utf-8",
    )
    (hermes_dir / "auth.json").write_text('{"nous": {"access_token": "token"}}', encoding="utf-8")

    state = collect_managed_tools(hermes_dir=str(hermes_dir), env={})
    by_key = {tool.key: tool for tool in state.tools}

    assert state.managed_count == 4
    assert state.direct_count == 0
    assert state.unavailable_count == 0
    assert by_key["web"].route == "managed"
    assert by_key["web"].enabled is True
    assert by_key["web"].available is True
    assert by_key["web"].config_section == "web"
    assert by_key["web"].gateway_enabled is True
    assert by_key["web"].has_direct_credential is False
    assert by_key["web"].missing_config == []
    assert by_key["web"].diagnostics == [
        "Gateway opt-in enabled in web.use_gateway.",
        "Nous Portal auth is present.",
        "No direct credential detected.",
    ]
    assert by_key["web"].safe_actions == ["gateway-restart"]
    assert by_key["image_gen"].gateway_service == "fal-queue"
    assert by_key["tts"].gateway_service == "openai-audio"
    assert by_key["browser"].gateway_service == "browser-use"


def test_collect_managed_tools_reports_direct_credentials_without_gateway_opt_in(
    tmp_path: Path,
) -> None:
    hermes_dir = tmp_path / "hermes"
    hermes_dir.mkdir()
    (hermes_dir / "config.yaml").write_text("web: {}\nimage_gen: {}\ntts: {}\nbrowser: {}\n", encoding="utf-8")

    state = collect_managed_tools(
        hermes_dir=str(hermes_dir),
        env={
            "FIRECRAWL_API_KEY": "fc",
            "FAL_KEY": "fal",
            "OPENAI_API_KEY": "openai",
            "BROWSER_USE_API_KEY": "browser",
        },
    )
    by_key = {tool.key: tool for tool in state.tools}

    assert state.managed_count == 0
    assert state.direct_count == 4
    assert by_key["web"].route == "direct"
    assert by_key["web"].gateway_enabled is False
    assert by_key["web"].has_direct_credential is True
    assert by_key["web"].missing_config == []
    assert by_key["web"].diagnostics == [
        "Gateway opt-in disabled in web.use_gateway.",
        "Direct credential configured: FIRECRAWL_API_KEY.",
    ]
    assert by_key["web"].safe_actions == []
    assert by_key["image_gen"].route == "direct"
    assert by_key["tts"].route == "direct"
    assert by_key["browser"].route == "direct"


def test_collect_managed_tools_explains_unavailable_gateway_requirements(tmp_path: Path) -> None:
    hermes_dir = tmp_path / "hermes"
    hermes_dir.mkdir()
    (hermes_dir / "config.yaml").write_text(
        """
web:
  use_gateway: true
image_gen:
  use_gateway: false
tts: {}
browser:
  use_gateway: true
""".strip(),
        encoding="utf-8",
    )

    state = collect_managed_tools(hermes_dir=str(hermes_dir), env={})
    by_key = {tool.key: tool for tool in state.tools}

    assert state.managed_count == 0
    assert state.direct_count == 0
    assert state.unavailable_count == 4
    assert by_key["web"].route == "unavailable"
    assert "Nous Portal auth" in by_key["web"].reason
    assert by_key["web"].gateway_enabled is True
    assert by_key["web"].has_direct_credential is False
    assert by_key["web"].missing_config == [
        "Nous Portal auth",
        "direct Firecrawl/Exa/Parallel/Tavily key",
    ]
    assert by_key["web"].diagnostics == [
        "Gateway opt-in enabled in web.use_gateway.",
        "Nous Portal auth is missing.",
        "No direct credential detected.",
    ]
    assert by_key["web"].safe_actions == ["gateway-restart"]
    assert by_key["image_gen"].reason == "No gateway opt-in or direct FAL key configured."
    assert by_key["image_gen"].missing_config == [
        "image_gen.use_gateway: true",
        "direct FAL key",
    ]
    assert by_key["tts"].reason == "No gateway opt-in or direct OpenAI audio key configured."
    assert "Nous Portal auth" in by_key["browser"].reason
