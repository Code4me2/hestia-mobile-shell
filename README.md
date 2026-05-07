# hestia-mobile-shell

AI-primary mobile shell prototype for Hestia on PureOS/Phosh.

This repo is intentionally separate from desktop/laptop [`hestia-shell`](https://github.com/Code4me2/hestia-shell). The current phone runs PureOS/Phosh/phoc on Wayland, not Hyprland/Quickshell, and the Hestia Mobile product direction is different:

- Voice is the primary control surface.
- The screen rests as a mostly blank, calm AI canvas.
- The assistant brings up relevant material/cards only when useful.
- The normal app interface is secondary.
- A bottom-right affordance opens the normal app interface.
- The UI consumes local Hestia assistant socket events rather than raw backend protocols.

## Current status

This is an initial safe prototype/skeleton:

- tested pure state reducer for normalized `assistant.*` events;
- tested visual material/card reducer for constrained `show_card`, `update_card`, `dismiss_card`, `show_confirmation`, and `show_tool_status` verbs;
- tested chat/text fallback and debug event journal state;
- mock assistant socket plus manual control CLI for no-phone testing;
- runtime/session probe for PureOS/Phosh compatibility checks;
- GTK3 fullscreen/near-fullscreen prototype that can be launched and killed without replacing Phosh;
- architecture, visual contract, runbook, and acceptance docs.

It does **not** replace Phosh yet.

## Runtime assumptions

Working services are expected from the Hestia Mobile gateway stack:

```text
hestia-unmute-voice.service
hestia-ai-bridge.service
$XDG_RUNTIME_DIR/hestia-shell/assistant.sock
$XDG_RUNTIME_DIR/hestia-shell/ai.sock
```

Backend services run on `tiny-emerson` through Tailscale and are tracked by the `hestia-mobile` integration repo.

## Probe the phone session

```bash
./scripts/probe-runtime.sh
```

Expected current phone shape:

```text
desktop=Phosh:GNOME
session_desktop=phosh
session_type=wayland
processes include phosh/phoc
hestia-ai-bridge.service active
hestia-unmute-voice.service active
assistant.sock present
```

## Run tests

```bash
PYTHONPATH=src python3 -m pytest -q
```

## Launch the prototype

The first prototype is deliberately reversible. It runs as a GTK3 app inside the current Phosh session.

Live assistant socket:

```bash
PYTHONPATH=src python3 -m hestia_mobile_shell.app
```

Offline demo replay, useful when the phone/backend is unavailable:

```bash
PYTHONPATH=src python3 -m hestia_mobile_shell.app \
  --windowed \
  --demo-events examples/demo-events.jsonl \
  --demo-interval-ms 900
```

Exit with `Esc` or close the window. If launched fullscreen and you need to force-close it:

```bash
pkill -f hestia_mobile_shell.app
```

Optional non-fullscreen mode for safer development:

```bash
PYTHONPATH=src python3 -m hestia_mobile_shell.app --windowed
```

## Mock assistant socket

For testing the real Unix-socket subscription/read path without the phone stack, run a mock `assistant.sock` server in one terminal:

```bash
cd /home/purism/projects/ai-phone-review/hestia-mobile-shell
PYTHONPATH=src python3 -m hestia_mobile_shell.mock_socket \
  --socket /tmp/hestia-assistant.sock \
  --events examples/demo-events.jsonl \
  --interval-ms 900
```

Then run the app against that socket in another terminal:

```bash
PYTHONPATH=src python3 -m hestia_mobile_shell.app \
  --windowed \
  --assistant-socket /tmp/hestia-assistant.sock
```

This is closer to live operation than `--demo-events`: the app sends the same subscribe frame and reads the same newline-delimited JSON socket stream it will use with `hestia-ai-bridge`.

## Manual control CLI

For fast offline testing, send one event into a running mock socket or live `assistant.sock`:

```bash
PYTHONPATH=src python3 -m hestia_mobile_shell.control \
  --socket /tmp/hestia-assistant.sock \
  show-card \
  --id next-event \
  --title "Next event" \
  --body "11:30 — Design review" \
  --priority 60
```

Useful commands:

```bash
PYTHONPATH=src python3 -m hestia_mobile_shell.control --socket /tmp/hestia-assistant.sock state listening
PYTHONPATH=src python3 -m hestia_mobile_shell.control --socket /tmp/hestia-assistant.sock state thinking
PYTHONPATH=src python3 -m hestia_mobile_shell.control --socket /tmp/hestia-assistant.sock tool-status --name calendar --status running --body "Checking schedule"
PYTHONPATH=src python3 -m hestia_mobile_shell.control --socket /tmp/hestia-assistant.sock show-confirmation --id send-note --title "Send note?" --confirm-label Send --cancel-label "Not now"
PYTHONPATH=src python3 -m hestia_mobile_shell.control --socket /tmp/hestia-assistant.sock dismiss-card --id next-event
PYTHONPATH=src python3 -m hestia_mobile_shell.control --socket /tmp/hestia-assistant.sock call-active
PYTHONPATH=src python3 -m hestia_mobile_shell.control --socket /tmp/hestia-assistant.sock call-inactive
PYTHONPATH=src python3 -m hestia_mobile_shell.control --socket /tmp/hestia-assistant.sock open-chat
PYTHONPATH=src python3 -m hestia_mobile_shell.control --socket /tmp/hestia-assistant.sock text "What's next?"
PYTHONPATH=src python3 -m hestia_mobile_shell.control --socket /tmp/hestia-assistant.sock close-chat
PYTHONPATH=src python3 -m hestia_mobile_shell.control --socket /tmp/hestia-assistant.sock toggle-debug
PYTHONPATH=src python3 -m hestia_mobile_shell.control --socket /tmp/hestia-assistant.sock clear-events
PYTHONPATH=src python3 -m hestia_mobile_shell.control --socket /tmp/hestia-assistant.sock open-apps
PYTHONPATH=src python3 -m hestia_mobile_shell.control --socket /tmp/hestia-assistant.sock close-apps
```

When installed as a package, use `hestia-mobile-control` instead of `PYTHONPATH=src python3 -m hestia_mobile_shell.control`.

## Visual material verbs

The mobile canvas accepts a small, constrained visual verb set. These are local shell events, not arbitrary UI generation:

```json
{"type":"hestia_mobile.show_card","id":"next-event","title":"Next event","body":"11:30 — Design review","priority":60}
{"type":"hestia_mobile.update_card","id":"next-event","body":"11:30 — Design review\nPrep notes ready"}
{"type":"hestia_mobile.dismiss_card","id":"next-event"}
{"type":"hestia_mobile.show_confirmation","id":"send-note","title":"Send note?","confirm_label":"Send","cancel_label":"Not now"}
{"type":"hestia_mobile.show_tool_status","name":"calendar","status":"running","body":"Checking schedule"}
```

Cards are prioritized by `priority`; ties use the most recently updated card. `dismiss_card` without an `id` clears all materials. The GTK prototype renders the primary material card plus action labels, while the pure reducer remains fully unit-tested.

## Chat fallback and ai.sock typed submission

The chat fallback is explicit and secondary:

```json
{"type":"hestia_mobile.open_chat"}
{"type":"hestia_mobile.submit_text","text":"What's next?"}
{"type":"hestia_mobile.close_chat"}
```

Submitted text opens the chat fallback, records local user transcript material, and sends a bridge-compatible `chat` request to `ai.sock` when the app is not in demo replay mode:

```json
{"type":"chat","model":"default","messages":[{"role":"user","content":"What's next?"}],"extra_context":{"source":"hestia-mobile-shell","input_mode":"typed_fallback"}}
```

The `ai.sock` response stream is normalized back into shell events:

```text
token -> assistant.transcript.assistant_delta
tool_call -> assistant.tool_call
tool_result -> assistant.tool_result
done -> assistant.state idle
error -> assistant.state error
```

Live phone/bridge runtime validation is still pending until the device is available.

## Debug overlay

The debug overlay is hidden by default and can be toggled with `F12` or events:

```json
{"type":"hestia_mobile.toggle_debug"}
{"type":"hestia_mobile.set_debug","visible":true}
{"type":"hestia_mobile.clear_event_journal"}
```

It shows the current mode, assistant state, primary material, material count, app/chat/debug visibility, and recent event journal.

See [`docs/acceptance/initial-prototype.md`](docs/acceptance/initial-prototype.md) for the current prototype acceptance checklist.

## Relationship to other repos

- `hestia-mobile`: integration/meta repo, manifests, probes, runbooks, release gates.
- `hestia-ai-bridge`: local bridge, health endpoint, assistant socket, and `/mobile_capabilities` discovery.
- `unmute-streaming-client`: always-available voice client.
- `hestia-shell`: desktop/laptop Quickshell shell and reference event/UI model.
- `hestia-mobile-shell`: this repo; mobile-native AI-first visual layer.

- [`docs/contracts/agent-phone-interface.md`](docs/contracts/agent-phone-interface.md) defines the local-only agent-facing phone UI contract, including the allowed visual verbs, `assistant.sock`, `ai.sock`, protected modes, and `/mobile_capabilities` discovery.

## Product target

Resting state:

```text
┌─────────────────────┐
│                     │
│                     │
│    blank calm AI    │
│       canvas        │
│                     │
│                 ◉   │  normal apps affordance
└─────────────────────┘
```

Material state:

```text
┌─────────────────────┐
│                     │
│  ┌───────────────┐  │
│  │ relevant AI   │  │
│  │ material/card │  │
│  └───────────────┘  │
│                 ◉   │
└─────────────────────┘
```
