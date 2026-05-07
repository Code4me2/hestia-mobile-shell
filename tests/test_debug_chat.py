from hestia_mobile_shell.state import MobileShellState, reduce_assistant_event, state_debug_lines


def test_assistant_response_material_replaces_last_typed_user_message():
    state = reduce_assistant_event(MobileShellState.initial(), {"type": "hestia_mobile.submit_text", "text": "hello"})
    state = reduce_assistant_event(state, {"type": "assistant.transcript.assistant_delta", "text": "Hi there"})

    assert state.primary_material is not None
    assert state.primary_material.id == "transcript"
    assert state.current_material == "Hi there"


def test_empty_tool_result_clears_current_tool_status_material_from_bridge():
    state = reduce_assistant_event(MobileShellState.initial(), {"type": "assistant.tool_call", "name": "calendar"})
    state = reduce_assistant_event(state, {"type": "assistant.tool_result", "name": ""})

    assert state.tool_status is None
    assert all(material.kind != "tool_status" for material in state.materials)
    assert state.current_material is None


def test_tool_result_clears_tool_status_material():
    state = reduce_assistant_event(MobileShellState.initial(), {"type": "assistant.tool_call", "name": "calendar"})
    state = reduce_assistant_event(state, {"type": "assistant.tool_result", "name": "calendar"})

    assert state.tool_status is None
    assert all(material.id != "tool:calendar" for material in state.materials)
    assert state.current_material is None


def test_chat_error_state_uses_event_message_for_status():
    state = reduce_assistant_event(
        MobileShellState.initial(),
        {"type": "assistant.state", "state": "error", "message": "chat socket unavailable"},
    )

    assert state.mode == "error"
    assert state.status_text == "chat socket unavailable"


def test_event_journal_records_recent_event_summaries_and_caps_length():
    state = MobileShellState.initial()

    for index in range(14):
        state = reduce_assistant_event(state, {"type": "assistant.state", "state": f"state-{index}"})

    assert len(state.event_journal) == 12
    assert state.event_journal[0] == "assistant.state state-2"
    assert state.event_journal[-1] == "assistant.state state-13"


def test_debug_overlay_can_be_toggled_and_cleared_with_events():
    state = MobileShellState.initial()
    state = reduce_assistant_event(state, {"type": "hestia_mobile.toggle_debug"})
    state = reduce_assistant_event(state, {"type": "assistant.state", "state": "listening"})

    assert state.debug_visible is True
    assert "assistant.state listening" in state.event_journal

    state = reduce_assistant_event(state, {"type": "hestia_mobile.clear_event_journal"})
    assert state.event_journal == ()

    state = reduce_assistant_event(state, {"type": "hestia_mobile.set_debug", "visible": False})
    assert state.debug_visible is False


def test_state_debug_lines_include_operational_snapshot():
    state = MobileShellState.initial()
    state = reduce_assistant_event(state, {"type": "hestia_mobile.show_card", "id": "card", "title": "Card"})
    state = reduce_assistant_event(state, {"type": "hestia_mobile.toggle_debug"})

    lines = state_debug_lines(state)

    assert "mode=material" in lines
    assert "assistant_state=idle" in lines
    assert "primary_material=card/card" in lines
    assert "materials=1" in lines
    assert "debug_visible=True" in lines
    assert any(line.endswith("hestia_mobile.toggle_debug") for line in lines)


def test_open_chat_sets_chat_visible_without_opening_app_interface():
    state = reduce_assistant_event(MobileShellState.initial(), {"type": "hestia_mobile.open_chat"})

    assert state.chat_visible is True
    assert state.app_interface_visible is False
    assert state.mode == "chat"

    state = reduce_assistant_event(state, {"type": "hestia_mobile.close_chat"})
    assert state.chat_visible is False
    assert state.mode == "blank"


def test_submit_text_opens_chat_and_creates_user_transcript_material():
    state = reduce_assistant_event(
        MobileShellState.initial(),
        {"type": "hestia_mobile.submit_text", "text": "What's next?"},
    )

    assert state.chat_visible is True
    assert state.assistant_state == "thinking"
    assert state.status_text == "Thinking"
    assert state.mode == "chat"
    assert state.primary_material is not None
    assert state.primary_material.id == "chat:last_user"
    assert state.primary_material.kind == "transcript"
    assert state.current_material == "You: What's next?"


def test_submit_text_is_ignored_when_blank_but_still_journaled():
    state = reduce_assistant_event(MobileShellState.initial(), {"type": "hestia_mobile.submit_text", "text": "  "})

    assert state.chat_visible is False
    assert state.materials == ()
    assert state.event_journal == ("hestia_mobile.submit_text",)


def test_chat_and_debug_do_not_escape_call_protection():
    state = MobileShellState.initial()
    state = reduce_assistant_event(state, {"type": "hestia_mobile.open_chat"})
    state = reduce_assistant_event(state, {"type": "hestia_mobile.toggle_debug"})
    state = reduce_assistant_event(
        state,
        {"type": "assistant.availability", "available": False, "reason": "phone_call_active"},
    )

    assert state.mode == "call_paused"
    assert state.chat_visible is True
    assert state.debug_visible is True
    assert state.current_material is None

    state = reduce_assistant_event(
        state,
        {"type": "assistant.availability", "available": True, "reason": "phone_call_inactive"},
    )
    assert state.mode == "chat"
