from __future__ import annotations

import json
import socket
import threading
from pathlib import Path

import pytest

from hestia_mobile_shell.agent_adapter import (
    AgentPhoneAdapter,
    CapabilityError,
    UnsupportedVerbError,
    validate_capabilities,
)


ALLOWED_VERBS = [
    "show_card",
    "update_card",
    "dismiss_card",
    "show_confirmation",
    "show_tool_status",
    "open_chat",
    "close_chat",
    "open_app_interface",
    "close_app_interface",
]


def _capabilities(socket_path: Path | str = "/tmp/assistant.sock") -> dict[str, object]:
    return {
        "interface": "hestia-mobile-agent-phone-interface",
        "version": 1,
        "transport": "local-only",
        "sockets": {"assistant": str(socket_path), "ai": "/tmp/ai.sock"},
        "http": {
            "health": "http://127.0.0.1:8765/health",
            "desktop_state": "http://127.0.0.1:8765/desktop_state",
            "mobile_capabilities": "http://127.0.0.1:8765/mobile_capabilities",
        },
        "visual_verbs": list(ALLOWED_VERBS),
        "protected_modes": ["phone_call_active", "offline", "error"],
    }


def test_validate_capabilities_accepts_local_contract(tmp_path: Path):
    capabilities = _capabilities(tmp_path / "assistant.sock")

    validated = validate_capabilities(capabilities)

    assert validated.assistant_socket == tmp_path / "assistant.sock"
    assert validated.visual_verbs == set(ALLOWED_VERBS)
    assert validated.version == 1


@pytest.mark.parametrize(
    "mutator, expected",
    [
        (lambda caps: caps.update({"interface": "other"}), "interface"),
        (lambda caps: caps.update({"transport": "remote"}), "local-only"),
        (lambda caps: caps["http"].update({"mobile_capabilities": "http://tiny-emerson:8765/mobile_capabilities"}), "loopback"),
        (lambda caps: caps["sockets"].pop("assistant"), "assistant"),
    ],
)
def test_validate_capabilities_rejects_unsafe_or_incomplete_contract(mutator, expected):
    capabilities = _capabilities()
    mutator(capabilities)

    with pytest.raises(CapabilityError, match=expected):
        validate_capabilities(capabilities)


def test_adapter_refuses_unsupported_visual_verb(tmp_path: Path):
    capabilities = _capabilities(tmp_path / "assistant.sock")
    capabilities["visual_verbs"] = ["show_card"]
    adapter = AgentPhoneAdapter.from_capabilities(capabilities)

    with pytest.raises(UnsupportedVerbError, match="open_chat"):
        adapter.open_chat()


def test_adapter_rejects_event_type_that_does_not_match_verb(tmp_path: Path):
    adapter = AgentPhoneAdapter.from_capabilities(_capabilities(tmp_path / "assistant.sock"))

    with pytest.raises(UnsupportedVerbError, match="show_card"):
        adapter.send_event("show_card", {"type": "assistant.availability", "available": True})


def test_from_capabilities_url_rejects_non_loopback_url_even_with_custom_fetcher():
    with pytest.raises(CapabilityError, match="loopback"):
        AgentPhoneAdapter.from_capabilities_url("http://tiny-emerson:8765/mobile_capabilities", fetcher=lambda url: _capabilities())


def test_adapter_sends_allowed_show_card_frame_to_assistant_socket(tmp_path: Path):
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

    adapter = AgentPhoneAdapter.from_capabilities(_capabilities(socket_path))
    adapter.show_card(id="agent-demo", title="Agent control works", body="Sent by adapter", priority=70)
    thread.join(timeout=1)

    assert captured == [
        {
            "type": "hestia_mobile.show_card",
            "id": "agent-demo",
            "title": "Agent control works",
            "body": "Sent by adapter",
            "priority": 70,
        }
    ]


def test_adapter_fetches_capabilities_before_sending(tmp_path: Path):
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
            captured.append(json.loads(conn.recv(4096).decode("utf-8")))
        listener.close()

    thread = threading.Thread(target=server, daemon=True)
    thread.start()
    assert ready.wait(timeout=1)

    adapter = AgentPhoneAdapter.from_capabilities_url(
        "http://127.0.0.1:8765/mobile_capabilities",
        fetcher=lambda url: _capabilities(socket_path),
    )
    assert adapter.capabilities_url == "http://127.0.0.1:8765/mobile_capabilities"

    adapter.open_app_interface()
    thread.join(timeout=1)

    assert captured == [{"type": "hestia_mobile.open_app_interface"}]
