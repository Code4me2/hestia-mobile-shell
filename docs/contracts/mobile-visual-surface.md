# Mobile Visual Surface Contract

The mobile visual layer consumes normalized local assistant events. It must not bind directly to raw backend or realtime protocol details.

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
confirm_action
set_surface_state
```

No arbitrary UI mutation in the first implementation.
