from __future__ import annotations

import json
import socket
import threading
from pathlib import Path

from hestia_mobile_shell.ai_chat import AIChatClient, build_chat_request, frame_to_assistant_event


def test_build_chat_request_uses_bridge_chat_protocol():
    request = build_chat_request("hello", model="default")

    assert request == {
        "type": "chat",
        "model": "default",
        "messages": [{"role": "user", "content": "hello"}],
    }


def test_build_chat_request_preserves_extra_context():
    request = build_chat_request("hello", extra_context={"source": "mobile-shell"})

    assert request["extra_context"] == {"source": "mobile-shell"}


def test_frame_to_assistant_event_maps_token_to_assistant_delta():
    assert frame_to_assistant_event({"type": "token", "content": "hi"}) == {
        "type": "assistant.transcript.assistant_delta",
        "text": "hi",
    }


def test_frame_to_assistant_event_maps_tool_call():
    assert frame_to_assistant_event({"type": "tool_call", "name": "calendar"}) == {
        "type": "assistant.tool_call",
        "name": "calendar",
        "status": "running",
    }


def test_frame_to_assistant_event_maps_terminal_frames():
    assert frame_to_assistant_event({"type": "done"}) == {"type": "assistant.state", "state": "idle"}
    assert frame_to_assistant_event({"type": "error", "message": "offline"}) == {
        "type": "assistant.state",
        "state": "error",
        "message": "offline",
    }


def test_frame_to_assistant_event_maps_tool_result_to_clear_status():
    assert frame_to_assistant_event({"type": "tool_result", "name": "calendar"}) == {
        "type": "assistant.tool_result",
        "name": "calendar",
    }


def test_frame_to_assistant_event_preserves_empty_tool_result_name():
    assert frame_to_assistant_event({"type": "tool_result", "name": "", "result": ""}) == {
        "type": "assistant.tool_result",
        "name": "",
    }


def test_frame_to_assistant_event_ignores_unknown_frames():
    assert frame_to_assistant_event({"type": "unknown"}) is None


def test_ai_chat_client_sends_request_and_streams_normalized_events(tmp_path: Path):
    socket_path = tmp_path / "ai.sock"
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(socket_path))
    server.listen(1)
    captured_request = {}

    def serve_once() -> None:
        conn, _ = server.accept()
        with conn:
            data = b""
            while not data.endswith(b"\n"):
                chunk = conn.recv(4096)
                if not chunk:
                    break
                data += chunk
            captured_request.update(json.loads(data.decode("utf-8")))
            for frame in [
                {"type": "token", "content": "Hello"},
                {"type": "tool_call", "name": "calendar"},
                {"type": "done"},
            ]:
                conn.sendall(json.dumps(frame).encode("utf-8") + b"\n")
        server.close()

    thread = threading.Thread(target=serve_once, daemon=True)
    thread.start()

    events = list(AIChatClient(socket_path).iter_chat_events("hello"))

    thread.join(timeout=2)
    assert captured_request["type"] == "chat"
    assert captured_request["messages"] == [{"role": "user", "content": "hello"}]
    assert events == [
        {"type": "assistant.transcript.assistant_delta", "text": "Hello"},
        {"type": "assistant.tool_call", "name": "calendar", "status": "running"},
        {"type": "assistant.state", "state": "idle"},
    ]
