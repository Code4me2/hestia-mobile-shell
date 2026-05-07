import json
from pathlib import Path

from hestia_mobile_shell.demo import load_demo_events


def test_load_demo_events_reads_jsonl_objects(tmp_path: Path):
    demo = tmp_path / "events.jsonl"
    demo.write_text(
        '{"type":"assistant.state","state":"listening"}\n'
        '\n'
        '{"type":"assistant.transcript.assistant_delta","text":"hello"}\n'
    )

    assert load_demo_events(demo) == [
        {"type": "assistant.state", "state": "listening"},
        {"type": "assistant.transcript.assistant_delta", "text": "hello"},
    ]


def test_load_demo_events_rejects_non_object_json(tmp_path: Path):
    demo = tmp_path / "bad.jsonl"
    demo.write_text('["not", "object"]\n')

    try:
        load_demo_events(demo)
    except ValueError as exc:
        assert "line 1" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_demo_fixture_is_valid_jsonl():
    fixture = Path("examples/demo-events.jsonl")

    events = load_demo_events(fixture)

    assert events[0] == {"type": "assistant.state", "state": "listening"}
    assert any(event.get("type") == "assistant.tool_call" for event in events)
    assert all(isinstance(event, dict) for event in events)
