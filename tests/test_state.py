from hestia_mobile_shell.state import MobileShellState, reduce_assistant_event


def test_initial_state_is_blank_and_available():
    state = MobileShellState.initial()

    assert state.mode == "blank"
    assert state.assistant_state == "idle"
    assert state.app_interface_visible is False
    assert state.status_text == "Listening when needed"


def test_reduces_assistant_lifecycle_events_to_mobile_states():
    state = MobileShellState.initial()

    state = reduce_assistant_event(state, {"type": "assistant.state", "state": "listening"})
    assert state.mode == "listening"
    assert state.assistant_state == "listening"
    assert state.status_text == "Listening"

    state = reduce_assistant_event(state, {"type": "assistant.state", "state": "thinking"})
    assert state.mode == "thinking"
    assert state.status_text == "Thinking"

    state = reduce_assistant_event(state, {"type": "assistant.state", "state": "speaking"})
    assert state.mode == "speaking"
    assert state.status_text == "Speaking"

    state = reduce_assistant_event(state, {"type": "assistant.state", "state": "idle"})
    assert state.mode == "blank"
    assert state.status_text == "Listening when needed"


def test_transcript_delta_creates_contextual_material_without_opening_app_interface():
    state = MobileShellState.initial()

    state = reduce_assistant_event(
        state,
        {"type": "assistant.transcript.assistant_delta", "text": "Your next meeting is at 4."},
    )

    assert state.mode == "material"
    assert state.current_material == "Your next meeting is at 4."
    assert state.app_interface_visible is False


def test_tool_call_creates_tool_status_material():
    state = MobileShellState.initial()

    state = reduce_assistant_event(
        state,
        {"type": "assistant.tool_call", "name": "calendar", "status": "running"},
    )

    assert state.mode == "material"
    assert state.tool_status == "calendar: running"
    assert state.current_material == "Using calendar"


def test_availability_call_active_pauses_ai_surface():
    state = MobileShellState.initial()

    state = reduce_assistant_event(
        state,
        {"type": "assistant.availability", "available": False, "reason": "phone_call_active"},
    )

    assert state.mode == "call_paused"
    assert state.assistant_state == "call_active"
    assert state.status_text == "Paused for phone call"

    state = reduce_assistant_event(
        state,
        {"type": "assistant.availability", "available": True, "reason": "phone_call_inactive"},
    )

    assert state.mode == "blank"
    assert state.assistant_state == "idle"


def test_app_interface_toggle_is_explicit_and_independent_from_voice_material():
    state = MobileShellState.initial()

    state = reduce_assistant_event(state, {"type": "hestia_mobile.open_app_interface"})
    assert state.app_interface_visible is True
    assert state.mode == "app_interface"

    state = reduce_assistant_event(
        state,
        {"type": "assistant.transcript.assistant_delta", "text": "I found a route."},
    )
    assert state.app_interface_visible is True
    assert state.current_material == "I found a route."

    state = reduce_assistant_event(state, {"type": "hestia_mobile.close_app_interface"})
    assert state.app_interface_visible is False
    assert state.mode == "material"
