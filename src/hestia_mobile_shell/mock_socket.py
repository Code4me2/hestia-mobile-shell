from __future__ import annotations

import argparse
import json
import socket
import stat
import threading
import time
from pathlib import Path
from typing import Iterable, Mapping, Optional

from .demo import load_demo_events


def encode_event(event: Mapping[str, object]) -> bytes:
    """Encode one assistant event as compact newline-delimited JSON."""

    return (json.dumps(dict(event), separators=(",", ":")) + "\n").encode("utf-8")


class MockAssistantSocketServer:
    """Tiny Unix-domain assistant socket server for offline UI testing."""

    def __init__(
        self,
        socket_path: Path | str,
        events: Iterable[Mapping[str, object]],
        interval_seconds: float = 0.9,
        replace_stale: bool = True,
    ) -> None:
        self.socket_path = Path(socket_path)
        self.events = [dict(event) for event in events]
        self.interval_seconds = max(interval_seconds, 0)
        self.replace_stale = replace_stale
        self.subscribe_messages: list[dict[str, object]] = []
        self._server: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._started = threading.Event()
        self._connections: list[socket.socket] = []
        self._subscribers: list[socket.socket] = []
        self._lock = threading.Lock()
        self._bound_device_inode: Optional[tuple[int, int]] = None

    def __enter__(self) -> "MockAssistantSocketServer":
        return self.start()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()

    def start(self) -> "MockAssistantSocketServer":
        self.socket_path.parent.mkdir(parents=True, exist_ok=True)
        self._prepare_socket_path()
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(str(self.socket_path))
        bound_stat = self.socket_path.stat()
        self._bound_device_inode = (bound_stat.st_dev, bound_stat.st_ino)
        server.listen(8)
        server.settimeout(0.1)
        self._server = server
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()
        self._started.wait(timeout=1)
        return self

    def stop(self) -> None:
        self._stop.set()
        if self._server is not None:
            try:
                self._server.close()
            except OSError:
                pass
        for conn in list(self._connections):
            try:
                conn.close()
            except OSError:
                pass
        if self._thread is not None:
            self._thread.join(timeout=1)
        self._unlink_if_owned()

    def _unlink_if_owned(self) -> None:
        if self._bound_device_inode is None:
            return
        try:
            current = self.socket_path.stat()
        except FileNotFoundError:
            return
        if (current.st_dev, current.st_ino) == self._bound_device_inode:
            self.socket_path.unlink()

    def _prepare_socket_path(self) -> None:
        try:
            mode = self.socket_path.stat().st_mode
        except FileNotFoundError:
            return
        if not self.replace_stale:
            raise FileExistsError(str(self.socket_path))
        if not stat.S_ISSOCK(mode):
            raise FileExistsError(f"refusing to replace non-socket path: {self.socket_path}")
        if self._socket_is_live():
            raise FileExistsError(f"refusing to replace live socket: {self.socket_path}")
        self.socket_path.unlink()
        return

    def _socket_is_live(self) -> bool:
        probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            probe.settimeout(0.1)
            probe.connect(str(self.socket_path))
            return True
        except OSError:
            return False
        finally:
            probe.close()

    def _serve(self) -> None:
        self._started.set()
        while not self._stop.is_set():
            try:
                assert self._server is not None
                conn, _addr = self._server.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            self._connections.append(conn)
            threading.Thread(target=self._handle_client, args=(conn,), daemon=True).start()

    def _handle_client(self, conn: socket.socket) -> None:
        subscribed = False
        try:
            subscribed, incoming_events = self._capture_first_frames(conn)
            if not subscribed:
                for event in incoming_events:
                    self._broadcast(event)
                return
            with self._lock:
                self._subscribers.append(conn)
            for event in self.events:
                if self._stop.is_set():
                    return
                conn.sendall(encode_event(event))
                if self.interval_seconds:
                    time.sleep(self.interval_seconds)
            while not self._stop.is_set():
                time.sleep(0.05)
        except OSError:
            return
        finally:
            if subscribed:
                with self._lock:
                    self._subscribers = [subscriber for subscriber in self._subscribers if subscriber is not conn]
            try:
                conn.close()
            except OSError:
                pass

    def _broadcast(self, event: Mapping[str, object]) -> None:
        payload = encode_event(event)
        with self._lock:
            subscribers = list(self._subscribers)
        stale: list[socket.socket] = []
        for subscriber in subscribers:
            try:
                subscriber.sendall(payload)
            except OSError:
                stale.append(subscriber)
        if stale:
            with self._lock:
                self._subscribers = [subscriber for subscriber in self._subscribers if subscriber not in stale]

    def _capture_first_frames(self, conn: socket.socket) -> tuple[bool, list[dict[str, object]]]:
        conn.settimeout(0.5)
        try:
            raw = conn.recv(4096)
        except socket.timeout:
            return False, []
        finally:
            conn.settimeout(None)
        subscribed = False
        incoming_events: list[dict[str, object]] = []
        for line in raw.splitlines():
            if not line.strip():
                continue
            try:
                decoded = json.loads(line.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            if isinstance(decoded, dict):
                if decoded.get("type") == "subscribe":
                    self.subscribe_messages.append(decoded)
                    subscribed = True
                else:
                    incoming_events.append(decoded)
        return subscribed, incoming_events


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a mock Hestia assistant.sock server")
    parser.add_argument("--socket", required=True, help="Unix socket path to bind")
    parser.add_argument("--events", default="examples/demo-events.jsonl", help="JSONL event file to replay")
    parser.add_argument("--interval-ms", type=int, default=900, help="Delay between events per client")
    parser.add_argument("--no-replace-stale", action="store_true", help="Fail instead of replacing stale socket/file path")
    args = parser.parse_args()

    events = load_demo_events(args.events)
    server = MockAssistantSocketServer(
        args.socket,
        events,
        interval_seconds=max(args.interval_ms, 0) / 1000,
        replace_stale=not args.no_replace_stale,
    ).start()
    print(f"mock assistant socket listening at {args.socket} ({len(events)} events)", flush=True)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        server.stop()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
