# Mobile Visual Surface Contract

The mobile visual layer consumes normalized local assistant events. It must not bind directly to raw backend or realtime protocol details.

## Supported visual verbs

The first supported event set is intentionally small:

| Event | Purpose |
| --- | --- |
| `hestia_mobile.show_card` | create/replace one material card by `id` |
| `hestia_mobile.update_card` | update fields on an existing card, creating it if needed |
| `hestia_mobile.dismiss_card` | remove one card by `id`; no `id` clears all cards |
| `hestia_mobile.show_confirmation` | show confirm/cancel material with constrained actions |
| `hestia_mobile.show_tool_status` | show/update a tool progress material |
| `hestia_mobile.open_chat` / `close_chat` | open/close the secondary chat fallback |
| `hestia_mobile.submit_text` | local prototype text fallback submission |
| `hestia_mobile.toggle_debug` / `set_debug` | show/hide the debug/event journal overlay |
| `hestia_mobile.clear_event_journal` | clear recent local event history |

Cards are selected for display by highest `priority`, then most recent update. UI code should render the reducer state; it should not decide business behavior itself.

## Inputs

- Assistant event socket:
  - default: `$XDG_RUNTIME_DIR/hestia-shell/assistant.sock`
  - newline-delimited JSON frames
- Bridge health:
  - `http://127.0.0.1:8765/health`
- Optional future call-state source:
  - ModemManager / gnome-calls / callaudiod DBus signals

## Core UI modes

| Mode | Meaning |
| --- | --- |
| `blank` | Resting AI canvas; no app launcher by default. |
| `listening` | Assistant is listening. |
| `thinking` | Assistant is processing. |
| `speaking` | Assistant is speaking. |
| `material` | AI has relevant text/card/tool material to show. |
| `chat` | Secondary text/chat fallback is explicitly open. |
| `app_interface` | Normal app interface has been explicitly opened. |
| `call_paused` | Assistant paused due to active phone call. |
| `offline` | Backend or local bridge unavailable. |
| `error` | Actionable failure state. |

## Consumed assistant events

```json
{ "type": "assistant.state", "state": "listening" }
{ "type": "assistant.state", "state": "thinking" }
{ "type": "assistant.state", "state": "speaking" }
{ "type": "assistant.state", "state": "idle" }
{ "type": "assistant.transcript.user_delta", "text": "hello" }
{ "type": "assistant.transcript.assistant_delta", "text": "Here is what I found." }
{ "type": "assistant.tool_call", "name": "calendar", "status": "running" }
{ "type": "assistant.availability", "available": false, "reason": "phone_call_active" }
```

## Mobile-local visual events

```json
{ "type": "hestia_mobile.open_app_interface" }
{ "type": "hestia_mobile.close_app_interface" }
{ "type": "hestia_mobile.open_chat" }
{ "type": "hestia_mobile.submit_text", "text": "What's next?" }
{ "type": "hestia_mobile.close_chat" }
{ "type": "hestia_mobile.toggle_debug" }
{ "type": "hestia_mobile.set_debug", "visible": true }
{ "type": "hestia_mobile.clear_event_journal" }
```

## Visual verbs

Start with a small whitelist:

```text
show_transcript
show_card
update_card
dismiss_card
show_tool_status
open_app_interface
close_app_interface
open_chat
close_chat
submit_text
set_debug_overlay
clear_event_journal
confirm_action
set_surface_state
```

No arbitrary UI mutation in the first implementation.
