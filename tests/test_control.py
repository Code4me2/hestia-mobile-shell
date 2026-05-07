from __future__ import annotations

import json
import socket
import threading
from pathlib import Path

import pytest

from hestia_mobile_shell.control import build_event, main, send_event


def test_build_show_card_event_with_optional_fields():
    event = build_event(
        [
            "show-card",
            "--id",
            "next-event",
            "--title",
            "Next event",
            "--body",
            "11:30 — Design review",
            "--priority",
            "60",
        ]
    )

    assert event == {
        "type": "hestia_mobile.show_card",
        "id": "next-event",
        "title": "Next event",
        "body": "11:30 — Design review",
        "priority": 60,
    }


def test_build_update_card_event_keeps_only_supplied_fields():
    event = build_event(["update-card", "--id", "next-event", "--body", "Updated"])

    assert event == {
        "type": "hestia_mobile.update_card",
        "id": "next-event",
        "body": "Updated",
    }


def test_build_dismiss_card_event_can_clear_all_cards():
    assert build_event(["dismiss-card"]) == {"type": "hestia_mobile.dismiss_card"}


def test_build_dismiss_card_event_can_target_card():
    assert build_event(["dismiss-card", "--id", "next-event"]) == {
        "type": "hestia_mobile.dismiss_card",
        "id": "next-event",
    }


def test_build_show_confirmation_event():
    event = build_event(
        [
            "show-confirmation",
            "--id",
            "send-note",
            "--title",
            "Send note?",
            "--body",
            "This will send the note.",
            "--confirm-label",
            "Send",
            "--cancel-label",
            "Not now",
        ]
    )

    assert event == {
        "type": "hestia_mobile.show_confirmation",
        "id": "send-note",
        "title": "Send note?",
        "body": "This will send the note.",
        "confirm_label": "Send",
        "cancel_label": "Not now",
    }


def test_build_tool_status_event():
    event = build_event(
        [
            "tool-status",
            "--name",
            "calendar",
            "--status",
            "running",
            "--body",
            "Checking schedule",
        ]
    )

    assert event == {
        "type": "hestia_mobile.show_tool_status",
        "name": "calendar",
        "status": "running",
        "body": "Checking schedule",
    }


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ("listening", {"type": "assistant.state", "state": "listening"}),
        ("thinking", {"type": "assistant.state", "state": "thinking"}),
        ("speaking", {"type": "assistant.state", "state": "speaking"}),
        ("idle", {"type": "assistant.state", "state": "idle"}),
        ("offline", {"type": "assistant.state", "state": "offline"}),
        ("error", {"type": "assistant.state", "state": "error"}),
    ],
)
def test_build_state_event(state, expected):
    assert build_event(["state", state]) == expected


def test_build_call_active_and_inactive_events():
    assert build_event(["call-active"]) == {
        "type": "assistant.availability",
        "available": False,
        "reason": "phone_call_active",
    }
    assert build_event(["call-inactive"]) == {
        "type": "assistant.availability",
        "available": True,
        "reason": "phone_call_inactive",
    }


def test_build_app_interface_events():
    assert build_event(["open-apps"]) == {"type": "hestia_mobile.open_app_interface"}
    assert build_event(["close-apps"]) == {"type": "hestia_mobile.close_app_interface"}


def test_build_debug_and_chat_events():
    assert build_event(["toggle-debug"]) == {"type": "hestia_mobile.toggle_debug"}
    assert build_event(["set-debug", "on"]) == {"type": "hestia_mobile.set_debug", "visible": True}
    assert build_event(["set-debug", "off"]) == {"type": "hestia_mobile.set_debug", "visible": False}
    assert build_event(["clear-events"]) == {"type": "hestia_mobile.clear_event_journal"}
    assert build_event(["open-chat"]) == {"type": "hestia_mobile.open_chat"}
    assert build_event(["close-chat"]) == {"type": "hestia_mobile.close_chat"}
    assert build_event(["text", "hello shell"]) == {"type": "hestia_mobile.submit_text", "text": "hello shell"}


def test_build_raw_json_event():
    assert build_event(["raw", '{"type":"hestia_mobile.show_card","id":"raw","title":"Raw"}']) == {
        "type": "hestia_mobile.show_card",
        "id": "raw",
        "title": "Raw",
    }


def test_build_raw_json_requires_object():
    with pytest.raises(SystemExit):
        build_event(["raw", '["not", "an", "object"]'])


def test_send_event_writes_one_ndjson_frame(tmp_path: Path):
    socket_path = tmp_path / "assistant.sock"
    captured: list[dict[str, object]] = []
    ready = threading.Event()

    def server() -> None:
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        listener.bind(str(socket_path))
        listener.listen(1)
        ready.set()
        conn, _addr = listener.accept()
        with conn:
            payload = conn.recv(4096)
            captured.append(json.loads(payload.decode("utf-8")))
        listener.close()

    thread = threading.Thread(target=server, daemon=True)
    thread.start()
    assert ready.wait(timeout=1)

    event = {"type": "assistant.state", "state": "listening"}
    send_event(socket_path, event)
    thread.join(timeout=1)

    assert captured == [event]


def test_main_sends_built_event_to_socket(tmp_path: Path):
    socket_path = tmp_path / "assistant.sock"
    captured: list[dict[str, object]] = []
    ready = threading.Event()

    def server() -> None:
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        listener.bind(str(socket_path))
        listener.listen(1)
        ready.set()
        conn, _addr = listener.accept()
        with conn:
            payload = conn.recv(4096)
            captured.append(json.loads(payload.decode("utf-8")))
        listener.close()

    thread = threading.Thread(target=server, daemon=True)
    thread.start()
    assert ready.wait(timeout=1)

    exit_code = main(["--socket", str(socket_path), "state", "thinking"])
    thread.join(timeout=1)

    assert exit_code == 0
    assert captured == [{"type": "assistant.state", "state": "thinking"}]
