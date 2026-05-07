from hestia_mobile_shell.state import MobileShellState, reduce_assistant_event


def test_show_card_creates_primary_material_card():
    state = reduce_assistant_event(
        MobileShellState.initial(),
        {
            "type": "hestia_mobile.show_card",
            "id": "weather-now",
            "title": "Weather",
            "body": "Light rain for the next hour",
            "priority": 8,
            "actions": [{"id": "open", "label": "Open forecast"}],
        },
    )

    assert state.mode == "material"
    assert len(state.materials) == 1
    card = state.primary_material
    assert card is not None
    assert card.id == "weather-now"
    assert card.kind == "card"
    assert card.title == "Weather"
    assert card.body == "Light rain for the next hour"
    assert card.priority == 8
    assert card.actions == ({"id": "open", "label": "Open forecast"},)
    assert state.current_material == "Weather\nLight rain for the next hour"


def test_show_card_replaces_existing_card_by_id():
    state = MobileShellState.initial()
    state = reduce_assistant_event(
        state,
        {"type": "hestia_mobile.show_card", "id": "timer", "title": "Timer", "body": "10 min"},
    )
    state = reduce_assistant_event(
        state,
        {"type": "hestia_mobile.show_card", "id": "timer", "title": "Timer", "body": "8 min"},
    )

    assert len(state.materials) == 1
    assert state.primary_material is not None
    assert state.primary_material.body == "8 min"


def test_update_card_preserves_missing_fields():
    state = reduce_assistant_event(
        MobileShellState.initial(),
        {"type": "hestia_mobile.show_card", "id": "route", "title": "Route", "body": "12 min"},
    )

    state = reduce_assistant_event(
        state,
        {"type": "hestia_mobile.update_card", "id": "route", "body": "14 min"},
    )

    assert state.primary_material is not None
    assert state.primary_material.title == "Route"
    assert state.primary_material.body == "14 min"


def test_update_unknown_card_creates_it():
    state = reduce_assistant_event(
        MobileShellState.initial(),
        {"type": "hestia_mobile.update_card", "id": "music", "title": "Music", "body": "Now playing"},
    )

    assert state.primary_material is not None
    assert state.primary_material.id == "music"
    assert state.primary_material.title == "Music"


def test_dismiss_card_removes_one_material_and_returns_blank_when_empty():
    state = MobileShellState.initial()
    state = reduce_assistant_event(state, {"type": "hestia_mobile.show_card", "id": "a", "title": "A"})
    state = reduce_assistant_event(state, {"type": "hestia_mobile.show_card", "id": "b", "title": "B", "priority": 10})

    state = reduce_assistant_event(state, {"type": "hestia_mobile.dismiss_card", "id": "b"})
    assert [m.id for m in state.materials] == ["a"]
    assert state.mode == "material"
    assert state.primary_material is not None
    assert state.primary_material.id == "a"

    state = reduce_assistant_event(state, {"type": "hestia_mobile.dismiss_card", "id": "a"})
    assert state.materials == ()
    assert state.mode == "blank"
    assert state.current_material is None


def test_dismiss_all_cards_clears_materials_but_preserves_app_interface():
    state = reduce_assistant_event(
        MobileShellState.initial(),
        {"type": "hestia_mobile.show_card", "id": "a", "title": "A"},
    )
    state = reduce_assistant_event(state, {"type": "hestia_mobile.open_app_interface"})

    state = reduce_assistant_event(state, {"type": "hestia_mobile.dismiss_card"})

    assert state.materials == ()
    assert state.mode == "app_interface"
    assert state.app_interface_visible is True


def test_show_confirmation_creates_confirmation_material():
    state = reduce_assistant_event(
        MobileShellState.initial(),
        {
            "type": "hestia_mobile.show_confirmation",
            "id": "send-msg",
            "title": "Send message?",
            "body": "Send to Alex",
            "confirm_label": "Send",
            "cancel_label": "Cancel",
        },
    )

    card = state.primary_material
    assert card is not None
    assert card.kind == "confirmation"
    assert card.actions == (
        {"id": "confirm", "label": "Send"},
        {"id": "cancel", "label": "Cancel"},
    )


def test_show_tool_status_creates_or_updates_tool_material():
    state = reduce_assistant_event(
        MobileShellState.initial(),
        {"type": "hestia_mobile.show_tool_status", "name": "calendar", "status": "running"},
    )
    state = reduce_assistant_event(
        state,
        {"type": "hestia_mobile.show_tool_status", "name": "calendar", "status": "done", "body": "Found 2 events"},
    )

    assert len(state.materials) == 1
    card = state.primary_material
    assert card is not None
    assert card.id == "tool:calendar"
    assert card.kind == "tool_status"
    assert card.title == "calendar"
    assert card.body == "Found 2 events"
    assert state.tool_status == "calendar: done"


def test_highest_priority_material_is_primary_then_most_recent():
    state = MobileShellState.initial()
    state = reduce_assistant_event(state, {"type": "hestia_mobile.show_card", "id": "low", "title": "Low", "priority": 1})
    state = reduce_assistant_event(state, {"type": "hestia_mobile.show_card", "id": "high", "title": "High", "priority": 9})
    state = reduce_assistant_event(state, {"type": "hestia_mobile.show_card", "id": "also-high", "title": "Later", "priority": 9})

    assert state.primary_material is not None
    assert state.primary_material.id == "also-high"


def test_dismiss_tool_status_clears_tool_status_even_with_other_materials():
    state = MobileShellState.initial()
    state = reduce_assistant_event(state, {"type": "hestia_mobile.show_card", "id": "card", "title": "Card"})
    state = reduce_assistant_event(state, {"type": "hestia_mobile.show_tool_status", "name": "calendar", "status": "running"})

    state = reduce_assistant_event(state, {"type": "hestia_mobile.dismiss_card", "id": "tool:calendar"})

    assert [m.id for m in state.materials] == ["card"]
    assert state.tool_status is None


def test_call_paused_mode_is_preserved_when_material_arrives():
    state = reduce_assistant_event(
        MobileShellState.initial(),
        {"type": "assistant.availability", "available": False, "reason": "phone_call_active"},
    )

    state = reduce_assistant_event(
        state,
        {"type": "hestia_mobile.show_card", "id": "card", "title": "Card"},
    )

    assert state.mode == "call_paused"
    assert state.assistant_state == "call_active"
    assert state.primary_material is not None
    assert state.current_material is None


def test_entering_call_paused_hides_existing_material_until_call_inactive():
    state = reduce_assistant_event(MobileShellState.initial(), {"type": "hestia_mobile.show_card", "id": "card", "title": "Card"})

    state = reduce_assistant_event(
        state,
        {"type": "assistant.availability", "available": False, "reason": "phone_call_active"},
    )

    assert state.mode == "call_paused"
    assert state.primary_material is not None
    assert state.current_material is None


def test_call_paused_retained_material_appears_after_call_inactive():
    state = reduce_assistant_event(
        MobileShellState.initial(),
        {"type": "assistant.availability", "available": False, "reason": "phone_call_active"},
    )
    state = reduce_assistant_event(state, {"type": "hestia_mobile.show_card", "id": "card", "title": "Card"})

    state = reduce_assistant_event(
        state,
        {"type": "assistant.availability", "available": True, "reason": "phone_call_inactive"},
    )

    assert state.mode == "material"
    assert state.current_material == "Card"


def test_offline_mode_is_preserved_when_material_arrives():
    state = reduce_assistant_event(MobileShellState.initial(), {"type": "assistant.state", "state": "offline"})

    state = reduce_assistant_event(state, {"type": "hestia_mobile.show_card", "id": "card", "title": "Card"})

    assert state.mode == "offline"
    assert state.primary_material is not None
    assert state.current_material is None


def test_entering_offline_mode_hides_existing_material():
    state = reduce_assistant_event(MobileShellState.initial(), {"type": "hestia_mobile.show_card", "id": "card", "title": "Card"})

    state = reduce_assistant_event(state, {"type": "assistant.state", "state": "offline"})

    assert state.mode == "offline"
    assert state.primary_material is not None
    assert state.current_material is None


def test_error_mode_is_preserved_when_material_arrives():
    state = reduce_assistant_event(MobileShellState.initial(), {"type": "assistant.state", "state": "error"})

    state = reduce_assistant_event(state, {"type": "hestia_mobile.show_card", "id": "card", "title": "Card"})

    assert state.mode == "error"
    assert state.primary_material is not None
    assert state.current_material is None


def test_entering_error_mode_hides_existing_material():
    state = reduce_assistant_event(MobileShellState.initial(), {"type": "hestia_mobile.show_card", "id": "card", "title": "Card"})

    state = reduce_assistant_event(state, {"type": "assistant.state", "state": "error"})

    assert state.mode == "error"
    assert state.primary_material is not None
    assert state.current_material is None


def test_protected_mode_overrides_open_app_interface():
    state = reduce_assistant_event(MobileShellState.initial(), {"type": "hestia_mobile.open_app_interface"})
    state = reduce_assistant_event(state, {"type": "hestia_mobile.show_card", "id": "card", "title": "Card"})

    state = reduce_assistant_event(
        state,
        {"type": "assistant.availability", "available": False, "reason": "phone_call_active"},
    )

    assert state.mode == "call_paused"
    assert state.app_interface_visible is True
    assert state.current_material is None


def test_app_interface_is_restored_after_call_inactive_if_it_was_open():
    state = reduce_assistant_event(MobileShellState.initial(), {"type": "hestia_mobile.open_app_interface"})
    state = reduce_assistant_event(state, {"type": "hestia_mobile.show_card", "id": "card", "title": "Card"})
    state = reduce_assistant_event(
        state,
        {"type": "assistant.availability", "available": False, "reason": "phone_call_active"},
    )

    state = reduce_assistant_event(
        state,
        {"type": "assistant.availability", "available": True, "reason": "phone_call_inactive"},
    )

    assert state.mode == "app_interface"
    assert state.current_material == "Card"


def test_open_app_interface_during_protected_mode_does_not_escape_protection():
    state = reduce_assistant_event(
        MobileShellState.initial(),
        {"type": "assistant.availability", "available": False, "reason": "phone_call_active"},
    )

    state = reduce_assistant_event(state, {"type": "hestia_mobile.open_app_interface"})

    assert state.mode == "call_paused"
    assert state.app_interface_visible is True
    assert state.current_material is None


def test_close_app_interface_during_protected_mode_does_not_escape_protection():
    state = reduce_assistant_event(MobileShellState.initial(), {"type": "hestia_mobile.open_app_interface"})
    state = reduce_assistant_event(
        state,
        {"type": "assistant.availability", "available": False, "reason": "phone_call_active"},
    )

    state = reduce_assistant_event(state, {"type": "hestia_mobile.close_app_interface"})

    assert state.mode == "call_paused"
    assert state.app_interface_visible is False


def test_transcript_delta_becomes_transcript_material_without_replacing_cards():
    state = reduce_assistant_event(
        MobileShellState.initial(),
        {"type": "hestia_mobile.show_card", "id": "card", "title": "Card", "priority": 5},
    )
    state = reduce_assistant_event(
        state,
        {"type": "assistant.transcript.assistant_delta", "text": "I can help with that."},
    )

    assert {m.id for m in state.materials} == {"card", "transcript"}
    assert state.primary_material is not None
    assert state.primary_material.id == "transcript"
    assert state.current_material == "I can help with that."
