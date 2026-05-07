# Initial Prototype Acceptance

This checklist defines the current "initial prototype" target for the AI-primary Hestia Mobile shell. It is intentionally scoped to features that can be built and verified without replacing Phosh or requiring the phone to be present.

## Product fit

- Blank, calm AI canvas at rest.
- Voice/status surface is primary; screen material appears only when useful.
- Bottom-right affordance opens a normal-app placeholder without making the dashboard primary.
- Chat/text input exists as fallback/debug, not the main interaction.
- Debug/event journal is available on demand and hidden by default.
- Phone-call protected mode suppresses cards, chat input, app interface, actions, and tool status while retaining state for later restore.

## Implemented local event contract

Assistant lifecycle:

```json
{"type":"assistant.state","state":"listening"}
{"type":"assistant.state","state":"thinking"}
{"type":"assistant.state","state":"speaking"}
{"type":"assistant.state","state":"idle"}
{"type":"assistant.state","state":"offline"}
{"type":"assistant.state","state":"error"}
```

Phone-call suppression:

```json
{"type":"assistant.availability","available":false,"reason":"phone_call_active"}
{"type":"assistant.availability","available":true,"reason":"phone_call_inactive"}
```

Visual material:

```json
{"type":"hestia_mobile.show_card","id":"next-event","title":"Next event","body":"11:30 — Design review","priority":60}
{"type":"hestia_mobile.update_card","id":"next-event","body":"Prep notes ready"}
{"type":"hestia_mobile.dismiss_card","id":"next-event"}
{"type":"hestia_mobile.dismiss_card"}
{"type":"hestia_mobile.show_confirmation","id":"send-note","title":"Send note?","confirm_label":"Send","cancel_label":"Not now"}
{"type":"hestia_mobile.show_tool_status","name":"calendar","status":"running","body":"Checking schedule"}
```

Fallback/debug surfaces:

```json
{"type":"hestia_mobile.open_chat"}
{"type":"hestia_mobile.close_chat"}
{"type":"hestia_mobile.submit_text","text":"What's next?"}
{"type":"hestia_mobile.toggle_debug"}
{"type":"hestia_mobile.set_debug","visible":true}
{"type":"hestia_mobile.clear_event_journal"}
{"type":"hestia_mobile.open_app_interface"}
{"type":"hestia_mobile.close_app_interface"}
```

## Manual validation flow

Start mock socket:

```bash
PYTHONPATH=src python3 -m hestia_mobile_shell.mock_socket \
  --socket /tmp/hestia-assistant.sock \
  --events examples/demo-events.jsonl \
  --interval-ms 900
```

Start windowed shell:

```bash
PYTHONPATH=src python3 -m hestia_mobile_shell.app \
  --windowed \
  --assistant-socket /tmp/hestia-assistant.sock
```

Inject useful states:

```bash
PYTHONPATH=src python3 -m hestia_mobile_shell.control --socket /tmp/hestia-assistant.sock toggle-debug
PYTHONPATH=src python3 -m hestia_mobile_shell.control --socket /tmp/hestia-assistant.sock open-chat
PYTHONPATH=src python3 -m hestia_mobile_shell.control --socket /tmp/hestia-assistant.sock text "What's next?"
PYTHONPATH=src python3 -m hestia_mobile_shell.control --socket /tmp/hestia-assistant.sock show-card --id next-event --title "Next event" --body "11:30 — Design review" --priority 60
PYTHONPATH=src python3 -m hestia_mobile_shell.control --socket /tmp/hestia-assistant.sock call-active
PYTHONPATH=src python3 -m hestia_mobile_shell.control --socket /tmp/hestia-assistant.sock call-inactive
PYTHONPATH=src python3 -m hestia_mobile_shell.control --socket /tmp/hestia-assistant.sock clear-events
```

Expected result:

- Debug panel shows mode, assistant state, primary material, material count, app/chat/debug visibility, and recent event journal.
- Chat fallback shows a text entry only while chat is open and not protected.
- Submitted text appears as local user transcript material and moves status to Thinking.
- Cards/tool/confirmation material render in the central card area.
- `call-active` hides material and chat input; `call-inactive` restores retained chat/material.
- `Esc` exits. `F12` toggles debug.

## Automated gates

```bash
PYTHONPATH=src python3 -m pytest -q
PYTHONPATH=src python3 -m py_compile src/hestia_mobile_shell/*.py
bash -n scripts/*.sh
desktop-file-validate packaging/hestia-mobile-shell.desktop
systemd-analyze --user verify packaging/hestia-mobile-shell.service
git diff --check
```

## Not yet claimed

- Runtime validation on the actual phone/Phosh session.
- Real backend submission of typed chat text; the current text command is a local fallback surface event.
- Replacement of Phosh or app launcher integration beyond the safe prototype launcher/service template.
