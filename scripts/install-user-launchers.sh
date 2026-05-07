#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DESKTOP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"

mkdir -p "$DESKTOP_DIR" "$SYSTEMD_USER_DIR"
install -m 0644 "$ROOT/packaging/hestia-mobile-shell.desktop" "$DESKTOP_DIR/hestia-mobile-shell.desktop"
install -m 0644 "$ROOT/packaging/hestia-mobile-shell.service" "$SYSTEMD_USER_DIR/hestia-mobile-shell.service"

systemctl --user daemon-reload

cat <<MSG
Installed Hestia Mobile Shell prototype launchers.

Manual launch:
  gtk-launch hestia-mobile-shell

Start user service once:
  systemctl --user start hestia-mobile-shell.service

Enable at user session startup:
  systemctl --user enable hestia-mobile-shell.service

Stop:
  systemctl --user stop hestia-mobile-shell.service
MSG
