import subprocess
import time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]


class FakeStdout:
    def __init__(self, chunks):
        self._chunks = list(chunks)

    def read1(self, _size):
        if self._chunks:
            return self._chunks.pop(0)
        return b""


class FakeProcess:
    def __init__(self, stdout_chunks=None, stderr_lines=None, returncode=0):
        self.stdout = FakeStdout(stdout_chunks or [])
        self.stderr = iter(stderr_lines or [])
        self.returncode = returncode
        self.terminated = False
        self.killed = False

    def wait(self, timeout=None):
        return self.returncode

    def poll(self):
        return None if not (self.terminated or self.killed) else self.returncode

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True


def fresh_engine(monkeypatch):
    import backend.chat.engine as engine_module

    engine_module.ChatEngine._instance = None
    monkeypatch.setattr(engine_module.shutil, "which", lambda name: "/usr/bin/hermes")
    monkeypatch.setattr(
        engine_module.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0),
    )
    return engine_module.ChatEngine()


def collect_events(streamer, timeout=2):
    deadline = time.time() + timeout
    events = []
    for event in streamer.iter_events():
        events.append(event)
        if time.time() > deadline:
            raise TimeoutError("stream did not finish")
    return events


def test_chat_availability_reports_only_engine_capability():
    api = (ROOT / "backend/api/chat.py").read_text()
    availability_block = api.split("async def check_availability", 1)[1].split("async def check_diagnostics", 1)[0]

    assert '"available": cli_available' in availability_block
    assert "TmuxChatFallback" not in availability_block
    assert "from run_agent import AIAgent" not in availability_block


def test_chat_diagnostics_keeps_tmux_and_direct_import_detail():
    api = (ROOT / "backend/api/chat.py").read_text()
    diagnostics_block = api.split("async def check_diagnostics", 1)[1]

    assert '@router.get("/diagnostics")' in api
    assert "from run_agent import AIAgent" in diagnostics_block
    assert "TmuxChatFallback.is_available()" in diagnostics_block
    assert "TmuxChatFallback.find_hermes_pane()" in diagnostics_block
    assert '"tmux_pane_id": tmux_pane' in diagnostics_block


def test_send_message_resumes_captured_hermes_session(monkeypatch):
    engine = fresh_engine(monkeypatch)
    session = engine.create_session()
    commands = []
    processes = [
        FakeProcess(
            stdout_chunks=[b"first\n"],
            stderr_lines=[b"session_id: hermes-123\n"],
        ),
        FakeProcess(
            stdout_chunks=[b"second\n"],
            stderr_lines=[b"session_id: hermes-123\n"],
        ),
    ]

    def fake_popen(cmd, **kwargs):
        commands.append(cmd)
        return processes.pop(0)

    monkeypatch.setattr("backend.chat.engine.subprocess.Popen", fake_popen)
    monkeypatch.setattr("backend.chat.engine._emit_tool_events", lambda *args: None)

    collect_events(engine.send_message(session.id, "hello"))
    collect_events(engine.send_message(session.id, "again"))

    assert session.hermes_session_id == "hermes-123"
    assert "--resume" not in commands[0]
    assert commands[1][commands[1].index("--resume") + 1] == "hermes-123"


def test_completed_stream_is_removed_from_composer_state(monkeypatch):
    engine = fresh_engine(monkeypatch)
    session = engine.create_session(model="nous")

    monkeypatch.setattr(
        "backend.chat.engine.subprocess.Popen",
        lambda *args, **kwargs: FakeProcess(
            stdout_chunks=[b"done\n"],
            stderr_lines=[b"session_id: hermes-clean\n"],
        ),
    )
    monkeypatch.setattr("backend.chat.engine._emit_tool_events", lambda *args: None)

    collect_events(engine.send_message(session.id, "hello"))

    assert session.id not in engine._streamers
    assert engine.get_composer_state(session.id).is_streaming is False
    assert engine.get_composer_state(session.id).status == "complete"
    assert engine.get_composer_state(session.id).first_token_ms is not None
    assert engine.get_composer_state(session.id).total_ms is not None
    assert engine.get_composer_state(session.id).process_start_ms is not None
    assert engine.get_composer_state(session.id).recent_runs == 1
    assert engine.get_composer_state(session.id).recent_first_token_avg_ms is not None
    assert engine.get_composer_state(session.id).recent_total_avg_ms is not None


def test_composer_state_uses_configured_model_when_session_model_is_empty(monkeypatch, tmp_path):
    engine = fresh_engine(monkeypatch)
    session = engine.create_session()
    config = tmp_path / "config.yaml"
    config.write_text(
        "model:\n"
        "  provider: openai-codex\n"
        "  default: gpt-5.5\n",
        encoding="utf-8",
    )

    monkeypatch.setattr("backend.chat.engine.default_hermes_dir", lambda *args: str(tmp_path))

    assert engine.get_composer_state(session.id).model == "gpt-5.5"


def test_nonzero_process_without_stderr_emits_error(monkeypatch):
    engine = fresh_engine(monkeypatch)
    session = engine.create_session()

    monkeypatch.setattr(
        "backend.chat.engine.subprocess.Popen",
        lambda *args, **kwargs: FakeProcess(returncode=2),
    )

    events = collect_events(engine.send_message(session.id, "fail"))

    errors = [event for event in events if event.type == "error"]
    assert errors
    assert "exited with code 2" in errors[0].data["errorText"]
    assert engine.get_composer_state(session.id).status == "error"


def test_cancel_stream_escalates_to_kill(monkeypatch):
    engine = fresh_engine(monkeypatch)
    session = engine.create_session()

    class HangingProcess(FakeProcess):
        def poll(self):
            return None

        def wait(self, timeout=None):
            if timeout is not None and not self.killed:
                raise subprocess.TimeoutExpired("hermes", timeout)
            return self.returncode

    process = HangingProcess()
    engine._processes[session.id] = process

    class StopRecorder:
        def __init__(self):
            self.stopped = False

        def stop(self):
            self.stopped = True

    streamer = StopRecorder()
    engine._streamers[session.id] = streamer

    engine.cancel_stream(session.id)

    assert process.terminated is True
    assert process.killed is True
    assert streamer.stopped is True
    assert session.id not in engine._processes
    assert session.id not in engine._streamers
    assert engine.get_composer_state(session.id).status == "cancelled"
