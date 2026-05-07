from pathlib import Path


def test_agent_phone_interface_contract_documents_safe_local_capabilities():
    contract = Path("docs/contracts/agent-phone-interface.md").read_text()

    assert "assistant.sock" in contract
    assert "ai.sock" in contract
    assert "local-only" in contract
    assert "Do not expose" in contract
    for verb in [
        "show_card",
        "update_card",
        "dismiss_card",
        "show_confirmation",
        "show_tool_status",
        "open_chat",
        "close_chat",
        "open_app_interface",
        "close_app_interface",
    ]:
        assert verb in contract
    for protected_mode in ["phone_call_active", "offline", "error"]:
        assert protected_mode in contract
