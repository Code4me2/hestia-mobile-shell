# Agent Phone Interface Contract

This contract defines the local-only interface an agent may use to observe and influence the Hestia Mobile visual surface on PureOS/Phosh.

## Scope

The phone remains a PureOS/Phosh device. Hestia adds a constrained AI surface, local bridge, voice client, and phone-local Unix sockets. Agents may request visual material and chat fallback behavior through documented events, but they may not arbitrarily mutate the UI or bypass protected modes.

## Local-only boundary

Do not expose the phone-local Unix sockets over Tailscale or any remote network. Remote services may run on `tiny-emerson`, but the phone UI control plane stays on the phone.

```text
$XDG_RUNTIME_DIR/hestia-shell/assistant.sock
$XDG_RUNTIME_DIR/hestia-shell/ai.sock
http://127.0.0.1:8765/mobile_capabilities
http://127.0.0.1:8765/mobile_state
http://127.0.0.1:8765/health
```

## Capability discovery

`hestia-ai-bridge` exposes a read-only capabilities endpoint:

```text
GET http://127.0.0.1:8765/mobile_capabilities
```

The response describes socket paths, supported assistant states, supported visual verbs, protected modes, forbidden behaviors, sanitized orchestrator availability, and the local `mobile_state` endpoint. It must not reveal raw upstream URLs, secrets, or exception details.

## Runtime state

`hestia-ai-bridge` exposes a local runtime-state endpoint:

```text
GET http://127.0.0.1:8765/mobile_state
```

The response describes whether the surface is currently protected and which verbs are safe right now:

```json
{"interface":"hestia-mobile-agent-phone-interface","version":1,"assistant_state":"idle","protected_mode":null,"protected":false,"online":true,"chat_open":false,"app_interface_open":false,"visible_cards":[],"safe_actions":["show_card","update_card","dismiss_card"]}
```

When `protected` is true, adapters must send only verbs listed in `safe_actions`. The default protected safe set is `dismiss_card`, `close_chat`, and `close_app_interface`.

## Versioning policy

- `interface` is the stable contract family identifier.
- `version` increments on breaking changes to required fields, verb meanings, socket protocol, or protected-mode behavior.
- Additive fields are non-breaking; agents must ignore unknown fields.
- Agents must refuse unknown major/interface versions and must never fall back to raw socket mutation.

## Agent adapter

Agents should prefer the validated adapter over writing directly to `assistant.sock`:

```bash
PYTHONPATH=src python3 -m hestia_mobile_shell.agent_adapter show-card \
  --id agent-demo \
  --title "Agent control works" \
  --body "This card was capability-checked before being sent."
```

The adapter fetches `http://127.0.0.1:8765/mobile_capabilities`, validates the interface name/version, enforces `transport: local-only`, rejects non-loopback HTTP capability URLs, requires a `mobile_state` URL, refuses visual verbs not advertised by the phone, fetches `mobile_state`, refuses protected-mode-unsafe actions, and then sends one newline-delimited JSON event to the advertised `assistant.sock`. If the bridge is token-protected, pass `--bridge-token` or set `HESTIA_BRIDGE_TOKEN`; the adapter sends the same bearer token to capabilities and state endpoints.

The installed console script is:

```bash
hestia-mobile-agent --capabilities-url http://127.0.0.1:8765/mobile_capabilities open-chat
```

## `assistant.sock` visual/event path

Protocol: newline-delimited JSON over a Unix-domain socket.

Shell subscribers send:

```json
{"type":"subscribe"}
```

Voice clients, bridges, and trusted local agent adapters may publish normalized assistant events:

```json
{"type":"assistant.state","state":"listening"}
{"type":"assistant.transcript.assistant_delta","text":"Here is what I found."}
{"type":"assistant.tool_call","name":"calendar","status":"running"}
```

They may also publish mobile visual events from the allowed verb set below.

## `ai.sock` typed/chat path

Protocol: newline-delimited JSON over a Unix-domain socket.

The mobile shell sends typed fallback requests to:

```json
{"type":"chat","model":"default","messages":[{"role":"user","content":"What's next?"}],"extra_context":{"source":"hestia-mobile-shell","input_mode":"typed_fallback"}}
```

The bridge returns:

```text
token -> assistant.transcript.assistant_delta
tool_call -> assistant.tool_call
tool_result -> assistant.tool_result
done -> assistant.state idle
error -> assistant.state error
```

## Allowed visual verbs

Agents may request only these constrained visual actions:

| Verb | Event type | Purpose |
| --- | --- | --- |
| `show_card` | `hestia_mobile.show_card` | Show or replace one contextual material card. |
| `update_card` | `hestia_mobile.update_card` | Update fields on an existing card, creating it if needed. |
| `dismiss_card` | `hestia_mobile.dismiss_card` | Remove one card by `id`; no `id` clears material. |
| `show_confirmation` | `hestia_mobile.show_confirmation` | Show confirm/cancel material with constrained labels. |
| `show_tool_status` | `hestia_mobile.show_tool_status` | Show/update tool progress material. |
| `open_chat` | `hestia_mobile.open_chat` | Open the secondary chat fallback. |
| `close_chat` | `hestia_mobile.close_chat` | Close the secondary chat fallback. |
| `open_app_interface` | `hestia_mobile.open_app_interface` | Reveal the secondary normal-app placeholder/interface. |
| `close_app_interface` | `hestia_mobile.close_app_interface` | Hide the secondary normal-app placeholder/interface. |

Example:

```json
{"type":"hestia_mobile.show_card","id":"agent-demo","title":"Agent control works","body":"This card came from the agent phone interface contract.","priority":70}
```

## Assistant states

The visual surface recognizes:

```text
idle
listening
thinking
speaking
interrupted
call_active
offline
error
```

## Protected modes

These modes suppress optional cards, actions, chat input, app-interface placeholders, and tool-status material while preserving state for restore:

```text
phone_call_active
offline
error
```

`phone_call_active` is reported through:

```json
{"type":"assistant.availability","available":false,"reason":"phone_call_active"}
```

and cleared through:

```json
{"type":"assistant.availability","available":true,"reason":"phone_call_inactive"}
```

## Forbidden behavior

Agents and adapters must not:

- perform arbitrary UI mutation;
- expose Unix sockets over Tailscale or a public interface;
- bypass `phone_call_active`, `offline`, or `error` protected modes;
- launch unapproved OS actions through this visual contract;
- treat the visual surface as a dashboard-first UI.

## Verification

Offline validation should include:

```bash
PYTHONPATH=src python3 -m pytest -q
PYTHONPATH=src python3 -m hestia_mobile_shell.mock_socket --socket /tmp/hestia-assistant.sock
PYTHONPATH=src python3 -m hestia_mobile_shell.control --socket /tmp/hestia-assistant.sock show-card --id agent-demo --title "Agent control works"
PYTHONPATH=src python3 -m hestia_mobile_shell.fake_phone --root /tmp/hestia-fake-phone --port 8766
```

Runtime phone validation remains separate: confirm the active Phosh session, `hestia-ai-bridge.service`, `hestia-unmute-voice.service`, `assistant.sock`, `ai.sock`, and bridge health before claiming end-to-end device readiness.
