from __future__ import annotations

import argparse
import json
import os
import socket
from pathlib import Path
from typing import Mapping, Sequence


def default_assistant_socket() -> Path:
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    return Path(runtime_dir) / "hestia-shell" / "assistant.sock"


def build_event(argv: Sequence[str]) -> dict[str, object]:
    parser = _build_parser(include_socket=False)
    args = parser.parse_args(list(argv))
    return _event_from_args(parser, args)


def send_event(socket_path: Path | str, event: Mapping[str, object]) -> None:
    payload = (json.dumps(dict(event), separators=(",", ":")) + "\n").encode("utf-8")
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        client.connect(str(socket_path))
        client.sendall(payload)
    finally:
        client.close()


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser(include_socket=True)
    args = parser.parse_args(list(argv) if argv is not None else None)
    event = _event_from_args(parser, args)
    send_event(args.socket, event)
    if not args.quiet:
        print(json.dumps(event, separators=(",", ":")))
    return 0


def _build_parser(include_socket: bool) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Send one Hestia Mobile shell event to assistant.sock")
    if include_socket:
        parser.add_argument("--socket", type=Path, default=default_assistant_socket(), help="assistant.sock path")
        parser.add_argument("--quiet", action="store_true", help="Do not print the sent event")
    subparsers = parser.add_subparsers(dest="command", required=True)

    show_card = subparsers.add_parser("show-card", help="Show or replace a visual material card")
    show_card.add_argument("--id", required=True)
    show_card.add_argument("--title", required=True)
    show_card.add_argument("--body", default=None)
    show_card.add_argument("--priority", type=int, default=None)

    update_card = subparsers.add_parser("update-card", help="Update fields on a visual material card")
    update_card.add_argument("--id", required=True)
    update_card.add_argument("--title", default=None)
    update_card.add_argument("--body", default=None)
    update_card.add_argument("--priority", type=int, default=None)

    dismiss_card = subparsers.add_parser("dismiss-card", help="Dismiss one card or all cards")
    dismiss_card.add_argument("--id", default=None)

    confirmation = subparsers.add_parser("show-confirmation", help="Show a constrained confirmation card")
    confirmation.add_argument("--id", required=True)
    confirmation.add_argument("--title", required=True)
    confirmation.add_argument("--body", default=None)
    confirmation.add_argument("--confirm-label", default="Confirm")
    confirmation.add_argument("--cancel-label", default="Cancel")
    confirmation.add_argument("--priority", type=int, default=None)

    tool_status = subparsers.add_parser("tool-status", help="Show or update tool progress")
    tool_status.add_argument("--name", required=True)
    tool_status.add_argument("--status", required=True)
    tool_status.add_argument("--body", default=None)
    tool_status.add_argument("--priority", type=int, default=None)

    state = subparsers.add_parser("state", help="Set assistant lifecycle state")
    state.add_argument("state", choices=["idle", "listening", "thinking", "speaking", "interrupted", "offline", "error"])

    subparsers.add_parser("call-active", help="Enter phone-call protected mode")
    subparsers.add_parser("call-inactive", help="Leave phone-call protected mode")
    subparsers.add_parser("open-apps", help="Open normal app interface placeholder")
    subparsers.add_parser("close-apps", help="Close normal app interface placeholder")
    subparsers.add_parser("toggle-debug", help="Toggle debug/event journal overlay")
    set_debug = subparsers.add_parser("set-debug", help="Set debug/event journal overlay visibility")
    set_debug.add_argument("visible", choices=["on", "off", "true", "false", "1", "0"])
    subparsers.add_parser("clear-events", help="Clear debug event journal")
    subparsers.add_parser("open-chat", help="Open chat fallback surface")
    subparsers.add_parser("close-chat", help="Close chat fallback surface")
    text = subparsers.add_parser("text", help="Submit one fallback text message")
    text.add_argument("text")

    raw = subparsers.add_parser("raw", help="Send a raw JSON object event")
    raw.add_argument("json_event")

    return parser


def _event_from_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> dict[str, object]:
    command = args.command
    if command == "show-card":
        return _compact(
            {
                "type": "hestia_mobile.show_card",
                "id": args.id,
                "title": args.title,
                "body": args.body,
                "priority": args.priority,
            }
        )
    if command == "update-card":
        return _compact(
            {
                "type": "hestia_mobile.update_card",
                "id": args.id,
                "title": args.title,
                "body": args.body,
                "priority": args.priority,
            }
        )
    if command == "dismiss-card":
        return _compact({"type": "hestia_mobile.dismiss_card", "id": args.id})
    if command == "show-confirmation":
        return _compact(
            {
                "type": "hestia_mobile.show_confirmation",
                "id": args.id,
                "title": args.title,
                "body": args.body,
                "confirm_label": args.confirm_label,
                "cancel_label": args.cancel_label,
                "priority": args.priority,
            }
        )
    if command == "tool-status":
        return _compact(
            {
                "type": "hestia_mobile.show_tool_status",
                "name": args.name,
                "status": args.status,
                "body": args.body,
                "priority": args.priority,
            }
        )
    if command == "state":
        return {"type": "assistant.state", "state": args.state}
    if command == "call-active":
        return {"type": "assistant.availability", "available": False, "reason": "phone_call_active"}
    if command == "call-inactive":
        return {"type": "assistant.availability", "available": True, "reason": "phone_call_inactive"}
    if command == "open-apps":
        return {"type": "hestia_mobile.open_app_interface"}
    if command == "close-apps":
        return {"type": "hestia_mobile.close_app_interface"}
    if command == "toggle-debug":
        return {"type": "hestia_mobile.toggle_debug"}
    if command == "set-debug":
        return {"type": "hestia_mobile.set_debug", "visible": args.visible in {"on", "true", "1"}}
    if command == "clear-events":
        return {"type": "hestia_mobile.clear_event_journal"}
    if command == "open-chat":
        return {"type": "hestia_mobile.open_chat"}
    if command == "close-chat":
        return {"type": "hestia_mobile.close_chat"}
    if command == "text":
        return {"type": "hestia_mobile.submit_text", "text": args.text}
    if command == "raw":
        try:
            event = json.loads(args.json_event)
        except json.JSONDecodeError as exc:
            parser.error(f"raw JSON event is invalid: {exc}")
        if not isinstance(event, dict):
            parser.error("raw JSON event must be an object")
        return dict(event)
    parser.error(f"unknown command: {command}")
    raise AssertionError("unreachable")


def _compact(event: Mapping[str, object | None]) -> dict[str, object]:
    return {key: value for key, value in event.items() if value is not None}


if __name__ == "__main__":
    raise SystemExit(main())
