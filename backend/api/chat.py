"""API routes for Agent Chat feature."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..chat import (
    ChatEngine,
    ChatNotAvailableError,
    ChatSession,
    chat_engine,
)
from ..collectors.sessions import collect_sessions

router = APIRouter(prefix="/chat", tags=["chat"])


# Request/Response Models
class CreateSessionRequest(BaseModel):
    profile: str | None = None
    model: str | None = None


class SendMessageRequest(BaseModel):
    content: str
    lang: str | None = None


class AISDKSendRequest(BaseModel):
    messages: list[dict]
    lang: str | None = None


class SessionResponse(BaseModel):
    id: str
    profile: str | None
    model: str | None
    title: str
    backend_type: str
    is_active: bool
    message_count: int


class ComposerStateResponse(BaseModel):
    model: str
    is_streaming: bool
    context_tokens: int
    status: str = "idle"
    elapsed_ms: int = 0
    first_token_ms: int | None = None
    total_ms: int | None = None
    process_start_ms: int | None = None
    resumed: bool = False
    recent_first_token_avg_ms: int | None = None
    recent_total_avg_ms: int | None = None
    recent_runs: int = 0


@router.post("/sessions", response_model=SessionResponse)
async def create_session(request: CreateSessionRequest) -> SessionResponse:
    """Create a new chat session."""
    try:
        session = chat_engine.create_session(
            profile=request.profile, model=request.model
        )
        return SessionResponse(
            id=session.id,
            profile=session.profile,
            model=session.model,
            title=session.title,
            backend_type=session.backend_type,
            is_active=session.is_active,
            message_count=session.message_count,
        )
    except ChatNotAvailableError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/sessions", response_model=list[SessionResponse])
async def list_sessions() -> list[SessionResponse]:
    """List all active chat sessions."""
    sessions = chat_engine.list_sessions()
    return [
        SessionResponse(
            id=s.id,
            profile=s.profile,
            model=s.model,
            title=s.title,
            backend_type=s.backend_type,
            is_active=s.is_active,
            message_count=s.message_count,
        )
        for s in sessions
    ]


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str) -> SessionResponse:
    """Get a specific session."""
    session = chat_engine.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return SessionResponse(
        id=session.id,
        profile=session.profile,
        model=session.model,
        title=session.title,
        backend_type=session.backend_type,
        is_active=session.is_active,
        message_count=session.message_count,
    )


@router.delete("/sessions/{session_id}")
async def end_session(session_id: str) -> dict[str, str]:
    """End a chat session."""
    if chat_engine.end_session(session_id):
        return {"status": "ended", "session_id": session_id}
    raise HTTPException(status_code=404, detail="Session not found")


@router.post("/sessions/{session_id}/send")
async def send_message(session_id: str, request: SendMessageRequest) -> dict[str, str]:
    """Send a message to a session."""
    session = chat_engine.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if not session.is_active:
        raise HTTPException(status_code=409, detail="Session is inactive")

    message = request.content
    if request.lang and request.lang != "en":
        lang_names = {"zh": "Chinese", "ja": "Japanese", "ko": "Korean", "es": "Spanish", "fr": "French", "de": "German"}
        lang_name = lang_names.get(request.lang, request.lang)
        message = f"[Respond in {lang_name}] {message}"

    # Send message - this creates the streamer
    try:
        chat_engine.send_message(session_id, message)
        return {"status": "accepted", "session_id": session_id}
    except ChatNotAvailableError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/{session_id}/message")
async def send_and_stream(
    session_id: str, request: AISDKSendRequest
) -> StreamingResponse:
    """Send a message and stream the response — AI SDK Data Stream Protocol v1."""
    session = chat_engine.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if not session.is_active:
        raise HTTPException(status_code=409, detail="Session is inactive")

    # Extract text content from the last user message's parts
    last = request.messages[-1] if request.messages else None
    if not last or last.get("role") != "user":
        raise HTTPException(status_code=400, detail="Last message must be from user")

    content = "".join(
        p.get("text", "") for p in last.get("parts", []) if p.get("type") == "text"
    )
    if not content:
        content = str(last.get("content", ""))
    if not content.strip():
        raise HTTPException(status_code=400, detail="Message content is empty")

    if request.lang and request.lang != "en":
        lang_names = {
            "zh": "Chinese", "ja": "Japanese", "ko": "Korean",
            "es": "Spanish", "fr": "French", "de": "German",
        }
        lang_name = lang_names.get(request.lang, request.lang)
        content = f"[Respond in {lang_name}] {content}"

    try:
        streamer = chat_engine.send_message(session_id, content)
    except ChatNotAvailableError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    def event_generator():
        yield 'data: {"type":"start"}\n\n'
        for event in streamer.iter_events():
            yield streamer.to_sse(event)
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "x-vercel-ai-ui-message-stream": "v1",
        },
    )


@router.get("/sessions/{session_id}/stream")
async def stream_response(session_id: str) -> StreamingResponse:
    """Stream chat response via SSE."""
    session = chat_engine.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if not session.is_active:
        raise HTTPException(status_code=409, detail="Session is inactive")

    try:
        # This is called when user sends a message via POST first
        # The streamer was created during that call
        streamer = chat_engine._streamers.get(session_id)

        if not streamer:
            # No active stream, return error
            raise HTTPException(
                status_code=400, detail="No active message stream. Send message first."
            )

        def event_generator():
            """Generate SSE events."""
            for event in streamer.iter_events():
                yield streamer.to_sse(event)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable nginx buffering
            },
        )

    except ChatNotAvailableError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/sessions/{session_id}/cancel")
async def cancel_stream(session_id: str) -> dict[str, str]:
    """Cancel an active streaming response by killing the subprocess."""
    session = chat_engine.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    chat_engine.cancel_stream(session_id)
    return {"status": "cancelled", "session_id": session_id}


@router.get("/sessions/{session_id}/history")
async def get_history(session_id: str, limit: int = 50) -> list[dict[str, Any]]:
    """Get message history for a session from state.db."""
    # This reads from the existing sessions collector
    # We just need to filter by session_id
    sessions_state = collect_sessions()

    # Find session in database
    for session in sessions_state.recent_sessions:
        if session.session_id == session_id:
            # Get detailed messages from state.db
            # This would need a new collector to read messages table
            # For now, return placeholder
            return []

    return []


@router.get("/sessions/{session_id}/composer", response_model=ComposerStateResponse)
async def get_composer_state(session_id: str) -> ComposerStateResponse:
    """Get composer state for UI footer."""
    try:
        state = chat_engine.get_composer_state(session_id)
        return ComposerStateResponse(
            model=state.model,
            is_streaming=state.is_streaming,
            context_tokens=state.context_tokens,
            status=state.status,
            elapsed_ms=state.elapsed_ms,
            first_token_ms=state.first_token_ms,
            total_ms=state.total_ms,
            process_start_ms=state.process_start_ms,
            resumed=state.resumed,
            recent_first_token_avg_ms=state.recent_first_token_avg_ms,
            recent_total_avg_ms=state.recent_total_avg_ms,
            recent_runs=state.recent_runs,
        )
    except Exception as e:
        # Return default if session not found
        return ComposerStateResponse(
            model="unknown",
            is_streaming=False,
            context_tokens=0,
            status="idle",
            elapsed_ms=0,
        )


@router.get("/available")
async def check_availability() -> dict[str, Any]:
    """Check if chat functionality is available."""
    cli_available = chat_engine.is_available()

    return {
        "available": cli_available,
        "cli_available": cli_available,
    }


@router.get("/diagnostics")
async def check_diagnostics() -> dict[str, Any]:
    """Return slower chat backend diagnostics outside the tab-open path."""
    from ..chat import TmuxChatFallback

    cli_available = chat_engine.is_available()

    direct_import = False
    try:
        from run_agent import AIAgent

        direct_import = True
    except ImportError:
        pass

    tmux_available = TmuxChatFallback.is_available()
    tmux_pane = TmuxChatFallback.find_hermes_pane() if tmux_available else None

    return {
        "available": cli_available,
        "cli_available": cli_available,
        "direct_import": direct_import,
        "tmux_available": tmux_available,
        "tmux_pane_found": tmux_pane is not None,
        "tmux_pane_id": tmux_pane,
    }
