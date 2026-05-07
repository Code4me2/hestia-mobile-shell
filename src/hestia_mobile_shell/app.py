from __future__ import annotations

import argparse
import json
import os
import socket
import threading
from pathlib import Path
from typing import Callable, Mapping, Optional

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from .state import MobileShellState, reduce_assistant_event


class HestiaMobileCanvas(Gtk.Application):
    def __init__(self, assistant_socket: Optional[str], windowed: bool) -> None:
        super().__init__(application_id="ai.hestia.MobileShell")
        self.assistant_socket = assistant_socket
        self.windowed = windowed
        self.state = MobileShellState.initial()
        self.window: Optional[Gtk.ApplicationWindow] = None
        self.status_label: Optional[Gtk.Label] = None
        self.material_label: Optional[Gtk.Label] = None
        self.app_button: Optional[Gtk.Button] = None

    def do_activate(self) -> None:  # type: ignore[override]
        self.window = Gtk.ApplicationWindow(application=self)
        self.window.set_title("Hestia Mobile")
        self.window.set_default_size(360, 720)
        self.window.connect("key-press-event", self._on_key_press)

        overlay = Gtk.Overlay()
        self.window.add(overlay)

        canvas = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        canvas.set_halign(Gtk.Align.CENTER)
        canvas.set_valign(Gtk.Align.CENTER)
        canvas.set_margin_start(24)
        canvas.set_margin_end(24)
        canvas.set_margin_top(24)
        canvas.set_margin_bottom(24)

        title = Gtk.Label(label="Hestia")
        title.get_style_context().add_class("title")
        canvas.pack_start(title, False, False, 0)

        self.status_label = Gtk.Label(label=self.state.status_text)
        self.status_label.set_line_wrap(True)
        canvas.pack_start(self.status_label, False, False, 0)

        self.material_label = Gtk.Label(label="")
        self.material_label.set_line_wrap(True)
        self.material_label.set_max_width_chars(32)
        canvas.pack_start(self.material_label, False, False, 0)

        overlay.add(canvas)

        self.app_button = Gtk.Button(label="Apps")
        self.app_button.set_halign(Gtk.Align.END)
        self.app_button.set_valign(Gtk.Align.END)
        self.app_button.set_margin_end(18)
        self.app_button.set_margin_bottom(18)
        self.app_button.connect("clicked", self._toggle_app_interface)
        overlay.add_overlay(self.app_button)

        self._install_css()
        self._render()
        self.window.show_all()
        if not self.windowed:
            self.window.fullscreen()

        if self.assistant_socket:
            start_assistant_socket_reader(self.assistant_socket, self._apply_event_from_thread)

    def _install_css(self) -> None:
        provider = Gtk.CssProvider()
        provider.load_from_data(
            b"""
            window { background: #05060a; color: #f5f7ff; }
            label { color: #f5f7ff; font-size: 18px; }
            .title { font-size: 34px; font-weight: 700; letter-spacing: 0.08em; }
            button { border-radius: 999px; padding: 14px 18px; }
            """
        )
        screen = Gdk.Screen.get_default()
        if screen is not None:
            Gtk.StyleContext.add_provider_for_screen(
                screen,
                provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )

    def _toggle_app_interface(self, _button: Gtk.Button) -> None:
        event_type = (
            "hestia_mobile.close_app_interface"
            if self.state.app_interface_visible
            else "hestia_mobile.open_app_interface"
        )
        self._apply_event({"type": event_type})

    def _on_key_press(self, _widget: Gtk.Widget, event: Gdk.EventKey) -> bool:
        if event.keyval == Gdk.KEY_Escape:
            self.quit()
            return True
        return False

    def _apply_event_from_thread(self, event: Mapping[str, object]) -> None:
        GLib.idle_add(self._apply_event, dict(event))

    def _apply_event(self, event: Mapping[str, object]) -> bool:
        self.state = reduce_assistant_event(self.state, event)
        self._render()
        return False

    def _render(self) -> None:
        if self.status_label is None or self.material_label is None or self.app_button is None:
            return
        self.status_label.set_text(self.state.status_text)
        material = self.state.current_material or ""
        if self.state.tool_status:
            material = f"{material}\n{self.state.tool_status}" if material else self.state.tool_status
        if self.state.app_interface_visible:
            material = f"Normal app interface placeholder\n\n{material}" if material else "Normal app interface placeholder"
        self.material_label.set_text(material)
        self.app_button.set_label("Close Apps" if self.state.app_interface_visible else "Apps")


def start_assistant_socket_reader(
    socket_path: str,
    on_event: Callable[[Mapping[str, object]], None],
) -> threading.Thread:
    thread = threading.Thread(
        target=_assistant_socket_reader,
        args=(socket_path, on_event),
        daemon=True,
    )
    thread.start()
    return thread


def _assistant_socket_reader(
    socket_path: str,
    on_event: Callable[[Mapping[str, object]], None],
) -> None:
    path = Path(socket_path)
    if not path.exists():
        on_event({"type": "assistant.state", "state": "offline"})
        return
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.connect(socket_path)
            client.sendall(b'{"type":"subscribe"}\n')
            buffer = b""
            while True:
                chunk = client.recv(4096)
                if not chunk:
                    on_event({"type": "assistant.state", "state": "offline"})
                    return
                buffer += chunk
                while b"\n" in buffer:
                    raw, buffer = buffer.split(b"\n", 1)
                    if not raw.strip():
                        continue
                    try:
                        event = json.loads(raw.decode("utf-8"))
                    except json.JSONDecodeError:
                        continue
                    if isinstance(event, dict):
                        on_event(event)
    except OSError:
        on_event({"type": "assistant.state", "state": "offline"})


def default_assistant_socket() -> str:
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    return str(Path(runtime_dir) / "hestia-shell" / "assistant.sock")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Hestia Mobile AI canvas prototype")
    parser.add_argument("--assistant-socket", default=default_assistant_socket())
    parser.add_argument("--windowed", action="store_true", help="Run in a normal window instead of fullscreen")
    args = parser.parse_args()

    app = HestiaMobileCanvas(args.assistant_socket, args.windowed)
    return app.run([])


if __name__ == "__main__":
    raise SystemExit(main())
