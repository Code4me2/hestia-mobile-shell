from __future__ import annotations

import json
import os
import socket
from pathlib import Path
from typing import Iterator, Mapping, Optional


def default_ai_socket() -> Path:
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    return Path(runtime_dir) / "hestia-shell" / "ai.sock"


def build_chat_request(
    text: str,
    *,
    model: str = "default",
    extra_context: Optional[Mapping[str, object]] = None,
) -> dict[str, object]:
    request: dict[str, object] = {
        "type": "chat",
        "model": model,
        "messages": [{"role": "user", "content": text}],
    }
    if extra_context:
        request["extra_context"] = dict(extra_context)
    return request


def frame_to_assistant_event(frame: Mapping[str, object]) -> Optional[dict[str, object]]:
    frame_type = str(frame.get("type") or "")
    if frame_type == "token":
        return {
            "type": "assistant.transcript.assistant_delta",
            "text": str(frame.get("content") or ""),
        }
    if frame_type == "tool_call":
        return {
            "type": "assistant.tool_call",
            "name": str(frame.get("name") or "tool"),
            "status": "running",
        }
    if frame_type == "tool_result":
        return {
            "type": "assistant.tool_result",
            "name": str(frame.get("name") or ""),
        }
    if frame_type == "done":
        return {"type": "assistant.state", "state": "idle"}
    if frame_type == "error":
        return {
            "type": "assistant.state",
            "state": "error",
            "message": str(frame.get("message") or "error"),
        }
    return None


class AIChatClient:
    def __init__(self, socket_path: str | Path, *, model: str = "default", timeout: float = 30.0):
        self.socket_path = Path(socket_path)
        self.model = model
        self.timeout = timeout

    def iter_chat_events(self, text: str) -> Iterator[dict[str, object]]:
        request = build_chat_request(
            text,
            model=self.model,
            extra_context={"source": "hestia-mobile-shell", "input_mode": "typed_fallback"},
        )
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(self.timeout)
            sock.connect(str(self.socket_path))
            sock.sendall(json.dumps(request, separators=(",", ":")).encode("utf-8") + b"\n")

            buffer = ""
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                buffer += chunk.decode("utf-8", errors="replace")
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        frame = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(frame, dict):
                        continue
                    event = frame_to_assistant_event(frame)
                    if event is not None:
                        yield event
                    if frame.get("type") in {"done", "error"}:
                        return
