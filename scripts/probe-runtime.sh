#!/usr/bin/env bash
set -euo pipefail

runtime_dir="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"

printf '== session ==\n'
printf 'desktop=%s\n' "${XDG_CURRENT_DESKTOP:-}"
printf 'session_desktop=%s\n' "${XDG_SESSION_DESKTOP:-}"
printf 'session_type=%s\n' "${XDG_SESSION_TYPE:-}"
printf 'wayland_display=%s\n' "${WAYLAND_DISPLAY:-}"
printf 'display=%s\n' "${DISPLAY:-}"
printf 'runtime_dir=%s\n' "$runtime_dir"

printf '\n== os ==\n'
if [ -r /etc/os-release ]; then
  . /etc/os-release
  printf 'pretty_name=%s\n' "${PRETTY_NAME:-}"
  printf 'id=%s\n' "${ID:-}"
  printf 'version_codename=%s\n' "${VERSION_CODENAME:-}"
fi
uname -m

printf '\n== graphical processes ==\n'
pgrep -af 'phosh|phoc|gnome-shell|mutter|hyprland|Hyprland|qs|quickshell|hestia-mobile|hestia-shell' || true

printf '\n== binaries ==\n'
for c in phosh phoc qs quickshell gsettings busctl gdbus python3; do
  if command -v "$c" >/dev/null 2>&1; then
    printf '%s=%s\n' "$c" "$(command -v "$c")"
  else
    printf '%s=missing\n' "$c"
  fi
done

printf '\n== python ui bindings ==\n'
python3 - <<'PY'
import subprocess
import sys

snippets = {
    'gi': "import gi",
    'Gtk3.0': "import gi; gi.require_version('Gtk', '3.0'); from gi.repository import Gtk",
    'Gtk4.0': "import gi; gi.require_version('Gtk', '4.0'); from gi.repository import Gtk",
    'Adw1': "import gi; gi.require_version('Adw', '1'); from gi.repository import Adw",
}
for name, snippet in snippets.items():
    cp = subprocess.run([sys.executable, '-c', snippet], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if cp.returncode == 0:
        print(f'{name}=ok')
    else:
        detail = (cp.stderr or cp.stdout).strip().splitlines()[-1] if (cp.stderr or cp.stdout).strip() else 'unavailable'
        print(f'{name}=missing:{detail}')
PY

printf '\n== hestia services ==\n'
systemctl --user show hestia-ai-bridge.service -p ActiveState -p SubState 2>/dev/null || true
systemctl --user show hestia-unmute-voice.service -p ActiveState -p SubState -p Restart -p RestartPreventExitStatus 2>/dev/null || true

printf '\n== hestia sockets ==\n'
for sock in "$runtime_dir/hestia-shell/ai.sock" "$runtime_dir/hestia-shell/assistant.sock"; do
  if [ -S "$sock" ]; then
    printf '%s=socket\n' "$sock"
  else
    printf '%s=missing\n' "$sock"
  fi
done

printf '\n== bridge health ==\n'
curl -fsS --max-time 2 http://127.0.0.1:8765/health 2>/dev/null || echo 'bridge_health=unavailable'
printf '\n'
