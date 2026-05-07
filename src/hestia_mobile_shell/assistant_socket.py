from __future__ import annotations

import json
import socket
from typing import Callable, Iterator, Mapping, Protocol


class SocketLike(Protocol):
    def connect(self, path: str) -> None: ...

    def sendall(self, payload: bytes) -> None: ...

    def recv(self, size: int) -> bytes: ...

    def close(self) -> None: ...


SocketFactory = Callable[[], SocketLike]


def parse_ndjson_events(buffer: bytes) -> tuple[list[dict[str, object]], bytes]:
    """Parse complete newline-delimited JSON object frames from *buffer*.

    Malformed frames and non-object JSON values are ignored. Incomplete trailing
    bytes are returned as the remainder for the next socket read.
    """

    events: list[dict[str, object]] = []
    while b"\n" in buffer:
        raw, buffer = buffer.split(b"\n", 1)
        if not raw.strip():
            continue
        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if isinstance(decoded, dict):
            events.append(decoded)
    return events, buffer


class AssistantSocketClient:
    """Small blocking assistant-socket reader independent from GTK."""

    def __init__(
        self,
        socket_path: str,
        socket_factory: SocketFactory | None = None,
        recv_size: int = 4096,
    ) -> None:
        self.socket_path = socket_path
        self.socket_factory = socket_factory or _unix_socket
        self.recv_size = recv_size

    def iter_events(self) -> Iterator[dict[str, object]]:
        client = self.socket_factory()
        try:
            client.connect(self.socket_path)
            client.sendall(b'{"type":"subscribe"}\n')
            buffer = b""
            while True:
                chunk = client.recv(self.recv_size)
                if not chunk:
                    yield _offline_event()
                    return
                events, buffer = parse_ndjson_events(buffer + chunk)
                yield from events
        except OSError:
            yield _offline_event()
        finally:
            try:
                client.close()
            except OSError:
                pass


def _unix_socket() -> socket.socket:
    return socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)


def _offline_event() -> dict[str, object]:
    return {"type": "assistant.state", "state": "offline"}
