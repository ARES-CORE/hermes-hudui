"""Replay data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


ReplayStatus = Literal["success", "failed", "partial", "unknown"]
ReplayEventType = Literal[
    "prompt",
    "assistant_message",
    "tool_call",
    "tool_result",
    "terminal_command",
    "test_passed",
    "test_failed",
    "error",
    "completion",
]
EventStatus = Literal["success", "failed", "warning", "info", "unknown"]


@dataclass
class ReplayCounts:
    messages: int = 0
    tool_calls: int = 0
    skills_used: int = 0
    files_changed: int | None = None
    tests_passed: int | None = None
    tests_failed: int | None = None
    subagents: int | None = None


@dataclass
class ReplayHashes:
    source_hash: str | None = None
    redacted_replay_hash: str | None = None
    receipt_hash: str | None = None


@dataclass
class ReplayRun:
    replay_id: str
    source_session_id: str
    title: str
    status: ReplayStatus
    counts: ReplayCounts
    hashes: ReplayHashes = field(default_factory=ReplayHashes)
    redaction_status: str = "not_scanned"
    started_at: str | None = None
    ended_at: str | None = None
    duration_ms: int | None = None
    primary_model: str | None = None
    total_cost_usd: float | None = None
    created_at: str | None = None
    updated_at: str | None = None


@dataclass
class ReplayEvent:
    event_id: str
    replay_id: str
    type: ReplayEventType
    title: str
    summary: str
    status: EventStatus
    raw_content: str | None = None
    redacted_content: str | None = None
    timestamp: str | None = None
    duration_ms: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReplayArtifact:
    artifact_id: str
    replay_id: str
    type: str
    title: str
    summary: str | None = None
    event_id: str | None = None
    path: str | None = None
    content: str | None = None
    redacted_content: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = None
    hash: str | None = None


@dataclass
class RedactionFinding:
    finding_id: str
    severity: Literal["low", "medium", "high", "critical"]
    type: str
    field_path: str
    preview: str
    replacement: str
    auto_redacted: bool = True


@dataclass
class RunReceipt:
    schema_version: str
    receipt_id: str
    replay_id: str
    source_session_id: str
    title: str
    status: str
    tool_call_count: int
    skills_used: list[dict[str, str | None]]
    hashes: ReplayHashes
    redaction: dict[str, str | int]
    generated_at: str
    generator: dict[str, str]
    started_at: str | None = None
    ended_at: str | None = None
    duration_ms: int | None = None
    model: str | None = None
    total_cost_usd: float | None = None
    files_changed: int | None = None
    tests: dict[str, int | str | None] | None = None


@dataclass
class ReplayDetail:
    run: ReplayRun
    events: list[ReplayEvent] = field(default_factory=list)
    artifacts: list[ReplayArtifact] = field(default_factory=list)
    receipt: RunReceipt | None = None
    missing_data: list[str] = field(default_factory=list)
    redactions: list[RedactionFinding] = field(default_factory=list)


@dataclass
class ReplayExportResult:
    ok: bool
    export_path: str
    receipt_hash: str | None
    redacted_replay_hash: str | None
    redaction_notice: str
