# Architecture

## Purpose

`hestia-mobile-shell` is the mobile-native visual layer for Hestia Mobile. It should not inherit the desktop/laptop assumptions of `hestia-shell` wholesale. The phone currently runs PureOS/Phosh/phoc, so the first implementation must be safe inside that session.

## Layers

```text
hardware audio/privacy switch
  -> hestia-unmute-voice.service
  -> tiny-emerson Unmute realtime backend
  -> tiny-emerson agentic_flow orchestrator
  -> hestia-ai-bridge.service on phone
  -> local assistant socket
  -> hestia-mobile-shell visual layer
```

## Design constraints

- Do not expose local Unix sockets over Tailscale.
- Do not block local UI startup on backend availability.
- Do not replace Phosh until a reversible prototype proves useful.
- Keep UI logic thin; test state reducers and protocol adapters.
- The normal app interface is secondary and explicit.

## First prototype

The first prototype is a GTK3 app because GTK3 is available on the current PureOS phone and can run under Phosh without replacing the session. GTK4/libadwaita are not currently available in the checked environment.

The app should:

- render a blank AI canvas by default;
- show assistant state text for listening/thinking/speaking;
- show transient material for transcript/tool events;
- provide a bottom-right button for app-interface mode;
- exit cleanly.

## Later integration options

1. GTK/Phosh-compatible app launched at login.
2. Phosh extension/plugin or shell integration.
3. Dedicated Hestia mobile session/compositor after product behavior is validated.
