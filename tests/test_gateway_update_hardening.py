from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_hermes_update_requires_confirmation_and_surfaces_status() -> None:
    gateway = (ROOT / "frontend/src/components/GatewayPanel.tsx").read_text()
    translations = (ROOT / "frontend/src/i18n/translations.ts").read_text()

    assert 'postPath="/api/hermes/update"' in gateway
    assert 'confirmLabel={t(\'gateway.confirmUpdate\')}' in gateway
    assert 'confirmPrompt={t(\'gateway.updateConfirmPrompt\')}' in gateway
    assert "showLastStatus" in gateway
    assert "setTimeout(() =>" in gateway
    assert "6000" in gateway
    assert "status.log_path" in gateway
    assert "gateway.actionSucceeded" in gateway
    assert "gateway.actionFailed" in gateway

    assert 'postPath="/api/gateway/restart"' in gateway
    restart_block = gateway.split('postPath="/api/gateway/restart"', 1)[1].split("/>", 1)[0]
    assert "confirmPrompt" not in restart_block

    assert "'gateway.updateDescription'" in translations
    assert "'gateway.confirmUpdate'" in translations
    assert "'gateway.updateConfirmPrompt'" in translations
    assert "'gateway.lastRun'" in translations
