from __future__ import annotations

import json
import socket
import threading
from pathlib import Path

import pytest

from hestia_mobile_shell.agent_adapter import (
    AgentPhoneAdapter,
    CapabilityError,
    ProtectedModeError,
    StateError,
    UnsupportedVerbError,
    fetch_capabilities,
    fetch_mobile_state,
    validate_capabilities,
    validate_mobile_state,
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
            "mobile_state": "http://127.0.0.1:8765/mobile_state",
        },
        "visual_verbs": list(ALLOWED_VERBS),
        "protected_modes": ["phone_call_active", "offline", "error"],
    }


def _mobile_state(*, protected_mode: str | None = None) -> dict[str, object]:
    return {
        "interface": "hestia-mobile-agent-phone-interface",
        "version": 1,
        "assistant_state": "idle" if protected_mode is None else protected_mode,
        "protected_mode": protected_mode,
        "protected": protected_mode is not None,
        "call_active": protected_mode == "phone_call_active",
        "online": protected_mode not in {"offline", "error"},
        "chat_open": False,
        "app_interface_open": False,
        "visible_cards": [],
        "safe_actions": list(ALLOWED_VERBS) if protected_mode is None else ["dismiss_card", "close_chat", "close_app_interface"],
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
        (lambda caps: caps["http"].pop("mobile_state"), "mobile_state"),
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
    adapter = AgentPhoneAdapter.from_capabilities(capabilities, state_fetcher=lambda url: _mobile_state())

    with pytest.raises(UnsupportedVerbError, match="open_chat"):
        adapter.open_chat()


def test_adapter_rejects_event_type_that_does_not_match_verb(tmp_path: Path):
    adapter = AgentPhoneAdapter.from_capabilities(_capabilities(tmp_path / "assistant.sock"), state_fetcher=lambda url: _mobile_state())

    with pytest.raises(UnsupportedVerbError, match="show_card"):
        adapter.send_event("show_card", {"type": "assistant.availability", "available": True})


def test_adapter_fails_closed_without_mobile_state_fetcher(tmp_path: Path):
    adapter = AgentPhoneAdapter.from_capabilities(_capabilities(tmp_path / "assistant.sock"))

    with pytest.raises(StateError, match="mobile_state"):
        adapter.open_chat()


def test_fetch_helpers_include_bearer_token(monkeypatch):
    requests = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def read(self):
            return b'{"interface":"hestia-mobile-agent-phone-interface","version":1,"protected":false,"safe_actions":[]}'

    def fake_urlopen(request, timeout):
        requests.append(request)
        return Response()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    token_value = "unit-test-bearer"
    fetch_capabilities("http://127.0.0.1:8765/mobile_capabilities", token=token_value)
    fetch_mobile_state("http://127.0.0.1:8765/mobile_state", token=token_value)

    assert [request.get_header("Authorization") for request in requests] == [f"Bearer {token_value}", f"Bearer {token_value}"]


def test_from_capabilities_url_passes_bridge_token_to_default_fetchers(monkeypatch):
    observed = []

    def fake_fetch_capabilities(url, *, token=None):
        observed.append(("capabilities", url, token))
        return _capabilities()

    def fake_fetch_mobile_state(url, *, token=None):
        observed.append(("state", url, token))
        return _mobile_state()

    monkeypatch.setattr("hestia_mobile_shell.agent_adapter.fetch_capabilities", fake_fetch_capabilities)
    monkeypatch.setattr("hestia_mobile_shell.agent_adapter.fetch_mobile_state", fake_fetch_mobile_state)

    token_value = "unit-test-bearer"
    adapter = AgentPhoneAdapter.from_capabilities_url("http://127.0.0.1:8765/mobile_capabilities", bridge_token=token_value)
    assert observed == [("capabilities", "http://127.0.0.1:8765/mobile_capabilities", token_value)]

    with pytest.raises(OSError):
        adapter.open_chat()
    assert observed[-1] == ("state", "http://127.0.0.1:8765/mobile_state", token_value)


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

    adapter = AgentPhoneAdapter.from_capabilities(_capabilities(socket_path), state_fetcher=lambda url: _mobile_state())
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


def test_validate_mobile_state_accepts_safe_loopback_contract():
    state = validate_mobile_state(_mobile_state())

    assert state.protected is False
    assert state.protected_mode is None
    assert state.safe_actions == set(ALLOWED_VERBS)


def test_validate_mobile_state_rejects_non_contract_payload():
    state = _mobile_state()
    state["interface"] = "other"

    with pytest.raises(StateError, match="interface"):
        validate_mobile_state(state)


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
        state_fetcher=lambda url: _mobile_state(),
    )
    assert adapter.capabilities_url == "http://127.0.0.1:8765/mobile_capabilities"

    adapter.open_app_interface()
    thread.join(timeout=1)

    assert captured == [{"type": "hestia_mobile.open_app_interface"}]


def test_adapter_gates_optional_visual_actions_during_protected_mode(tmp_path: Path):
    adapter = AgentPhoneAdapter.from_capabilities_url(
        "http://127.0.0.1:8765/mobile_capabilities",
        fetcher=lambda url: _capabilities(tmp_path / "assistant.sock"),
        state_fetcher=lambda url: _mobile_state(protected_mode="phone_call_active"),
    )

    with pytest.raises(ProtectedModeError, match="phone_call_active"):
        adapter.show_card(id="blocked", title="Blocked")


def test_adapter_allows_safe_close_actions_during_protected_mode(tmp_path: Path):
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
        state_fetcher=lambda url: _mobile_state(protected_mode="offline"),
    )
    adapter.close_chat()
    thread.join(timeout=1)

    assert captured == [{"type": "hestia_mobile.close_chat"}]
