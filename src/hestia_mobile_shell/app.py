from __future__ import annotations

import argparse
import os
import threading
from pathlib import Path
from typing import Callable, Mapping, Optional

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from .assistant_socket import AssistantSocketClient
from .demo import iter_demo_events
from .state import MobileShellState, reduce_assistant_event, state_debug_lines


class HestiaMobileCanvas(Gtk.Application):
    def __init__(
        self,
        assistant_socket: Optional[str],
        windowed: bool,
        demo_events: Optional[str] = None,
        demo_interval_ms: int = 1200,
    ) -> None:
        super().__init__(application_id="ai.hestia.MobileShell")
        self.assistant_socket = assistant_socket
        self.windowed = windowed
        self.demo_events = demo_events
        self.demo_interval_ms = demo_interval_ms
        self.state = MobileShellState.initial()
        self.window: Optional[Gtk.ApplicationWindow] = None
        self.status_label: Optional[Gtk.Label] = None
        self.material_label: Optional[Gtk.Label] = None
        self.action_label: Optional[Gtk.Label] = None
        self.debug_label: Optional[Gtk.Label] = None
        self.chat_entry: Optional[Gtk.Entry] = None
        self.app_button: Optional[Gtk.Button] = None
        self.chat_button: Optional[Gtk.Button] = None

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
        self.material_label.get_style_context().add_class("material-card")
        canvas.pack_start(self.material_label, False, False, 0)

        self.action_label = Gtk.Label(label="")
        self.action_label.set_line_wrap(True)
        self.action_label.set_max_width_chars(32)
        self.action_label.get_style_context().add_class("material-actions")
        canvas.pack_start(self.action_label, False, False, 0)

        self.chat_entry = Gtk.Entry()
        self.chat_entry.set_placeholder_text("Type fallback message…")
        self.chat_entry.connect("activate", self._submit_chat_text)
        canvas.pack_start(self.chat_entry, False, False, 0)

        overlay.add(canvas)

        self.debug_label = Gtk.Label(label="")
        self.debug_label.set_halign(Gtk.Align.START)
        self.debug_label.set_valign(Gtk.Align.START)
        self.debug_label.set_margin_start(12)
        self.debug_label.set_margin_top(12)
        self.debug_label.set_line_wrap(True)
        self.debug_label.set_max_width_chars(44)
        self.debug_label.get_style_context().add_class("debug-panel")
        overlay.add_overlay(self.debug_label)

        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        controls.set_halign(Gtk.Align.END)
        controls.set_valign(Gtk.Align.END)
        controls.set_margin_end(18)
        controls.set_margin_bottom(18)

        self.chat_button = Gtk.Button(label="Chat")
        self.chat_button.connect("clicked", self._toggle_chat)
        controls.pack_start(self.chat_button, False, False, 0)

        self.app_button = Gtk.Button(label="Apps")
        self.app_button.connect("clicked", self._toggle_app_interface)
        controls.pack_start(self.app_button, False, False, 0)
        overlay.add_overlay(controls)

        self._install_css()
        self.window.show_all()
        self._render()
        if not self.windowed:
            self.window.fullscreen()

        if self.demo_events:
            start_demo_replay(self.demo_events, self.demo_interval_ms, self._apply_event_from_thread)
        elif self.assistant_socket:
            start_assistant_socket_reader(self.assistant_socket, self._apply_event_from_thread)

    def _install_css(self) -> None:
        provider = Gtk.CssProvider()
        provider.load_from_data(
            b"""
            window { background: #05060a; color: #f5f7ff; }
            label { color: #f5f7ff; font-size: 18px; }
            .title { font-size: 34px; font-weight: 700; letter-spacing: 0.08em; }
            .material-card { background: rgba(255,255,255,0.08); border-radius: 22px; padding: 18px; }
            .material-actions { color: #b8c7ff; font-size: 14px; }
            .debug-panel { background: rgba(30,40,60,0.72); color: #b8c7ff; font-family: monospace; font-size: 11px; border-radius: 12px; padding: 10px; }
            entry { border-radius: 18px; padding: 10px 12px; }
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

    def _toggle_chat(self, _button: Gtk.Button) -> None:
        event_type = "hestia_mobile.close_chat" if self.state.chat_visible else "hestia_mobile.open_chat"
        self._apply_event({"type": event_type})

    def _submit_chat_text(self, entry: Gtk.Entry) -> None:
        text = entry.get_text().strip()
        if text:
            self._apply_event({"type": "hestia_mobile.submit_text", "text": text})
            entry.set_text("")

    def _on_key_press(self, _widget: Gtk.Widget, event: Gdk.EventKey) -> bool:
        if event.keyval == Gdk.KEY_Escape:
            self.quit()
            return True
        if event.keyval == Gdk.KEY_F12:
            self._apply_event({"type": "hestia_mobile.toggle_debug"})
            return True
        return False

    def _apply_event_from_thread(self, event: Mapping[str, object]) -> None:
        GLib.idle_add(self._apply_event, dict(event))

    def _apply_event(self, event: Mapping[str, object]) -> bool:
        self.state = reduce_assistant_event(self.state, event)
        self._render()
        return False

    def _render(self) -> None:
        if (
            self.status_label is None
            or self.material_label is None
            or self.action_label is None
            or self.debug_label is None
            or self.chat_entry is None
            or self.app_button is None
            or self.chat_button is None
        ):
            return
        self.status_label.set_text(self.state.status_text)
        primary = self.state.primary_material
        material = self.state.current_material or ""
        actions = ""
        if primary and primary.actions:
            actions = " · ".join(action.get("label", "") for action in primary.actions if action.get("label"))
        if self.state.mode in {"call_paused", "offline", "error"}:
            material = ""
            actions = ""
        if self.state.tool_status and self.state.mode not in {"call_paused", "offline", "error"} and (not primary or primary.kind != "tool_status"):
            material = f"{material}\n{self.state.tool_status}" if material else self.state.tool_status
        if self.state.chat_visible and self.state.mode not in {"call_paused", "offline", "error"}:
            material = f"Chat fallback\n\n{material}" if material else "Chat fallback"
        if self.state.app_interface_visible and self.state.mode not in {"call_paused", "offline", "error"}:
            material = f"Normal app interface placeholder\n\n{material}" if material else "Normal app interface placeholder"
        self.material_label.set_text(material)
        self.material_label.set_visible(bool(material))
        self.action_label.set_text(actions)
        self.action_label.set_visible(bool(actions))
        self.debug_label.set_text("\n".join(state_debug_lines(self.state)))
        self.debug_label.set_visible(self.state.debug_visible)
        self.chat_entry.set_visible(self.state.chat_visible and self.state.mode not in {"call_paused", "offline", "error"})
        self.chat_button.set_label("Close Chat" if self.state.chat_visible else "Chat")
        self.app_button.set_label("Close Apps" if self.state.app_interface_visible else "Apps")


def start_assistant_socket_reader(
    socket_path: str,
    on_event: CallableEvent,
) -> threading.Thread:
    thread = threading.Thread(
        target=_assistant_socket_reader,
        args=(socket_path, on_event),
        daemon=True,
    )
    thread.start()
    return thread


CallableEvent = Callable[[Mapping[str, object]], None]


def _assistant_socket_reader(
    socket_path: str,
    on_event: CallableEvent,
) -> None:
    for event in AssistantSocketClient(socket_path).iter_events():
        on_event(event)


def start_demo_replay(
    demo_path: str,
    interval_ms: int,
    on_event: CallableEvent,
) -> threading.Thread:
    thread = threading.Thread(
        target=_demo_replay,
        args=(demo_path, interval_ms, on_event),
        daemon=True,
    )
    thread.start()
    return thread


def _demo_replay(demo_path: str, interval_ms: int, on_event: CallableEvent) -> None:
    import time

    interval_seconds = max(interval_ms, 0) / 1000
    for event in iter_demo_events(demo_path):
        on_event(event)
        time.sleep(interval_seconds)


def default_assistant_socket() -> str:
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    return str(Path(runtime_dir) / "hestia-shell" / "assistant.sock")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Hestia Mobile AI canvas prototype")
    parser.add_argument("--assistant-socket", default=default_assistant_socket())
    parser.add_argument("--windowed", action="store_true", help="Run in a normal window instead of fullscreen")
    parser.add_argument("--demo-events", help="Replay newline-delimited JSON events instead of connecting to assistant.sock")
    parser.add_argument("--demo-interval-ms", type=int, default=1200, help="Delay between demo events")
    args = parser.parse_args()

    app = HestiaMobileCanvas(
        args.assistant_socket,
        args.windowed,
        demo_events=args.demo_events,
        demo_interval_ms=args.demo_interval_ms,
    )
    return app.run([])


if __name__ == "__main__":
    raise SystemExit(main())
