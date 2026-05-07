from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Mapping, Optional


@dataclass(frozen=True)
class MobileShellState:
    """Pure state for the AI-primary Hestia Mobile canvas.

    The visual layer should stay thin and render this state. Backend and
    realtime protocols are normalized elsewhere into assistant.* events.
    """

    mode: str
    assistant_state: str
    status_text: str
    current_material: Optional[str] = None
    tool_status: Optional[str] = None
    app_interface_visible: bool = False

    @classmethod
    def initial(cls) -> "MobileShellState":
        return cls(
            mode="blank",
            assistant_state="idle",
            status_text="Listening when needed",
        )


def reduce_assistant_event(
    state: MobileShellState,
    event: Mapping[str, Any],
) -> MobileShellState:
    """Reduce a normalized assistant/mobile event into mobile canvas state."""

    event_type = str(event.get("type", ""))

    if event_type == "assistant.state":
        assistant_state = str(event.get("state", "idle"))
        return _state_for_assistant_lifecycle(state, assistant_state)

    if event_type in {
        "assistant.transcript.assistant_delta",
        "assistant.transcript.user_delta",
    }:
        text = str(event.get("text") or event.get("delta") or "").strip()
        if not text:
            return state
        return replace(
            state,
            mode="app_interface" if state.app_interface_visible else "material",
            current_material=text,
        )

    if event_type == "assistant.tool_call":
        name = str(event.get("name") or "tool")
        status = str(event.get("status") or "running")
        return replace(
            state,
            mode="app_interface" if state.app_interface_visible else "material",
            tool_status=f"{name}: {status}",
            current_material=f"Using {name}",
        )

    if event_type == "assistant.availability":
        available = bool(event.get("available", True))
        reason = str(event.get("reason", ""))
        if not available and reason == "phone_call_active":
            return replace(
                state,
                mode="call_paused",
                assistant_state="call_active",
                status_text="Paused for phone call",
            )
        if available and reason == "phone_call_inactive":
            return replace(
                state,
                mode="blank",
                assistant_state="idle",
                status_text="Listening when needed",
            )
        return state

    if event_type == "hestia_mobile.open_app_interface":
        return replace(state, mode="app_interface", app_interface_visible=True)

    if event_type == "hestia_mobile.close_app_interface":
        return replace(
            state,
            mode="material" if state.current_material else "blank",
            app_interface_visible=False,
        )

    return state


def _state_for_assistant_lifecycle(
    state: MobileShellState,
    assistant_state: str,
) -> MobileShellState:
    mapping = {
        "idle": ("blank", "Listening when needed"),
        "listening": ("listening", "Listening"),
        "thinking": ("thinking", "Thinking"),
        "speaking": ("speaking", "Speaking"),
        "interrupted": ("interrupted", "Interrupted"),
        "offline": ("offline", "Offline"),
        "error": ("error", "Needs attention"),
        "call_active": ("call_paused", "Paused for phone call"),
    }
    mode, status_text = mapping.get(assistant_state, ("blank", "Listening when needed"))
    if state.app_interface_visible and mode not in {"call_paused", "offline", "error"}:
        mode = "app_interface"
    return replace(
        state,
        mode=mode,
        assistant_state=assistant_state,
        status_text=status_text,
    )
