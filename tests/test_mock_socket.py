from __future__ import annotations

import socket
from pathlib import Path

from hestia_mobile_shell.assistant_socket import AssistantSocketClient
from hestia_mobile_shell.mock_socket import MockAssistantSocketServer, encode_event


def test_encode_event_returns_ndjson_bytes():
    assert encode_event({"type": "assistant.state", "state": "listening"}) == (
        b'{"type":"assistant.state","state":"listening"}\n'
    )


def test_mock_server_streams_events_after_subscribe(tmp_path: Path):
    socket_path = tmp_path / "assistant.sock"
    events = [
        {"type": "assistant.state", "state": "listening"},
        {"type": "assistant.transcript.assistant_delta", "text": "hello"},
    ]

    with MockAssistantSocketServer(socket_path, events, interval_seconds=0) as server:
        received = []
        for event in AssistantSocketClient(str(socket_path)).iter_events():
            received.append(event)
            if len(received) == len(events):
                break

    assert received == events
    assert server.subscribe_messages == [{"type": "subscribe"}]


def test_mock_server_replaces_stale_socket_file(tmp_path: Path):
    socket_path = tmp_path / "assistant.sock"
    stale = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        stale.bind(str(socket_path))
    finally:
        stale.close()

    with MockAssistantSocketServer(socket_path, [], interval_seconds=0):
        assert socket_path.exists()
        assert socket_path.stat().st_mode & 0o170000 == 0o140000

    assert not socket_path.exists()


def test_mock_server_refuses_to_replace_regular_file_by_default(tmp_path: Path):
    socket_path = tmp_path / "assistant.sock"
    socket_path.write_text("not a socket")

    try:
        MockAssistantSocketServer(socket_path, [], interval_seconds=0).start()
    except FileExistsError:
        pass
    else:
        raise AssertionError("expected FileExistsError")

    assert socket_path.read_text() == "not a socket"


def test_mock_server_rejects_existing_path_when_replacement_disabled(tmp_path: Path):
    socket_path = tmp_path / "assistant.sock"
    stale = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        stale.bind(str(socket_path))
    finally:
        stale.close()

    try:
        MockAssistantSocketServer(socket_path, [], interval_seconds=0, replace_stale=False).start()
    except FileExistsError:
        pass
    else:
        raise AssertionError("expected FileExistsError")


def test_mock_server_refuses_to_replace_live_socket(tmp_path: Path):
    socket_path = tmp_path / "assistant.sock"
    live = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    live.bind(str(socket_path))
    live.listen(1)
    try:
        try:
            MockAssistantSocketServer(socket_path, [], interval_seconds=0).start()
        except FileExistsError:
            pass
        else:
            raise AssertionError("expected FileExistsError")
    finally:
        live.close()


def test_mock_server_does_not_stream_without_subscribe(tmp_path: Path):
    socket_path = tmp_path / "assistant.sock"
    event = {"type": "assistant.state", "state": "speaking"}

    with MockAssistantSocketServer(socket_path, [event], interval_seconds=0):
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            client.settimeout(0.2)
            client.connect(str(socket_path))
            try:
                payload = client.recv(4096)
            except socket.timeout:
                payload = b""
        finally:
            client.close()

    assert payload == b""


def test_mock_server_accepts_raw_socket_client_after_subscribe(tmp_path: Path):
    socket_path = tmp_path / "assistant.sock"
    event = {"type": "assistant.state", "state": "speaking"}

    with MockAssistantSocketServer(socket_path, [event], interval_seconds=0):
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            client.connect(str(socket_path))
            client.sendall(b'{"type":"subscribe"}\n')
            payload = client.recv(4096)
        finally:
            client.close()

    assert payload == encode_event(event)


def test_stop_does_not_unlink_replaced_path(tmp_path: Path):
    socket_path = tmp_path / "assistant.sock"
    server = MockAssistantSocketServer(socket_path, [], interval_seconds=0).start()
    server_socket_inode = socket_path.stat().st_ino
    socket_path.unlink()
    socket_path.write_text("replacement")

    server.stop()

    assert socket_path.read_text() == "replacement"
    assert socket_path.stat().st_ino != server_socket_inode
