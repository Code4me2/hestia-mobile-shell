from __future__ import annotations

import argparse
import json
import socket
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Sequence
from urllib.parse import urlparse


INTERFACE_NAME = "hestia-mobile-agent-phone-interface"
SUPPORTED_VERSION = 1
DEFAULT_CAPABILITIES_URL = "http://127.0.0.1:8765/mobile_capabilities"

EVENT_TYPES_BY_VERB = {
    "show_card": "hestia_mobile.show_card",
    "update_card": "hestia_mobile.update_card",
    "dismiss_card": "hestia_mobile.dismiss_card",
    "show_confirmation": "hestia_mobile.show_confirmation",
    "show_tool_status": "hestia_mobile.show_tool_status",
    "open_chat": "hestia_mobile.open_chat",
    "close_chat": "hestia_mobile.close_chat",
    "open_app_interface": "hestia_mobile.open_app_interface",
    "close_app_interface": "hestia_mobile.close_app_interface",
}


class CapabilityError(ValueError):
    """Raised when `/mobile_capabilities` is missing required local contract data."""


class UnsupportedVerbError(ValueError):
    """Raised when an adapter caller asks for a verb not advertised by the phone."""


@dataclass(frozen=True)
class PhoneCapabilities:
    version: int
    assistant_socket: Path
    visual_verbs: set[str]
    protected_modes: tuple[str, ...]


def fetch_capabilities(url: str = DEFAULT_CAPABILITIES_URL, *, timeout: float = 5.0) -> dict[str, object]:
    _require_loopback_url(url, field="capabilities URL")
    with urllib.request.urlopen(url, timeout=timeout) as response:
        payload = response.read().decode("utf-8")
    parsed = json.loads(payload)
    if not isinstance(parsed, dict):
        raise CapabilityError("capabilities response must be a JSON object")
    return parsed


def validate_capabilities(capabilities: Mapping[str, object]) -> PhoneCapabilities:
    if capabilities.get("interface") != INTERFACE_NAME:
        raise CapabilityError(f"capabilities interface must be {INTERFACE_NAME!r}")
    if capabilities.get("version") != SUPPORTED_VERSION:
        raise CapabilityError(f"capabilities version must be {SUPPORTED_VERSION}")
    if capabilities.get("transport") != "local-only":
        raise CapabilityError("capabilities transport must be local-only")

    sockets = capabilities.get("sockets")
    if not isinstance(sockets, Mapping):
        raise CapabilityError("capabilities sockets must be an object with assistant socket")
    assistant_socket = sockets.get("assistant")
    if not isinstance(assistant_socket, str) or not assistant_socket:
        raise CapabilityError("capabilities must include assistant socket")

    http = capabilities.get("http")
    if isinstance(http, Mapping):
        for name, value in http.items():
            if isinstance(value, str):
                _require_loopback_url(value, field=f"http.{name}")

    visual_verbs = capabilities.get("visual_verbs")
    if not isinstance(visual_verbs, list) or not all(isinstance(verb, str) for verb in visual_verbs):
        raise CapabilityError("capabilities visual_verbs must be a list of strings")
    supported = set(visual_verbs)
    unknown = supported - set(EVENT_TYPES_BY_VERB)
    if unknown:
        raise CapabilityError(f"capabilities advertise unsupported visual verbs: {sorted(unknown)}")

    protected_modes = capabilities.get("protected_modes", [])
    if not isinstance(protected_modes, list) or not all(isinstance(mode, str) for mode in protected_modes):
        raise CapabilityError("capabilities protected_modes must be a list of strings")

    return PhoneCapabilities(
        version=SUPPORTED_VERSION,
        assistant_socket=Path(assistant_socket),
        visual_verbs=supported,
        protected_modes=tuple(protected_modes),
    )


class AgentPhoneAdapter:
    def __init__(self, capabilities: PhoneCapabilities, *, capabilities_url: str | None = None):
        self.capabilities = capabilities
        self.capabilities_url = capabilities_url

    @classmethod
    def from_capabilities(cls, capabilities: Mapping[str, object]) -> "AgentPhoneAdapter":
        return cls(validate_capabilities(capabilities))

    @classmethod
    def from_capabilities_url(
        cls,
        url: str = DEFAULT_CAPABILITIES_URL,
        *,
        fetcher: Callable[[str], Mapping[str, object]] | None = None,
    ) -> "AgentPhoneAdapter":
        _require_loopback_url(url, field="capabilities URL")
        fetch = fetcher if fetcher is not None else fetch_capabilities
        return cls(validate_capabilities(fetch(url)), capabilities_url=url)

    def send_event(self, verb: str, event: Mapping[str, object]) -> None:
        self._require_verb(verb)
        expected_type = EVENT_TYPES_BY_VERB[verb]
        if event.get("type") != expected_type:
            raise UnsupportedVerbError(f"visual verb {verb} must send event type {expected_type}")
        payload = (json.dumps(dict(event), separators=(",", ":")) + "\n").encode("utf-8")
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            client.connect(str(self.capabilities.assistant_socket))
            client.sendall(payload)
        finally:
            client.close()

    def show_card(self, *, id: str, title: str, body: str | None = None, priority: int | None = None) -> None:
        self.send_event(
            "show_card",
            _compact({"type": EVENT_TYPES_BY_VERB["show_card"], "id": id, "title": title, "body": body, "priority": priority}),
        )

    def update_card(self, *, id: str, title: str | None = None, body: str | None = None, priority: int | None = None) -> None:
        self.send_event(
            "update_card",
            _compact({"type": EVENT_TYPES_BY_VERB["update_card"], "id": id, "title": title, "body": body, "priority": priority}),
        )

    def dismiss_card(self, *, id: str | None = None) -> None:
        self.send_event("dismiss_card", _compact({"type": EVENT_TYPES_BY_VERB["dismiss_card"], "id": id}))

    def show_confirmation(
        self,
        *,
        id: str,
        title: str,
        body: str | None = None,
        confirm_label: str = "Confirm",
        cancel_label: str = "Cancel",
        priority: int | None = None,
    ) -> None:
        self.send_event(
            "show_confirmation",
            _compact(
                {
                    "type": EVENT_TYPES_BY_VERB["show_confirmation"],
                    "id": id,
                    "title": title,
                    "body": body,
                    "confirm_label": confirm_label,
                    "cancel_label": cancel_label,
                    "priority": priority,
                }
            ),
        )

    def show_tool_status(self, *, name: str, status: str, body: str | None = None, priority: int | None = None) -> None:
        self.send_event(
            "show_tool_status",
            _compact({"type": EVENT_TYPES_BY_VERB["show_tool_status"], "name": name, "status": status, "body": body, "priority": priority}),
        )

    def open_chat(self) -> None:
        self.send_event("open_chat", {"type": EVENT_TYPES_BY_VERB["open_chat"]})

    def close_chat(self) -> None:
        self.send_event("close_chat", {"type": EVENT_TYPES_BY_VERB["close_chat"]})

    def open_app_interface(self) -> None:
        self.send_event("open_app_interface", {"type": EVENT_TYPES_BY_VERB["open_app_interface"]})

    def close_app_interface(self) -> None:
        self.send_event("close_app_interface", {"type": EVENT_TYPES_BY_VERB["close_app_interface"]})

    def _require_verb(self, verb: str) -> None:
        if verb not in self.capabilities.visual_verbs:
            raise UnsupportedVerbError(f"phone interface does not advertise visual verb: {verb}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    adapter = AgentPhoneAdapter.from_capabilities_url(args.capabilities_url)
    _dispatch_cli(adapter, args)
    if not args.quiet:
        print(json.dumps({"sent": args.command, "capabilities_url": args.capabilities_url}, separators=(",", ":")))
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validated agent adapter for the Hestia Mobile phone interface")
    parser.add_argument("--capabilities-url", default=DEFAULT_CAPABILITIES_URL)
    parser.add_argument("--quiet", action="store_true")
    subparsers = parser.add_subparsers(dest="command", required=True)

    show_card = subparsers.add_parser("show-card")
    show_card.add_argument("--id", required=True)
    show_card.add_argument("--title", required=True)
    show_card.add_argument("--body", default=None)
    show_card.add_argument("--priority", type=int, default=None)

    update_card = subparsers.add_parser("update-card")
    update_card.add_argument("--id", required=True)
    update_card.add_argument("--title", default=None)
    update_card.add_argument("--body", default=None)
    update_card.add_argument("--priority", type=int, default=None)

    dismiss_card = subparsers.add_parser("dismiss-card")
    dismiss_card.add_argument("--id", default=None)

    confirmation = subparsers.add_parser("show-confirmation")
    confirmation.add_argument("--id", required=True)
    confirmation.add_argument("--title", required=True)
    confirmation.add_argument("--body", default=None)
    confirmation.add_argument("--confirm-label", default="Confirm")
    confirmation.add_argument("--cancel-label", default="Cancel")
    confirmation.add_argument("--priority", type=int, default=None)

    tool_status = subparsers.add_parser("tool-status")
    tool_status.add_argument("--name", required=True)
    tool_status.add_argument("--status", required=True)
    tool_status.add_argument("--body", default=None)
    tool_status.add_argument("--priority", type=int, default=None)

    subparsers.add_parser("open-chat")
    subparsers.add_parser("close-chat")
    subparsers.add_parser("open-apps")
    subparsers.add_parser("close-apps")
    return parser


def _dispatch_cli(adapter: AgentPhoneAdapter, args: argparse.Namespace) -> None:
    if args.command == "show-card":
        adapter.show_card(id=args.id, title=args.title, body=args.body, priority=args.priority)
    elif args.command == "update-card":
        adapter.update_card(id=args.id, title=args.title, body=args.body, priority=args.priority)
    elif args.command == "dismiss-card":
        adapter.dismiss_card(id=args.id)
    elif args.command == "show-confirmation":
        adapter.show_confirmation(
            id=args.id,
            title=args.title,
            body=args.body,
            confirm_label=args.confirm_label,
            cancel_label=args.cancel_label,
            priority=args.priority,
        )
    elif args.command == "tool-status":
        adapter.show_tool_status(name=args.name, status=args.status, body=args.body, priority=args.priority)
    elif args.command == "open-chat":
        adapter.open_chat()
    elif args.command == "close-chat":
        adapter.close_chat()
    elif args.command == "open-apps":
        adapter.open_app_interface()
    elif args.command == "close-apps":
        adapter.close_app_interface()
    else:
        raise AssertionError(f"unknown command: {args.command}")


def _require_loopback_url(url: str, *, field: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise CapabilityError(f"{field} must be an HTTP loopback URL")
    if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise CapabilityError(f"{field} must use a loopback host")


def _compact(event: Mapping[str, object | None]) -> dict[str, object]:
    return {key: value for key, value in event.items() if value is not None}


if __name__ == "__main__":
    raise SystemExit(main())
