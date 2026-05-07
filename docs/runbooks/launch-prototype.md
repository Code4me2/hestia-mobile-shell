# Launch Prototype Runbook

This runbook is safe to use when the phone is available again. It does not replace Phosh.

## One-time install

```bash
cd /home/purism/projects/ai-phone-review/hestia-mobile-shell
chmod +x scripts/install-user-launchers.sh
./scripts/install-user-launchers.sh
```

## Manual development launch

Mock assistant socket, closest to live operation without the phone stack:

```bash
cd /home/purism/projects/ai-phone-review/hestia-mobile-shell
PYTHONPATH=src python3 -m hestia_mobile_shell.mock_socket \
  --socket /tmp/hestia-assistant.sock \
  --events examples/demo-events.jsonl \
  --interval-ms 900
```

In another terminal:

```bash
PYTHONPATH=src python3 -m hestia_mobile_shell.app \
  --windowed \
  --assistant-socket /tmp/hestia-assistant.sock
```

Manual one-shot control while the app is connected to that socket:

```bash
PYTHONPATH=src python3 -m hestia_mobile_shell.control --socket /tmp/hestia-assistant.sock show-card --id next-event --title "Next event" --body "11:30 — Design review" --priority 60
PYTHONPATH=src python3 -m hestia_mobile_shell.control --socket /tmp/hestia-assistant.sock tool-status --name calendar --status running --body "Checking schedule"
PYTHONPATH=src python3 -m hestia_mobile_shell.control --socket /tmp/hestia-assistant.sock show-confirmation --id send-note --title "Send note?" --confirm-label Send --cancel-label "Not now"
PYTHONPATH=src python3 -m hestia_mobile_shell.control --socket /tmp/hestia-assistant.sock open-chat
PYTHONPATH=src python3 -m hestia_mobile_shell.control --socket /tmp/hestia-assistant.sock text "What's next?"
PYTHONPATH=src python3 -m hestia_mobile_shell.control --socket /tmp/hestia-assistant.sock toggle-debug
PYTHONPATH=src python3 -m hestia_mobile_shell.control --socket /tmp/hestia-assistant.sock call-active
PYTHONPATH=src python3 -m hestia_mobile_shell.control --socket /tmp/hestia-assistant.sock call-inactive
PYTHONPATH=src python3 -m hestia_mobile_shell.control --socket /tmp/hestia-assistant.sock dismiss-card
```

Windowed, with internal offline demo events:

```bash
cd /home/purism/projects/ai-phone-review/hestia-mobile-shell
PYTHONPATH=src python3 -m hestia_mobile_shell.app \
  --windowed \
  --demo-events examples/demo-events.jsonl \
  --demo-interval-ms 900
```

Windowed, using the live assistant socket:

```bash
PYTHONPATH=src python3 -m hestia_mobile_shell.app --windowed
```

Fullscreen, live assistant socket:

```bash
PYTHONPATH=src python3 -m hestia_mobile_shell.app
```

## Start/stop as user service

Start once:

```bash
systemctl --user start hestia-mobile-shell.service
```

Check logs:

```bash
journalctl --user -u hestia-mobile-shell.service -f
```

Stop:

```bash
systemctl --user stop hestia-mobile-shell.service
```

Enable on login only after manual testing feels safe:

```bash
systemctl --user enable hestia-mobile-shell.service
```

Disable:

```bash
systemctl --user disable hestia-mobile-shell.service
```

## Emergency exit

The prototype exits on `Esc`. If that fails:

```bash
pkill -f hestia_mobile_shell.app
```

## Expected behavior

- Blank dark AI canvas at rest.
- Status text changes for listening/thinking/speaking/offline.
- Transient material appears when assistant transcript/tool events arrive.
- Bottom-right `Apps` button toggles a placeholder normal-app interface.
- Voice services continue independently of this UI.
