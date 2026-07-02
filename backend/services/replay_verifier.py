"""Local Replay receipt/replay verification."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.services.replay_normalizer import _hash_payload
from backend.services.replay_signer import verify_signature


def _load_json(path: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        data = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, f"File not found: {path}"
    except json.JSONDecodeError as exc:
        return None, f"Invalid JSON in {path}: {exc}"
    except OSError as exc:
        return None, f"Could not read {path}: {exc}"
    if not isinstance(data, dict):
        return None, f"Expected JSON object in {path}"
    return data, None


def _receipt_hash(receipt: dict[str, Any]) -> str:
    payload = dict(receipt)
    for key in ["signature_algorithm", "signature", "public_key", "signed_at"]:
        payload.pop(key, None)
    hashes = dict(payload.get("hashes") or {})
    hashes["receipt_hash"] = None
    payload["hashes"] = hashes
    return _hash_payload(payload)


def verify_replay_files(receipt_path: str, replay_path: str) -> dict[str, Any]:
    receipt, receipt_error = _load_json(receipt_path)
    replay_doc, replay_error = _load_json(replay_path)
    errors = [error for error in [receipt_error, replay_error] if error]
    warnings: list[str] = []

    if receipt is None or replay_doc is None:
        return {"ok": False, "errors": errors, "warnings": warnings}

    replay = replay_doc.get("replay")
    if not isinstance(replay, dict):
        errors.append("Replay JSON is missing replay object.")
        replay = {}

    run = replay.get("run") if isinstance(replay.get("run"), dict) else {}
    receipt_hashes = receipt.get("hashes") if isinstance(receipt.get("hashes"), dict) else {}
    run_hashes = run.get("hashes") if isinstance(run.get("hashes"), dict) else {}

    for field in ["schema_version", "receipt_id", "replay_id", "source_session_id", "hashes", "redaction"]:
        if field not in receipt:
            errors.append(f"Receipt missing required field: {field}")
    if replay_doc.get("schema_version") != "0.1":
        errors.append("Replay JSON schema_version must be 0.1.")
    if receipt.get("schema_version") != "0.1":
        errors.append("Receipt schema_version must be 0.1.")
    if receipt.get("replay_id") != run.get("replay_id"):
        errors.append("Receipt replay_id does not match replay run.")
    if receipt.get("source_session_id") != run.get("source_session_id"):
        errors.append("Receipt source_session_id does not match replay run.")

    expected_receipt_hash = receipt_hashes.get("receipt_hash")
    actual_receipt_hash = _receipt_hash(receipt)
    if expected_receipt_hash != actual_receipt_hash:
        errors.append("Receipt hash does not match receipt payload.")

    expected_replay_hash = receipt_hashes.get("redacted_replay_hash")
    if expected_replay_hash != run_hashes.get("redacted_replay_hash"):
        errors.append("Receipt redacted_replay_hash does not match replay run hash.")

    redaction = receipt.get("redaction") if isinstance(receipt.get("redaction"), dict) else {}
    if not redaction.get("mode"):
        errors.append("Receipt missing redaction mode.")
    if redaction.get("mode") == "raw":
        warnings.append("Receipt declares raw redaction mode.")

    signature = receipt.get("signature")
    public_key = receipt.get("public_key")
    if signature or public_key:
        if receipt.get("signature_algorithm") != "ed25519":
            errors.append("Unsupported signature algorithm.")
        elif not signature or not public_key:
            errors.append("Incomplete signature fields.")
        elif not verify_signature(str(expected_receipt_hash), str(expected_replay_hash), str(signature), str(public_key)):
            errors.append("Receipt signature is invalid.")
    else:
        warnings.append("No signature present; local hash verification only.")

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "receipt_hash": expected_receipt_hash,
        "redacted_replay_hash": expected_replay_hash,
        "redaction_mode": redaction.get("mode"),
        "signature_algorithm": receipt.get("signature_algorithm"),
        "signature_valid": bool(signature or public_key) and "Receipt signature is invalid." not in errors and "Unsupported signature algorithm." not in errors and "Incomplete signature fields." not in errors,
    }
