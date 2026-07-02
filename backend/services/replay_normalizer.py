"""Normalize Hermes sessions into replay objects."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.collectors.models import SessionInfo
from backend.collectors.utils import parse_timestamp
from backend.models.replay import ReplayArtifact, ReplayCounts, ReplayDetail, ReplayEvent, ReplayHashes, ReplayRun, RunReceipt


def replay_id_for_session(session_id: str) -> str:
    digest = hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:12]
    return f"replay_{digest}"


def _iso(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    parsed = parse_timestamp(value)
    return parsed.isoformat() if parsed else None


def _hash_payload(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _shorten(text: str, limit: int = 160) -> str:
    clean = re.sub(r"\s+", " ", text or "").strip()
    if len(clean) <= limit:
        return clean
    return f"{clean[: limit - 1]}..."


def _event_id(replay_id: str, index: int, event_type: str, raw_id: Any = None) -> str:
    seed = f"{replay_id}:{index}:{event_type}:{raw_id or ''}"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def _decode_tool_calls(raw: Any) -> list[dict[str, Any]]:
    if not raw:
        return []
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return []
    return []


def _tool_name(call: dict[str, Any]) -> str:
    fn = call.get("function")
    if isinstance(fn, dict) and fn.get("name"):
        return str(fn["name"])
    return str(call.get("name") or call.get("type") or "tool")


def _artifact_id(replay_id: str, artifact_type: str, seed: str) -> str:
    digest = hashlib.sha256(f"{replay_id}:{artifact_type}:{seed}".encode("utf-8")).hexdigest()[:12]
    return f"artifact_{digest}"


def _extract_test_counts(text: str) -> tuple[int | None, int | None]:
    clean = text.lower()
    passed = failed = None
    match = re.search(r"(\d+)\s+passed", clean)
    if match:
        passed = int(match.group(1))
    match = re.search(r"(\d+)\s+failed", clean)
    if match:
        failed = int(match.group(1))
    if "all tests passed" in clean and passed is None:
        passed = 1
        failed = failed or 0
    return passed, failed


def _extract_skill_names(text: str) -> list[str]:
    names: list[str] = []
    patterns = [
        r"\bskill(?:\s+used)?\s*[:=]\s*([A-Za-z0-9_.:/-]+)",
        r"\busing\s+skill\s+([A-Za-z0-9_.:/-]+)",
        r"\bloaded\s+skill\s+([A-Za-z0-9_.:/-]+)",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            name = match.group(1).strip(".,;")
            if name and name not in names:
                names.append(name)
    return names


def _extract_skill_mutations(text: str) -> list[tuple[str, str]]:
    mutations: list[tuple[str, str]] = []
    patterns = [
        ("skill_created", r"\bcreated\s+skill\s+([A-Za-z0-9_.:/-]+)"),
        ("skill_created", r"\bskill\s+created\s*[:=]\s*([A-Za-z0-9_.:/-]+)"),
        ("skill_modified", r"\bmodified\s+skill\s+([A-Za-z0-9_.:/-]+)"),
        ("skill_modified", r"\bupdated\s+skill\s+([A-Za-z0-9_.:/-]+)"),
        ("skill_modified", r"\bskill\s+modified\s*[:=]\s*([A-Za-z0-9_.:/-]+)"),
    ]
    for event_type, pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            name = match.group(1).strip(".,;")
            mutation = (event_type, name)
            if name and mutation not in mutations:
                mutations.append(mutation)
    return mutations


def _extract_project_paths(text: str) -> list[Path]:
    candidates: list[Path] = []
    for match in re.finditer(r"(?:/home|/Users|/workspace|/tmp)/[A-Za-z0-9._/-]+", text):
        value = match.group(0).rstrip(".,;:)")
        path = Path(value).expanduser()
        if path not in candidates:
            candidates.append(path)
    return candidates


def _extract_media_paths(text: str, extensions: tuple[str, ...]) -> list[str]:
    paths: list[str] = []
    extension_pattern = "|".join(re.escape(ext.lstrip(".")) for ext in extensions)
    pattern = rf"(?:/home|/Users|/workspace|/tmp)/[A-Za-z0-9._/-]+\.({extension_pattern})\b"
    for match in re.finditer(pattern, text, flags=re.IGNORECASE):
        value = match.group(0).rstrip(".,;:)")
        if value not in paths:
            paths.append(value)
    return paths


def _tool_arguments(call: dict[str, Any]) -> dict[str, Any]:
    fn = call.get("function")
    args = fn.get("arguments") if isinstance(fn, dict) else call.get("arguments")
    if isinstance(args, dict):
        return args
    if isinstance(args, str):
        try:
            parsed = json.loads(args)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _git_root(path: Path) -> Path | None:
    current = path if path.is_dir() else path.parent
    for candidate in [current, *current.parents]:
        if (candidate / ".git").exists():
            return candidate
    return None


def _git_diff_artifact(run: ReplayRun, project_path: Path) -> ReplayArtifact | None:
    root = _git_root(project_path)
    if root is None:
        return None
    try:
        status = subprocess.run(
            ["git", "status", "--short"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        shortstat = subprocess.run(
            ["git", "diff", "--shortstat"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    status_text = status.stdout.strip()
    shortstat_text = shortstat.stdout.strip()
    if not status_text and not shortstat_text:
        return None
    changed_files = [line for line in status_text.splitlines() if line.strip()]
    content = "\n".join(part for part in [shortstat_text, status_text] if part)
    run.counts.files_changed = len(changed_files) if changed_files else None
    return ReplayArtifact(
        artifact_id=_artifact_id(run.replay_id, "git_diff", str(root)),
        replay_id=run.replay_id,
        type="git_diff",
        title="Git diff summary",
        summary=f"{len(changed_files)} changed files detected in {root.name}.",
        path=str(root),
        content=content,
        redacted_content=content,
        mime_type="text/plain",
        size_bytes=len(content.encode("utf-8")),
        hash=_hash_payload(content),
    )


def _git_file_artifacts(run: ReplayRun, git_artifact: ReplayArtifact) -> list[ReplayArtifact]:
    artifacts: list[ReplayArtifact] = []
    root = Path(git_artifact.path) if git_artifact.path else None
    for line in (git_artifact.content or "").splitlines():
        if not line.strip() or line.startswith(" "):
            continue
        status = line[:2].strip()
        raw_path = line[3:].strip() if len(line) > 3 else ""
        if not raw_path:
            continue
        artifact_type = "generated_file" if status == "??" else "modified_file"
        title = "Generated file" if artifact_type == "generated_file" else "Modified file"
        display_path = str(root / raw_path) if root else raw_path
        content = f"{status or 'changed'} {raw_path}"
        artifacts.append(ReplayArtifact(
            artifact_id=_artifact_id(run.replay_id, artifact_type, content),
            replay_id=run.replay_id,
            type=artifact_type,
            title=title,
            summary=f"{raw_path} was {'created' if artifact_type == 'generated_file' else 'changed'}.",
            path=display_path,
            content=content,
            redacted_content=content,
            mime_type="text/plain",
            size_bytes=len(content.encode("utf-8")),
            hash=_hash_payload(content),
        ))
    return artifacts


def _media_artifact(run: ReplayRun, artifact_type: str, path: str) -> ReplayArtifact:
    file_path = Path(path)
    exists = file_path.exists()
    size_bytes = file_path.stat().st_size if exists and file_path.is_file() else None
    content = f"{artifact_type}: {path}"
    if artifact_type == "screenshot":
        title = "Screenshot"
        mime_type = "image/png" if file_path.suffix.lower() == ".png" else "image/jpeg"
        summary = "Screenshot path detected from local session data."
    else:
        title = "Browser recording"
        mime_type = "video/webm" if file_path.suffix.lower() == ".webm" else "video/mp4"
        summary = "Browser recording path detected from local session data."
    if not exists:
        summary = f"{summary} File not found locally."
    return ReplayArtifact(
        artifact_id=_artifact_id(run.replay_id, artifact_type, path),
        replay_id=run.replay_id,
        type=artifact_type,
        title=title,
        summary=summary,
        path=path,
        content=content,
        redacted_content=content,
        mime_type=mime_type,
        size_bytes=size_bytes,
        hash=_hash_payload(content),
    )


def _session_status(session: SessionInfo) -> str:
    if session.ended_at:
        return "success"
    return "unknown"


def build_replay_run(session: SessionInfo) -> ReplayRun:
    replay_id = replay_id_for_session(session.id)
    duration_ms = None
    if session.started_at and session.ended_at:
        duration_ms = int((session.ended_at - session.started_at).total_seconds() * 1000)

    started_at = _iso(session.started_at)
    ended_at = _iso(session.ended_at)
    return ReplayRun(
        replay_id=replay_id,
        source_session_id=session.id,
        title=session.title or session.id[:8],
        status=_session_status(session),
        started_at=started_at,
        ended_at=ended_at,
        duration_ms=duration_ms,
        primary_model=session.model,
        total_cost_usd=session.estimated_cost_usd,
        counts=ReplayCounts(
            messages=session.message_count,
            tool_calls=session.tool_call_count,
            skills_used=0,
        ),
        created_at=started_at,
        updated_at=ended_at or started_at,
    )


def normalize_session(session: SessionInfo, messages: list[dict[str, Any]]) -> ReplayDetail:
    run = build_replay_run(session)
    events: list[ReplayEvent] = []
    artifacts: list[ReplayArtifact] = []
    missing_data: list[str] = []
    tool_names: list[str] = []
    skill_names: list[str] = []
    transcript_lines: list[str] = []
    project_paths: list[Path] = []
    terminal_outputs: list[str] = []
    screenshot_paths: list[str] = []
    browser_recording_paths: list[str] = []
    test_passed_total = 0
    test_failed_total = 0

    if not messages:
        missing_data.append("No message history found for this session.")

    for index, message in enumerate(messages):
        role = str(message.get("role") or "unknown")
        content = str(message.get("content") or "")
        timestamp = _iso(message.get("timestamp")) or run.started_at
        raw_id = message.get("id")
        tool_calls = _decode_tool_calls(message.get("tool_calls"))
        for skill_name in _extract_skill_names(content):
            if skill_name not in skill_names:
                skill_names.append(skill_name)
        skill_mutations = _extract_skill_mutations(content)
        for _, skill_name in skill_mutations:
            if skill_name not in skill_names:
                skill_names.append(skill_name)
        for project_path in _extract_project_paths(content):
            if project_path not in project_paths:
                project_paths.append(project_path)
        for path in _extract_media_paths(content, (".png", ".jpg", ".jpeg")):
            if path not in screenshot_paths:
                screenshot_paths.append(path)
        for path in _extract_media_paths(content, (".webm", ".mp4", ".mov")):
            if path not in browser_recording_paths:
                browser_recording_paths.append(path)
        if role in {"user", "assistant"} and content:
            transcript_lines.append(f"{role}: {_shorten(content, 220)}")

        if role == "user":
            events.append(ReplayEvent(
                event_id=_event_id(run.replay_id, index, "prompt", raw_id),
                replay_id=run.replay_id,
                type="prompt",
                title="User prompt",
                summary=_shorten(content) or "Prompt content unavailable.",
                raw_content=content,
                timestamp=timestamp,
                status="info",
            ))
        elif role == "assistant":
            events.append(ReplayEvent(
                event_id=_event_id(run.replay_id, index, "assistant_message", raw_id),
                replay_id=run.replay_id,
                type="assistant_message",
                title="Assistant message",
                summary=_shorten(content) or "Assistant content unavailable.",
                raw_content=content,
                timestamp=timestamp,
                status="info",
            ))
        elif role == "tool":
            if content:
                terminal_outputs.append(content)
            passed, failed = _extract_test_counts(content)
            if passed is not None or failed is not None:
                test_passed_total += passed or 0
                test_failed_total += failed or 0
            events.append(ReplayEvent(
                event_id=_event_id(run.replay_id, index, "tool_result", raw_id),
                replay_id=run.replay_id,
                type="tool_result",
                title="Tool result",
                summary=_shorten(content) or "Tool result unavailable.",
                raw_content=content,
                timestamp=timestamp,
                status="success",
            ))
        else:
            events.append(ReplayEvent(
                event_id=_event_id(run.replay_id, index, "error", raw_id),
                replay_id=run.replay_id,
                type="error",
                title="Unrecognized message",
                summary=f"Unsupported role: {role}",
                raw_content=content,
                timestamp=timestamp,
                status="warning",
                metadata={"role": role},
            ))

        for mutation_index, (event_type, skill_name) in enumerate(skill_mutations):
            action = "created" if event_type == "skill_created" else "modified"
            events.append(ReplayEvent(
                event_id=_event_id(run.replay_id, index, f"{event_type}:{mutation_index}", raw_id),
                replay_id=run.replay_id,
                type=event_type,
                title=f"Skill {action}: {skill_name}",
                summary=f"Detected explicit skill {action} event for {skill_name}.",
                raw_content=content,
                timestamp=timestamp,
                status="success",
                metadata={"skill_name": skill_name},
            ))

        for call_index, call in enumerate(tool_calls):
            name = _tool_name(call)
            tool_names.append(name)
            args = _tool_arguments(call)
            for key in ("cwd", "workdir", "path", "repo", "project_path"):
                value = args.get(key)
                if isinstance(value, str):
                    path = Path(value).expanduser()
                    if path not in project_paths:
                        project_paths.append(path)
            for key in ("screenshot", "screenshot_path", "image_path", "path"):
                value = args.get(key)
                if isinstance(value, str) and Path(value).suffix.lower() in {".png", ".jpg", ".jpeg"}:
                    if value not in screenshot_paths:
                        screenshot_paths.append(value)
            for key in ("recording", "recording_path", "video_path", "path"):
                value = args.get(key)
                if isinstance(value, str) and Path(value).suffix.lower() in {".webm", ".mp4", ".mov"}:
                    if value not in browser_recording_paths:
                        browser_recording_paths.append(value)
            event_type = "terminal_command" if name in {"shell", "bash", "exec", "exec_command"} else "tool_call"
            events.append(ReplayEvent(
                event_id=_event_id(run.replay_id, index, f"tool_call:{call_index}", raw_id),
                replay_id=run.replay_id,
                type=event_type,
                title=f"Tool call: {name}",
                summary=f"Called {name}",
                raw_content=json.dumps(call, sort_keys=True),
                timestamp=timestamp,
                status="info",
                metadata={"tool_name": name},
            ))

    actual_tool_calls = len(tool_names)
    if actual_tool_calls and actual_tool_calls != run.counts.tool_calls:
        run.counts.tool_calls = actual_tool_calls
    run.counts.skills_used = len(skill_names)

    if transcript_lines:
        transcript = "\n".join(transcript_lines[:40])
        artifacts.append(ReplayArtifact(
            artifact_id=_artifact_id(run.replay_id, "transcript_summary", transcript),
            replay_id=run.replay_id,
            type="transcript_summary",
            title="Transcript summary",
            summary=f"{len(transcript_lines)} user/assistant messages summarized.",
            content=transcript,
            redacted_content=transcript,
            mime_type="text/markdown",
            size_bytes=len(transcript.encode("utf-8")),
            hash=_hash_payload(transcript),
        ))
    if tool_names:
        tool_summary = "\n".join(f"- {name}" for name in tool_names)
        tool_counts = {name: tool_names.count(name) for name in sorted(set(tool_names))}
        tool_grouping = "\n".join(f"- {name}: {count}" for name, count in tool_counts.items())
        artifacts.append(ReplayArtifact(
            artifact_id=_artifact_id(run.replay_id, "tool_call_list", tool_summary),
            replay_id=run.replay_id,
            type="tool_call_list",
            title="Tool call list",
            summary=f"{len(tool_names)} tool calls detected.",
            content=tool_summary,
            redacted_content=tool_summary,
            mime_type="text/markdown",
            size_bytes=len(tool_summary.encode("utf-8")),
            hash=_hash_payload(tool_summary),
        ))
        artifacts.append(ReplayArtifact(
            artifact_id=_artifact_id(run.replay_id, "tool_call_grouping", tool_grouping),
            replay_id=run.replay_id,
            type="tool_call_grouping",
            title="Tool call grouping",
            summary=f"{len(tool_counts)} distinct tools used across {len(tool_names)} calls.",
            content=tool_grouping,
            redacted_content=tool_grouping,
            mime_type="text/markdown",
            size_bytes=len(tool_grouping.encode("utf-8")),
            hash=_hash_payload(tool_grouping),
        ))
    cost_model_summary = (
        f"Model: {run.primary_model or 'Unknown'}\n"
        f"Cost: {run.total_cost_usd if run.total_cost_usd is not None else 'Unknown'}\n"
        f"Messages: {run.counts.messages}\n"
        f"Tool calls: {run.counts.tool_calls}"
    )
    artifacts.append(ReplayArtifact(
        artifact_id=_artifact_id(run.replay_id, "cost_summary", cost_model_summary),
        replay_id=run.replay_id,
        type="cost_summary",
        title="Cost and model summary",
        summary=f"{run.primary_model or 'Unknown model'} · {run.total_cost_usd if run.total_cost_usd is not None else 'unknown cost'}",
        content=cost_model_summary,
        redacted_content=cost_model_summary,
        mime_type="text/markdown",
        size_bytes=len(cost_model_summary.encode("utf-8")),
        hash=_hash_payload(cost_model_summary),
    ))
    if test_passed_total or test_failed_total:
        test_summary = f"Passed: {test_passed_total}\nFailed: {test_failed_total}"
        artifacts.append(ReplayArtifact(
            artifact_id=_artifact_id(run.replay_id, "test_output", test_summary),
            replay_id=run.replay_id,
            type="test_output",
            title="Test result extraction",
            summary=f"{test_passed_total} passed, {test_failed_total} failed.",
            content=test_summary,
            redacted_content=test_summary,
            mime_type="text/markdown",
            size_bytes=len(test_summary.encode("utf-8")),
            hash=_hash_payload(test_summary),
        ))
        run.counts.tests_passed = test_passed_total
        run.counts.tests_failed = test_failed_total
    if terminal_outputs:
        output_count = len(terminal_outputs)
        output_bytes = sum(len(output.encode("utf-8")) for output in terminal_outputs)
        terminal_summary = f"{output_count} tool/terminal outputs captured; {output_bytes} bytes hidden by Safe Share Mode."
        artifacts.append(ReplayArtifact(
            artifact_id=_artifact_id(run.replay_id, "terminal_output", terminal_summary),
            replay_id=run.replay_id,
            type="terminal_output",
            title="Terminal output",
            summary=terminal_summary,
            content="[REDACTED_TERMINAL_OUTPUT]",
            redacted_content="[REDACTED_TERMINAL_OUTPUT]",
            mime_type="text/plain",
            size_bytes=len("[REDACTED_TERMINAL_OUTPUT]".encode("utf-8")),
            hash=_hash_payload(terminal_summary),
        ))
    for path in screenshot_paths:
        artifacts.append(_media_artifact(run, "screenshot", path))
    for path in browser_recording_paths:
        artifacts.append(_media_artifact(run, "browser_recording", path))
    if skill_names:
        skill_summary = "\n".join(f"- {name} (version unavailable, hash unavailable)" for name in skill_names)
        artifacts.append(ReplayArtifact(
            artifact_id=_artifact_id(run.replay_id, "skill_card", skill_summary),
            replay_id=run.replay_id,
            type="skill_card",
            title="Skill provenance",
            summary=f"{len(skill_names)} skills detected; version/hash unavailable unless present in source data.",
            content=skill_summary,
            redacted_content=skill_summary,
            mime_type="text/markdown",
            size_bytes=len(skill_summary.encode("utf-8")),
            hash=_hash_payload(skill_summary),
        ))
    for project_path in project_paths:
        artifact = _git_diff_artifact(run, project_path)
        if artifact:
            artifacts.append(artifact)
            artifacts.extend(_git_file_artifacts(run, artifact))
            break

    events.sort(key=lambda event: event.timestamp or "")
    if events:
        events.append(ReplayEvent(
            event_id=_event_id(run.replay_id, len(events), "completion", session.id),
            replay_id=run.replay_id,
            type="completion",
            title="Replay complete",
            summary="Normalized replay timeline generated from local Hermes session data.",
            timestamp=run.ended_at or events[-1].timestamp,
            status="success" if run.status == "success" else "unknown",
        ))

    source_hash = _hash_payload({
        "session_id": session.id,
        "messages": messages,
        "events": [event.__dict__ for event in events],
        "artifacts": [artifact.__dict__ for artifact in artifacts],
    })
    redacted_hash = _hash_payload({
        "replay_id": run.replay_id,
        "events": [
            {
                "event_id": event.event_id,
                "type": event.type,
                "title": event.title,
                "summary": event.summary,
                "timestamp": event.timestamp,
                "status": event.status,
            }
            for event in events
        ],
    })
    run.hashes = ReplayHashes(source_hash=source_hash, redacted_replay_hash=redacted_hash)

    receipt = RunReceipt(
        schema_version="0.1",
        receipt_id=f"receipt_{run.replay_id}",
        replay_id=run.replay_id,
        source_session_id=run.source_session_id,
        title=run.title,
        status=run.status,
        started_at=run.started_at,
        ended_at=run.ended_at,
        duration_ms=run.duration_ms,
        model=run.primary_model,
        total_cost_usd=run.total_cost_usd,
        files_changed=run.counts.files_changed,
        tests={
            "passed": run.counts.tests_passed,
            "failed": run.counts.tests_failed,
            "command": None,
        } if run.counts.tests_passed is not None or run.counts.tests_failed is not None else None,
        tool_call_count=run.counts.tool_calls,
        skills_used=[{"name": name, "version": None, "hash": None} for name in skill_names],
        hashes=run.hashes,
        redaction={"mode": "safe_share", "findings_count": 0, "redacted_fields_count": 0},
        generated_at=datetime.now().isoformat(),
        generator={"name": "hermes-replay", "version": "0.1"},
    )
    receipt.hashes.receipt_hash = _hash_payload({**receipt.__dict__, "hashes": receipt.hashes.__dict__ | {"receipt_hash": None}})
    run.hashes.receipt_hash = receipt.hashes.receipt_hash

    return ReplayDetail(run=run, events=events, artifacts=artifacts, receipt=receipt, missing_data=missing_data)
