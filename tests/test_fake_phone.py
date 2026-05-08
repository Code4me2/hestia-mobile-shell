from __future__ import annotations

import json
import urllib.request
from pathlib import Path

from hestia_mobile_shell.agent_adapter import AgentPhoneAdapter
from hestia_mobile_shell.fake_phone import FakePhoneHarness


def test_fake_phone_harness_serves_capabilities_state_and_captures_adapter_events(tmp_path: Path):
    with FakePhoneHarness(tmp_path) as phone:
        capabilities = json.loads(urllib.request.urlopen(phone.capabilities_url, timeout=2).read().decode("utf-8"))
        state = json.loads(urllib.request.urlopen(phone.state_url, timeout=2).read().decode("utf-8"))

        assert capabilities["http"]["mobile_state"] == phone.state_url
        assert capabilities["sockets"]["assistant"] == str(phone.assistant_socket)
        assert state["protected"] is False

        adapter = AgentPhoneAdapter.from_capabilities_url(
            phone.capabilities_url,
            state_fetcher=lambda url: json.loads(urllib.request.urlopen(url, timeout=2).read().decode("utf-8")),
        )
        adapter.show_card(id="fake-phone", title="Harness works")

        assert phone.wait_for_event(timeout=1) == {
            "type": "hestia_mobile.show_card",
            "id": "fake-phone",
            "title": "Harness works",
        }


def test_fake_phone_harness_can_enter_protected_mode(tmp_path: Path):
    with FakePhoneHarness(tmp_path, protected_mode="phone_call_active") as phone:
        state = json.loads(urllib.request.urlopen(phone.state_url, timeout=2).read().decode("utf-8"))

    assert state["protected"] is True
    assert state["protected_mode"] == "phone_call_active"
    assert state["safe_actions"] == ["dismiss_card", "close_chat", "close_app_interface"]
