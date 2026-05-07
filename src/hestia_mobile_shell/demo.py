from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable


def load_demo_events(path: Path | str) -> list[dict[str, object]]:
    """Load newline-delimited JSON object events for offline UI replay."""

    demo_path = Path(path)
    events: list[dict[str, object]] = []
    for line_number, line in enumerate(demo_path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        try:
            decoded = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON on line {line_number}: {exc}") from exc
        if not isinstance(decoded, dict):
            raise ValueError(f"demo event on line {line_number} must be a JSON object")
        events.append(decoded)
    return events


def iter_demo_events(path: Path | str) -> Iterable[dict[str, object]]:
    yield from load_demo_events(path)
