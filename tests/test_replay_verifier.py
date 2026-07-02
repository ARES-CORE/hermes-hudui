from datetime import datetime
import json

from backend.collectors.models import SessionInfo
from backend.services.replay_exporter import export_json
from backend.services.replay_normalizer import normalize_session
from backend.services.replay_verifier import verify_replay_files


def _detail():
    session = SessionInfo(
        id="session-verify",
        source="cli",
        title="Verify run",
        started_at=datetime.fromtimestamp(100),
        ended_at=datetime.fromtimestamp(120),
        message_count=1,
        tool_call_count=0,
        input_tokens=1,
        output_tokens=1,
    )
    return normalize_session(
        session,
        [{"id": 1, "role": "user", "content": "Verify this replay", "timestamp": 101}],
    )


def test_verify_replay_files_accepts_exported_receipt_and_replay(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HERMES_HUD_REPLAY_DIR", str(tmp_path))
    detail = _detail()
    export_json(detail)

    run_dir = tmp_path / "runs" / detail.run.replay_id
    result = verify_replay_files(str(run_dir / "receipt.json"), str(run_dir / "replay.redacted.json"))

    assert result["ok"] is True
    assert result["errors"] == []
    receipt = json.loads((run_dir / "receipt.json").read_text(encoding="utf-8"))
    assert result["receipt_hash"] == receipt["hashes"]["receipt_hash"]
    assert receipt["signature_algorithm"] == "ed25519"
    assert result["signature_algorithm"] == "ed25519"
    assert result["signature_valid"] is True


def test_verify_replay_files_rejects_tampered_receipt_hash(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HERMES_HUD_REPLAY_DIR", str(tmp_path))
    detail = _detail()
    export_json(detail)
    run_dir = tmp_path / "runs" / detail.run.replay_id
    receipt_path = run_dir / "receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["hashes"]["receipt_hash"] = "sha256:bad"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    result = verify_replay_files(str(receipt_path), str(run_dir / "replay.redacted.json"))

    assert result["ok"] is False
    assert "Receipt hash does not match receipt payload." in result["errors"]


def test_verify_replay_files_rejects_tampered_signature(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HERMES_HUD_REPLAY_DIR", str(tmp_path))
    detail = _detail()
    export_json(detail)
    run_dir = tmp_path / "runs" / detail.run.replay_id
    receipt_path = run_dir / "receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["signature"] = receipt["signature"][:-4] + "AAAA"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    result = verify_replay_files(str(receipt_path), str(run_dir / "replay.redacted.json"))

    assert result["ok"] is False
    assert "Receipt signature is invalid." in result["errors"]
