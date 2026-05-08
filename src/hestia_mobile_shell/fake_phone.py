from __future__ import annotations

import argparse
import json
import queue
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional

from .agent_adapter import EVENT_TYPES_BY_VERB, INTERFACE_NAME, SUPPORTED_VERSION

SAFE_ACTIONS_PROTECTED = ["dismiss_card", "close_chat", "close_app_interface"]


class FakePhoneHarness:
    """Offline fake Hestia phone: /mobile_capabilities, /mobile_state, assistant.sock."""

    def __init__(self, root: Path | str, *, protected_mode: str | None = None, port: int = 0) -> None:
        self.root = Path(root)
        self.protected_mode = protected_mode
        self.port = port
        self.assistant_socket = self.root / "hestia-shell" / "assistant.sock"
        self.ai_socket = self.root / "hestia-shell" / "ai.sock"
        self._http: Optional[ThreadingHTTPServer] = None
        self._http_thread: Optional[threading.Thread] = None
        self._socket: Optional[socket.socket] = None
        self._socket_thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._events: queue.Queue[dict[str, object]] = queue.Queue()

    def __enter__(self) -> "FakePhoneHarness":
        return self.start()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()

    @property
    def base_url(self) -> str:
        assert self._http is not None
        return f"http://127.0.0.1:{self._http.server_port}"

    @property
    def capabilities_url(self) -> str:
        return f"{self.base_url}/mobile_capabilities"

    @property
    def state_url(self) -> str:
        return f"{self.base_url}/mobile_state"

    def start(self) -> "FakePhoneHarness":
        self.root.mkdir(parents=True, exist_ok=True)
        self.assistant_socket.parent.mkdir(parents=True, exist_ok=True)
        self.ai_socket.touch()
        self._start_socket()
        self._start_http()
        return self

    def stop(self) -> None:
        self._stop.set()
        if self._http is not None:
            self._http.shutdown()
            self._http.server_close()
        if self._socket is not None:
            try:
                self._socket.close()
            except OSError:
                pass
        if self._http_thread is not None:
            self._http_thread.join(timeout=1)
        if self._socket_thread is not None:
            self._socket_thread.join(timeout=1)
        try:
            self.assistant_socket.unlink()
        except FileNotFoundError:
            pass

    def wait_for_event(self, *, timeout: float) -> dict[str, object] | None:
        try:
            return self._events.get(timeout=timeout)
        except queue.Empty:
            return None

    def capabilities_payload(self) -> dict[str, object]:
        return {
            "interface": INTERFACE_NAME,
            "version": SUPPORTED_VERSION,
            "transport": "local-only",
            "sockets": {"assistant": str(self.assistant_socket), "ai": str(self.ai_socket)},
            "http": {
                "mobile_capabilities": self.capabilities_url,
                "mobile_state": self.state_url,
                "health": f"{self.base_url}/health",
            },
            "visual_verbs": list(EVENT_TYPES_BY_VERB),
            "protected_modes": ["phone_call_active", "offline", "error"],
        }

    def state_payload(self) -> dict[str, object]:
        protected = self.protected_mode is not None
        return {
            "interface": INTERFACE_NAME,
            "version": SUPPORTED_VERSION,
            "assistant_state": "idle" if not protected else self.protected_mode,
            "protected_mode": self.protected_mode,
            "protected": protected,
            "call_active": self.protected_mode == "phone_call_active",
            "online": self.protected_mode not in {"offline", "error"},
            "chat_open": False,
            "app_interface_open": False,
            "visible_cards": [],
            "safe_actions": list(EVENT_TYPES_BY_VERB) if not protected else list(SAFE_ACTIONS_PROTECTED),
        }

    def _start_http(self) -> None:
        harness = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802 - stdlib hook
                if self.path == "/health":
                    self._send({"status": "ok"})
                elif self.path == "/mobile_capabilities":
                    self._send(harness.capabilities_payload())
                elif self.path == "/mobile_state":
                    status = 200 if harness.protected_mode not in {"offline", "error"} else 503
                    self._send(harness.state_payload(), status=status)
                else:
                    self._send({"error": "not_found"}, status=404)

            def log_message(self, format: str, *args: object) -> None:
                return

            def _send(self, payload: dict[str, object], *, status: int = 200) -> None:
                encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

        self._http = ThreadingHTTPServer(("127.0.0.1", self.port), Handler)
        self._http_thread = threading.Thread(target=self._http.serve_forever, daemon=True)
        self._http_thread.start()

    def _start_socket(self) -> None:
        try:
            self.assistant_socket.unlink()
        except FileNotFoundError:
            pass
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(str(self.assistant_socket))
        server.listen(8)
        server.settimeout(0.1)
        self._socket = server
        self._socket_thread = threading.Thread(target=self._serve_socket, daemon=True)
        self._socket_thread.start()

    def _serve_socket(self) -> None:
        while not self._stop.is_set():
            try:
                assert self._socket is not None
                conn, _addr = self._socket.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            with conn:
                payload = conn.recv(65536)
            for line in payload.splitlines():
                try:
                    decoded = json.loads(line.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    continue
                if isinstance(decoded, dict):
                    self._events.put(decoded)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run an offline fake Hestia phone capabilities/state/socket harness")
    parser.add_argument("--root", type=Path, default=Path("/tmp/hestia-fake-phone"))
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--protected-mode", choices=["phone_call_active", "offline", "error"], default=None)
    args = parser.parse_args()
    with FakePhoneHarness(args.root, protected_mode=args.protected_mode, port=args.port) as phone:
        print(f"fake phone capabilities: {phone.capabilities_url}", flush=True)
        print(f"fake phone state:        {phone.state_url}", flush=True)
        print(f"fake assistant socket:   {phone.assistant_socket}", flush=True)
        try:
            while True:
                event = phone.wait_for_event(timeout=3600)
                if event is not None:
                    print(json.dumps(event, separators=(",", ":")), flush=True)
        except KeyboardInterrupt:
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
