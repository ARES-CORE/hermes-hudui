from datetime import datetime

from backend.collectors.models import SessionInfo
from backend.services.replay_normalizer import normalize_session
from backend.services.replay_redactor import apply_manual_redactions, scan_replay


def _detail():
    session = SessionInfo(
        id="session-secret",
        source="cli",
        title="Secret run",
        started_at=datetime.fromtimestamp(100),
        ended_at=datetime.fromtimestamp(120),
        message_count=1,
        tool_call_count=0,
        input_tokens=1,
        output_tokens=1,
    )
    return normalize_session(
        session,
        [
            {
                "id": 1,
                "role": "user",
                "content": "Email me at person@example.com from /home/joey/project with sk-abcdefghijklmnopqrstuvwxyz",
                "timestamp": 101,
            }
        ],
    )


def test_scan_replay_detects_common_secret_patterns() -> None:
    redacted = scan_replay(_detail())

    finding_types = {finding.type for finding in redacted.redactions}

    assert {"api_key", "email", "local_path", "raw_field"}.issubset(finding_types)
    assert redacted.run.redaction_status == "needs_review"
    assert redacted.receipt is not None
    assert redacted.receipt.redaction["findings_count"] == len(redacted.redactions)


def test_scan_replay_redacts_raw_event_content_by_default() -> None:
    redacted = scan_replay(_detail())

    assert redacted.events[0].raw_content == "[REDACTED_RAW_FIELD]"
    assert "person@example.com" not in redacted.events[0].summary
    assert "sk-abcdefghijklmnopqrstuvwxyz" not in redacted.events[0].summary


def test_apply_manual_redactions_replaces_exact_values_in_preview_fields() -> None:
    redacted = apply_manual_redactions(
        _detail(),
        [{"value": "Email me", "replacement": "[REDACTED_CUSTOM_INTENT]"}],
    )

    assert redacted.run.redaction_status == "manual_override"
    assert redacted.events[0].summary.startswith("[REDACTED_CUSTOM_INTENT]")
    assert any(finding.type == "custom" and not finding.auto_redacted for finding in redacted.redactions)
