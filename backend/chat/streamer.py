"""SSE streaming handler — AI SDK Data Stream Protocol v1."""

from __future__ import annotations

import json
import queue
import threading
from typing import Any, Iterator

from .models import StreamingEvent, ToolCall, ToolStatus


_HEARTBEAT_INTERVAL_S = 15  # Keep SSE alive past proxy idle timeouts


class ChatStreamer:
    """Manages SSE streaming for a single chat session."""

    def __init__(self):
        self._queue: queue.Queue[StreamingEvent | None] = queue.Queue()
        self._stopped = threading.Event()
        self._current_message: str = ""
        self._current_tools: dict[str, ToolCall] = {}
        self._text_started: bool = False

    def emit(self, event: StreamingEvent) -> None:
        """Queue an event for streaming."""
        if not self._stopped.is_set():
            self._queue.put(event)

    def _close_text_block(self) -> None:
        """Emit text-end if a text block is currently open."""
        if self._text_started:
            self._text_started = False
            self.emit(StreamingEvent(type="text-end", data={"id": "t0"}))

    def emit_token(self, token: str) -> None:
        """Emit a text token."""
        self._current_message += token
        if not self._text_started:
            self._text_started = True
            self.emit(StreamingEvent(type="text-start", data={"id": "t0"}))
        self.emit(StreamingEvent(type="text-delta", data={"id": "t0", "delta": token}))

    def emit_tool_start(self, tool_id: str, name: str, arguments: dict) -> None:
        """Emit tool call start."""
        self._close_text_block()
        tool = ToolCall(id=tool_id, name=name, arguments=arguments)
        self._current_tools[tool_id] = tool
        self.emit(StreamingEvent(
            type="tool-input-start",
            data={"toolCallId": tool_id, "toolName": name},
        ))
        self.emit(StreamingEvent(
            type="tool-input-available",
            data={"toolCallId": tool_id, "toolName": name, "input": arguments},
        ))

    def emit_tool_end(
        self, tool_id: str, result: Any = None, error: str | None = None
    ) -> None:
        """Emit tool call completion."""
        if tool_id in self._current_tools:
            tool = self._current_tools[tool_id]
            tool.status = ToolStatus.ERROR if error else ToolStatus.COMPLETE
            tool.result = result
            tool.error = error
        output = {"error": error} if error else result
        self.emit(StreamingEvent(
            type="tool-output-available",
            data={"toolCallId": tool_id, "output": output},
        ))

    def emit_reasoning(self, content: str) -> None:
        """Emit reasoning/thinking content."""
        self._close_text_block()
        self.emit(StreamingEvent(type="reasoning-start", data={"id": "r0"}))
        self.emit(StreamingEvent(type="reasoning-delta", data={"id": "r0", "delta": content}))
        self.emit(StreamingEvent(type="reasoning-end", data={"id": "r0"}))

    def emit_done(self) -> None:
        """Signal completion."""
        self._close_text_block()
        self.emit(StreamingEvent(type="finish", data={"finishReason": "stop"}))
        self._queue.put(None)  # Sentinel to stop iteration

    def emit_error(self, error: str) -> None:
        """Emit error event."""
        self._close_text_block()
        self.emit(StreamingEvent(type="error", data={"errorText": error}))
        self._queue.put(None)

    def stop(self) -> None:
        """Stop the stream."""
        self._stopped.set()
        self._queue.put(None)

    def iter_events(self) -> Iterator[StreamingEvent]:
        """Iterate over events for SSE."""
        while not self._stopped.is_set():
            try:
                event = self._queue.get(timeout=_HEARTBEAT_INTERVAL_S)
            except queue.Empty:
                # Yield a heartbeat comment to keep the connection alive
                yield StreamingEvent(type="heartbeat", data={})
                continue
            if event is None:
                break
            yield event

    def to_sse(self, event: StreamingEvent) -> str:
        """Convert event to AI SDK Data Stream Protocol v1 SSE format."""
        if event.type == "heartbeat":
            return ": heartbeat\n\n"
        payload = {"type": event.type, **event.data}
        return f"data: {json.dumps(payload)}\n\n"
