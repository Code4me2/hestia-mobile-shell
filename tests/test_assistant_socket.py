from hestia_mobile_shell.assistant_socket import AssistantSocketClient, parse_ndjson_events


def test_parse_ndjson_events_returns_events_and_remainder():
    events, remainder = parse_ndjson_events(
        b'{"type":"assistant.state","state":"listening"}\n'
        b'{"type":"assistant.transcript.assistant_delta","text":"hi"}\n'
        b'{"type":"assistant.state"'
    )

    assert events == [
        {"type": "assistant.state", "state": "listening"},
        {"type": "assistant.transcript.assistant_delta", "text": "hi"},
    ]
    assert remainder == b'{"type":"assistant.state"'


def test_parse_ndjson_events_ignores_malformed_and_non_object_frames():
    events, remainder = parse_ndjson_events(
        b'not-json\n'
        b'["not", "object"]\n'
        b'{"type":"assistant.state","state":"speaking"}\n'
    )

    assert events == [{"type": "assistant.state", "state": "speaking"}]
    assert remainder == b""


def test_client_emits_subscribe_frame_on_connect():
    sent = []

    class FakeSocket:
        def connect(self, path):
            assert path == "/tmp/assistant.sock"

        def sendall(self, payload):
            sent.append(payload)

        def recv(self, size):
            return b""

        def close(self):
            pass

    client = AssistantSocketClient("/tmp/assistant.sock", socket_factory=lambda: FakeSocket())

    list(client.iter_events())

    assert sent == [b'{"type":"subscribe"}\n']


def test_client_yields_events_until_socket_closes_then_offline():
    chunks = [
        b'{"type":"assistant.state","state":"thinking"}\n',
        b'{"type":"assistant.transcript.assistant_delta","text":"found it"}\n',
        b"",
    ]

    class FakeSocket:
        def connect(self, path):
            pass

        def sendall(self, payload):
            pass

        def recv(self, size):
            return chunks.pop(0)

        def close(self):
            pass

    client = AssistantSocketClient("/tmp/assistant.sock", socket_factory=lambda: FakeSocket())

    assert list(client.iter_events()) == [
        {"type": "assistant.state", "state": "thinking"},
        {"type": "assistant.transcript.assistant_delta", "text": "found it"},
        {"type": "assistant.state", "state": "offline"},
    ]


def test_client_yields_offline_when_connect_fails():
    class FakeSocket:
        def connect(self, path):
            raise OSError("missing")

        def close(self):
            pass

    client = AssistantSocketClient("/tmp/missing.sock", socket_factory=lambda: FakeSocket())

    assert list(client.iter_events()) == [{"type": "assistant.state", "state": "offline"}]
