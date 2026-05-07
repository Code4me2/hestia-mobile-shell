from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Mapping, Optional


@dataclass(frozen=True)
class VisualMaterial:
    """Constrained visual material the assistant can place on the mobile canvas."""

    id: str
    kind: str
    title: str
    body: str = ""
    priority: int = 0
    actions: tuple[Mapping[str, str], ...] = ()
    sequence: int = 0

    @property
    def display_text(self) -> str:
        if self.kind == "tool_status" and self.body.startswith("Using "):
            return self.body.strip()
        parts = [self.title.strip(), self.body.strip()]
        return "\n".join(part for part in parts if part)


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
    chat_visible: bool = False
    debug_visible: bool = False
    event_journal: tuple[str, ...] = ()
    materials: tuple[VisualMaterial, ...] = ()
    material_sequence: int = 0

    @classmethod
    def initial(cls) -> "MobileShellState":
        return cls(
            mode="blank",
            assistant_state="idle",
            status_text="Listening when needed",
        )

    @property
    def primary_material(self) -> Optional[VisualMaterial]:
        if not self.materials:
            return None
        return max(self.materials, key=lambda material: (material.priority, material.sequence))


def reduce_assistant_event(
    state: MobileShellState,
    event: Mapping[str, Any],
) -> MobileShellState:
    """Reduce a normalized assistant/mobile event into mobile canvas state."""

    next_state = _reduce_assistant_event_without_journal(state, event)
    if str(event.get("type", "")) == "hestia_mobile.clear_event_journal":
        return replace(next_state, event_journal=())
    return _append_event_journal(next_state, event)


def _reduce_assistant_event_without_journal(
    state: MobileShellState,
    event: Mapping[str, Any],
) -> MobileShellState:
    event_type = str(event.get("type", ""))

    if event_type == "assistant.state":
        assistant_state = str(event.get("state", "idle"))
        return _state_for_assistant_lifecycle(
            state,
            assistant_state,
            message=_optional_string(event.get("message")),
        )

    if event_type in {
        "assistant.transcript.assistant_delta",
        "assistant.transcript.user_delta",
    }:
        text = str(event.get("text") or event.get("delta") or "").strip()
        if not text:
            return state
        return _upsert_material(
            state,
            VisualMaterial(
                id="transcript",
                kind="transcript",
                title=text,
                priority=65 if event_type == "assistant.transcript.assistant_delta" else 50,
            ),
        )

    if event_type == "assistant.tool_call":
        return _show_tool_status(
            state,
            name=str(event.get("name") or "tool"),
            status=str(event.get("status") or "running"),
            body=f"Using {str(event.get('name') or 'tool')}",
        )

    if event_type == "assistant.tool_result":
        name = str(event.get("name") or "")
        if not name:
            state_without_tools = replace(
                state,
                materials=tuple(material for material in state.materials if material.kind != "tool_status"),
                tool_status=None,
            )
            return _sync_material_mode(state_without_tools)
        return _dismiss_material(state, f"tool:{name}")

    if event_type == "hestia_mobile.show_card":
        return _upsert_material(state, _card_from_event(event, kind="card"))

    if event_type == "hestia_mobile.update_card":
        return _update_card(state, event)

    if event_type == "hestia_mobile.dismiss_card":
        return _dismiss_material(state, _optional_string(event.get("id")))

    if event_type == "hestia_mobile.show_confirmation":
        confirm_label = str(event.get("confirm_label") or "Confirm")
        cancel_label = str(event.get("cancel_label") or "Cancel")
        return _upsert_material(
            state,
            _card_from_event(
                {
                    **event,
                    "actions": [
                        {"id": "confirm", "label": confirm_label},
                        {"id": "cancel", "label": cancel_label},
                    ],
                },
                kind="confirmation",
                default_priority=90,
            ),
        )

    if event_type == "hestia_mobile.show_tool_status":
        return _show_tool_status(
            state,
            name=str(event.get("name") or "tool"),
            status=str(event.get("status") or "running"),
            body=_optional_string(event.get("body")),
        )

    if event_type == "hestia_mobile.open_chat":
        return _sync_material_mode(replace(state, chat_visible=True))

    if event_type == "hestia_mobile.close_chat":
        return _sync_material_mode(replace(state, chat_visible=False))

    if event_type == "hestia_mobile.submit_text":
        text = str(event.get("text") or "").strip()
        if not text:
            return state
        return _upsert_material(
            replace(
                state,
                chat_visible=True,
                assistant_state="thinking",
                status_text="Thinking",
            ),
            VisualMaterial(
                id="chat:last_user",
                kind="transcript",
                title=f"You: {text}",
                priority=55,
            ),
        )

    if event_type == "hestia_mobile.toggle_debug":
        return replace(state, debug_visible=not state.debug_visible)

    if event_type == "hestia_mobile.set_debug":
        return replace(state, debug_visible=bool(event.get("visible", False)))

    if event_type == "hestia_mobile.clear_event_journal":
        return replace(state, event_journal=())

    if event_type == "assistant.availability":
        available = bool(event.get("available", True))
        reason = str(event.get("reason", ""))
        if not available and reason == "phone_call_active":
            return _sync_material_mode(
                replace(
                    state,
                    mode="call_paused",
                    assistant_state="call_active",
                    status_text="Paused for phone call",
                )
            )
        if available and reason == "phone_call_inactive":
            return _sync_material_mode(
                replace(
                    state,
                    mode="blank",
                    assistant_state="idle",
                    status_text="Listening when needed",
                ),
                expose_protected=True,
            )
        return state

    if event_type == "hestia_mobile.open_app_interface":
        return _sync_material_mode(replace(state, app_interface_visible=True))

    if event_type == "hestia_mobile.close_app_interface":
        return _sync_material_mode(replace(state, app_interface_visible=False))

    return state


def _state_for_assistant_lifecycle(
    state: MobileShellState,
    assistant_state: str,
    message: Optional[str] = None,
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
    if assistant_state == "error" and message:
        status_text = message
    if state.app_interface_visible and mode not in {"call_paused", "offline", "error"}:
        mode = "app_interface"
    elif state.chat_visible and mode not in {"call_paused", "offline", "error"}:
        mode = "chat"
    elif state.primary_material and mode == "blank":
        mode = "material"
    return _sync_material_mode(
        replace(
            state,
            mode=mode,
            assistant_state=assistant_state,
            status_text=status_text,
        )
    )


def _card_from_event(
    event: Mapping[str, Any],
    kind: str,
    default_priority: int = 0,
) -> VisualMaterial:
    card_id = str(event.get("id") or f"{kind}:default")
    return VisualMaterial(
        id=card_id,
        kind=kind,
        title=str(event.get("title") or ""),
        body=str(event.get("body") or ""),
        priority=_int_or_default(event.get("priority"), default_priority),
        actions=_actions_tuple(event.get("actions")),
    )


def _update_card(state: MobileShellState, event: Mapping[str, Any]) -> MobileShellState:
    card_id = str(event.get("id") or "card:default")
    existing = next((material for material in state.materials if material.id == card_id), None)
    if existing is None:
        return _upsert_material(state, _card_from_event(event, kind="card"))
    updated = replace(
        existing,
        kind=str(event.get("kind") or existing.kind),
        title=str(event.get("title")) if event.get("title") is not None else existing.title,
        body=str(event.get("body")) if event.get("body") is not None else existing.body,
        priority=_int_or_default(event.get("priority"), existing.priority),
        actions=_actions_tuple(event.get("actions")) if event.get("actions") is not None else existing.actions,
    )
    return _upsert_material(state, updated)


def _show_tool_status(
    state: MobileShellState,
    name: str,
    status: str,
    body: Optional[str] = None,
) -> MobileShellState:
    material = VisualMaterial(
        id=f"tool:{name}",
        kind="tool_status",
        title=name,
        body=body if body is not None else status,
        priority=70,
    )
    return replace(_upsert_material(state, material), tool_status=f"{name}: {status}")


def _upsert_material(state: MobileShellState, material: VisualMaterial) -> MobileShellState:
    next_sequence = state.material_sequence + 1
    material = replace(material, sequence=next_sequence)
    materials = tuple(item for item in state.materials if item.id != material.id) + (material,)
    next_state = replace(state, materials=materials, material_sequence=next_sequence)
    return _sync_material_mode(next_state)


def _dismiss_material(state: MobileShellState, material_id: Optional[str]) -> MobileShellState:
    if material_id:
        materials = tuple(item for item in state.materials if item.id != material_id)
    else:
        materials = ()
    next_state = replace(state, materials=materials)
    dismissed_tool = bool(material_id and material_id.startswith("tool:"))
    if material_id is None or not materials or dismissed_tool:
        next_state = replace(next_state, tool_status=None)
    return _sync_material_mode(next_state)


def _sync_material_mode(
    state: MobileShellState,
    expose_protected: bool = False,
) -> MobileShellState:
    primary = state.primary_material
    protected = state.mode in {"call_paused", "offline", "error"}
    current_material = None if protected and not expose_protected else (primary.display_text if primary else None)
    if protected and not expose_protected:
        mode = state.mode
    elif state.app_interface_visible:
        mode = "app_interface"
    elif state.chat_visible:
        mode = "chat"
    elif primary:
        mode = "material"
    elif state.mode in {"listening", "thinking", "speaking", "interrupted"}:
        mode = state.mode
    else:
        mode = "blank"
    return replace(state, mode=mode, current_material=current_material)


def state_debug_lines(state: MobileShellState) -> tuple[str, ...]:
    primary = state.primary_material
    primary_label = f"{primary.id}/{primary.kind}" if primary else "none"
    lines = [
        f"mode={state.mode}",
        f"assistant_state={state.assistant_state}",
        f"status={state.status_text}",
        f"primary_material={primary_label}",
        f"materials={len(state.materials)}",
        f"app_interface_visible={state.app_interface_visible}",
        f"chat_visible={state.chat_visible}",
        f"debug_visible={state.debug_visible}",
    ]
    lines.extend(f"event[{index}]={entry}" for index, entry in enumerate(state.event_journal[-6:], start=1))
    return tuple(lines)


def _append_event_journal(state: MobileShellState, event: Mapping[str, Any]) -> MobileShellState:
    summary = _event_summary(event)
    if not summary:
        return state
    return replace(state, event_journal=(state.event_journal + (summary,))[-12:])


def _event_summary(event: Mapping[str, Any]) -> str:
    event_type = str(event.get("type") or "").strip()
    if not event_type:
        return "unknown"
    suffix = ""
    if event_type == "assistant.state":
        suffix = str(event.get("state") or "").strip()
    elif event_type == "assistant.availability":
        reason = str(event.get("reason") or "").strip()
        suffix = reason or str(event.get("available") or "").strip()
    elif event_type in {"hestia_mobile.show_card", "hestia_mobile.update_card", "hestia_mobile.dismiss_card", "hestia_mobile.show_confirmation"}:
        suffix = str(event.get("id") or "").strip()
    elif event_type in {"assistant.tool_call", "hestia_mobile.show_tool_status"}:
        suffix = str(event.get("name") or "").strip()
    return f"{event_type} {suffix}".strip()


def _current_material_text(state: MobileShellState) -> Optional[str]:
    primary = state.primary_material
    return primary.display_text if primary else None


def _actions_tuple(value: Any) -> tuple[Mapping[str, str], ...]:
    if not isinstance(value, list):
        return ()
    actions: list[Mapping[str, str]] = []
    for action in value:
        if not isinstance(action, Mapping):
            continue
        action_id = str(action.get("id") or "")
        label = str(action.get("label") or action_id)
        if action_id or label:
            actions.append({"id": action_id, "label": label})
    return tuple(actions)


def _int_or_default(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _optional_string(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
