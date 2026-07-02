from backend.api.dashboard import build_executive_summary
from backend.collectors.health import DiagnosticStatus
from backend.collectors.models import (
    GatewayState,
    ManagedToolsState,
    ManagedToolStatus,
    ModelAnalyticsState,
    ModelUsage,
    ProviderAuth,
    ProvidersState,
)


def test_dashboard_summary_prioritizes_health_cost_model_and_risks() -> None:
    health = type("Health", (), {
        "diagnostics_broken": 2,
        "diagnostics_warnings": 3,
        "features": [
            DiagnosticStatus(name="Chat", status="ok"),
            DiagnosticStatus(name="Gateway", status="broken", detail="gateway down"),
        ],
        "readiness": [DiagnosticStatus(name="Config", status="warning", detail="missing key")],
        "freshness": [],
        "database": [],
    })()
    costs = {
        "today": {"billed_cost_usd": 1.25, "estimated_cost_usd": 1.1},
        "trend_summary": {"delta_usd": 0.75, "delta_pct": 25.0},
        "top_sessions": [{"id": "s1", "title": "Expensive", "billed_cost_usd": 3.5}],
    }
    models = ModelAnalyticsState(models=[
        ModelUsage(model="claude-sonnet-4-6", provider="anthropic", sessions=4, input_tokens=100, output_tokens=50),
        ModelUsage(model="gpt-5", provider="openai", sessions=1, input_tokens=20, output_tokens=10),
    ])
    providers = ProvidersState(
        providers=[ProviderAuth(id="anthropic", name="Anthropic", status="expired", warnings=["Expired OAuth"])],
        warnings=["Configured provider mismatch"],
    )
    gateway = GatewayState(
        state="running",
        managed_tools=ManagedToolsState(tools=[
            ManagedToolStatus(key="web", label="Web Search", gateway_service="search", route="managed", available=True),
            ManagedToolStatus(key="browser", label="Browser", gateway_service="browser", route="unavailable", available=False, reason="missing"),
        ]),
    )

    summary = build_executive_summary(health, costs, models, providers, gateway)

    assert summary["health"]["broken"] == 2
    assert summary["health"]["warnings"] == 3
    assert summary["spend"]["today_usd"] == 1.25
    assert summary["spend"]["trend_delta_usd"] == 0.75
    assert summary["spend"]["top_session"]["title"] == "Expensive"
    assert summary["model"]["top_model"] == "claude-sonnet-4-6"
    assert summary["model"]["top_provider"] == "anthropic"
    assert summary["model"]["total_tokens"] == 180
    assert summary["risks"]["provider_warnings"] == 2
    assert summary["risks"]["gateway_unavailable_tools"] == 1
    assert summary["actions"][0]["severity"] == "broken"
    assert any(action["source"] == "providers" for action in summary["actions"])
    assert any(action["source"] == "gateway" for action in summary["actions"])


def test_dashboard_summary_handles_empty_inputs() -> None:
    health = type("Health", (), {
        "diagnostics_broken": 0,
        "diagnostics_warnings": 0,
        "features": [],
        "readiness": [],
        "freshness": [],
        "database": [],
    })()

    summary = build_executive_summary(
        health,
        {},
        ModelAnalyticsState(),
        ProvidersState(),
        GatewayState(),
    )

    assert summary["spend"]["today_usd"] == 0
    assert summary["model"]["top_model"] == ""
    assert summary["risks"]["provider_warnings"] == 0
    assert summary["actions"] == []
