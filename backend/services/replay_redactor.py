"""Local Replay redaction scanner."""

from __future__ import annotations

import copy
import re
from dataclasses import fields, is_dataclass
from typing import Any

from backend.models.replay import RedactionFinding, ReplayDetail


PATTERNS: list[tuple[str, str, str, re.Pattern[str]]] = [
    ("api_key", "critical", "[REDACTED_API_KEY]", re.compile(r"\b(?:sk-[A-Za-z0-9_-]{20,}|sk-ant-[A-Za-z0-9_-]{20,})\b")),
    ("bearer_token", "critical", "[REDACTED_BEARER_TOKEN]", re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{16,}", re.IGNORECASE)),
    ("github_token", "critical", "[REDACTED_GITHUB_TOKEN]", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{20,}\b")),
    ("aws_key", "critical", "[REDACTED_AWS_KEY]", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("ssh_key", "critical", "[REDACTED_SSH_KEY]", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.DOTALL)),
    ("email", "medium", "[REDACTED_EMAIL]", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("env_var", "high", "[REDACTED_ENV_VALUE]", re.compile(r"\b[A-Z][A-Z0-9_]{2,}\s*=\s*[^\s'\"]{8,}")),
    ("basic_auth_url", "high", "[REDACTED_URL]", re.compile(r"https?://[^/\s:@]+:[^/\s:@]+@[^\s]+")),
    ("tokenized_url", "high", "[REDACTED_URL]", re.compile(r"https?://[^\s]+[?&](?:token|key|secret|auth|signature)=[^\s&]+", re.IGNORECASE)),
    ("local_path", "medium", "[REDACTED_LOCAL_PATH]", re.compile(r"(?:/Users|/home|/var/folders|/tmp)/[A-Za-z0-9._/-]+")),
]

RAW_FIELD_NAMES = {"raw_content", "reasoning"}
RAW_METADATA_KEYS = {"arguments", "args", "command", "output", "stderr", "stdout"}


def _finding_id(field_path: str, kind: str, index: int) -> str:
    safe_path = re.sub(r"[^a-zA-Z0-9]+", "_", field_path).strip("_")[:48]
    return f"{safe_path}_{kind}_{index}"


def _scan_text(value: str, field_path: str, offset: int = 0) -> tuple[str, list[RedactionFinding]]:
    redacted = value
    findings: list[RedactionFinding] = []
    counters: dict[str, int] = {}
    for kind, severity, base_replacement, pattern in PATTERNS:
        matches = list(pattern.finditer(redacted))
        for match in matches:
            counters[kind] = counters.get(kind, 0) + 1
            replacement = f"{base_replacement[:-1]}_{counters[kind]}]"
            preview = match.group(0)
            findings.append(RedactionFinding(
                finding_id=_finding_id(field_path, kind, offset + len(findings) + 1),
                severity=severity,  # type: ignore[arg-type]
                type=kind,
                field_path=field_path,
                preview=preview[:80],
                replacement=replacement,
            ))
            redacted = redacted.replace(preview, replacement)
    return redacted, findings


def _redact_value(value: Any, field_path: str) -> tuple[Any, list[RedactionFinding]]:
    if isinstance(value, str):
        return _scan_text(value, field_path)
    if isinstance(value, list):
        items = []
        findings: list[RedactionFinding] = []
        for index, item in enumerate(value):
            redacted, item_findings = _redact_value(item, f"{field_path}[{index}]")
            items.append(redacted)
            findings.extend(item_findings)
        return items, findings
    if isinstance(value, dict):
        result: dict[Any, Any] = {}
        findings: list[RedactionFinding] = []
        for key, item in value.items():
            child_path = f"{field_path}.{key}"
            if str(key) in RAW_METADATA_KEYS and isinstance(item, str):
                result[key] = "[REDACTED_RAW_FIELD]"
                findings.append(RedactionFinding(
                    finding_id=_finding_id(child_path, "raw_field", 1),
                    severity="high",
                    type="raw_field",
                    field_path=child_path,
                    preview=item[:80],
                    replacement="[REDACTED_RAW_FIELD]",
                ))
                continue
            redacted, item_findings = _redact_value(item, child_path)
            result[key] = redacted
            findings.extend(item_findings)
        return result, findings
    return value, []


def _copy_dataclass(obj: Any, field_path: str) -> tuple[Any, list[RedactionFinding]]:
    cloned = copy.deepcopy(obj)
    findings: list[RedactionFinding] = []
    if not is_dataclass(cloned):
        return cloned, findings
    for field in fields(cloned):
        value = getattr(cloned, field.name)
        child_path = f"{field_path}.{field.name}"
        if field.name in RAW_FIELD_NAMES and isinstance(value, str) and value:
            setattr(cloned, field.name, "[REDACTED_RAW_FIELD]")
            findings.append(RedactionFinding(
                finding_id=_finding_id(child_path, "raw_field", 1),
                severity="high",
                type="raw_field",
                field_path=child_path,
                preview=value[:80],
                replacement="[REDACTED_RAW_FIELD]",
            ))
            continue
        redacted, item_findings = _redact_value(value, child_path)
        setattr(cloned, field.name, redacted)
        findings.extend(item_findings)
    return cloned, findings


def scan_replay(detail: ReplayDetail) -> ReplayDetail:
    redacted = copy.deepcopy(detail)
    findings: list[RedactionFinding] = []
    redacted_events = []
    for index, event in enumerate(detail.events):
        cloned, event_findings = _copy_dataclass(event, f"events[{index}]")
        redacted_events.append(cloned)
        findings.extend(event_findings)
    redacted_artifacts = []
    for index, artifact in enumerate(detail.artifacts):
        cloned, artifact_findings = _copy_dataclass(artifact, f"artifacts[{index}]")
        redacted_artifacts.append(cloned)
        findings.extend(artifact_findings)

    redacted.events = redacted_events
    redacted.artifacts = redacted_artifacts
    redacted.redactions = findings
    redacted.run.redaction_status = "needs_review" if findings else "safe"
    if redacted.receipt:
        redacted.receipt.redaction = {
            "mode": "safe_share",
            "findings_count": len(findings),
            "redacted_fields_count": len(findings),
        }
    return redacted


def apply_manual_redactions(detail: ReplayDetail, rules: list[dict[str, str]]) -> ReplayDetail:
    redacted = scan_replay(detail)
    applied = 0
    for rule_index, rule in enumerate(rules):
        value = (rule.get("value") or "").strip()
        replacement = (rule.get("replacement") or "[REDACTED_CUSTOM]").strip() or "[REDACTED_CUSTOM]"
        if not value:
            continue
        for event_index, event in enumerate(redacted.events):
            for field_name in ("title", "summary", "raw_content", "redacted_content"):
                current = getattr(event, field_name)
                if isinstance(current, str) and value in current:
                    setattr(event, field_name, current.replace(value, replacement))
                    applied += 1
                    redacted.redactions.append(RedactionFinding(
                        finding_id=_finding_id(f"events[{event_index}].{field_name}", "custom", rule_index + 1),
                        severity="medium",
                        type="custom",
                        field_path=f"events[{event_index}].{field_name}",
                        preview=replacement,
                        replacement=replacement,
                        auto_redacted=False,
                    ))
        for artifact_index, artifact in enumerate(redacted.artifacts):
            for field_name in ("title", "summary", "content", "redacted_content"):
                current = getattr(artifact, field_name)
                if isinstance(current, str) and value in current:
                    setattr(artifact, field_name, current.replace(value, replacement))
                    applied += 1
                    redacted.redactions.append(RedactionFinding(
                        finding_id=_finding_id(f"artifacts[{artifact_index}].{field_name}", "custom", rule_index + 1),
                        severity="medium",
                        type="custom",
                        field_path=f"artifacts[{artifact_index}].{field_name}",
                        preview=replacement,
                        replacement=replacement,
                        auto_redacted=False,
                    ))
    redacted.run.redaction_status = "manual_override" if applied else redacted.run.redaction_status
    if redacted.receipt:
        redacted.receipt.redaction = {
            "mode": "custom" if applied else "safe_share",
            "findings_count": len(redacted.redactions),
            "redacted_fields_count": len(redacted.redactions),
        }
    return redacted
