# Hestia Mobile Shell Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Grow the safe GTK3 prototype into a mobile-native AI-primary shell surface for PureOS/Phosh.

**Architecture:** Keep voice/backend/bridge services independent. The visual shell consumes normalized assistant events through the local assistant socket and renders a mostly blank AI canvas with transient material and an explicit app-interface affordance.

**Tech Stack:** Python 3.9, GTK3/PyGObject initially, PureOS/Phosh/phoc Wayland, Unix-domain assistant socket.

**Integration owner repo:** `hestia-mobile`

**Component repos:**
- `hestia-mobile-shell` — mobile visual layer.
- `hestia-mobile` — integration manifest and release gates.
- `hestia-ai-bridge` — socket and health.
- `unmute-streaming-client` — voice client.

**Runtime topology:** phone-local UI consumes `$XDG_RUNTIME_DIR/hestia-shell/assistant.sock`; backend remains `tiny-emerson`.

**Acceptance gates:** tests pass, app launches/kills safely under Phosh, assistant events update UI, normal app access is not blocked.

---

## Task 1: Keep state reducer tested

**Objective:** Make all visual modes derive from tested `MobileShellState` transitions.

**Files:**
- Test: `tests/test_state.py`
- Modify: `src/hestia_mobile_shell/state.py`

**Verification:**

```bash
PYTHONPATH=src python3 -m pytest -q
```

Expected: all tests pass.

## Task 2: Add socket-reader tests

**Objective:** Isolate assistant socket parsing and reconnect/offline behavior from GTK rendering.

**Files:**
- Create: `tests/test_assistant_socket.py`
- Modify: `src/hestia_mobile_shell/app.py` or extract `src/hestia_mobile_shell/assistant_socket.py`

**Verification:** tests cover subscribe frame, newline JSON parsing, malformed frame ignore, offline event on socket failure.

## Task 3: Improve visual prototype styling

**Objective:** Make the prototype visually match the blank calm AI canvas concept.

**Files:**
- Modify: `src/hestia_mobile_shell/app.py`
- Optional: create `src/hestia_mobile_shell/style.css`

**Verification:** launch `--windowed`, inspect, then fullscreen.

## Task 4: Add app-interface affordance behavior

**Objective:** Make the bottom-right affordance open a reversible app-interface placeholder first, then integrate with Phosh/app launcher later.

**Files:**
- Test state behavior in `tests/test_state.py`
- Modify UI rendering.

**Verification:** button toggles state; `Esc` exits.

## Task 5: Integrate with `hestia-mobile`

**Objective:** Add this repo to `hestia-mobile/mobile-stack.json` as optional/experimental and add probe coverage.

**Files in `hestia-mobile` later:**
- `mobile-stack.json`
- `scripts/probe-hestia-mobile-json.py`
- `docs/compatibility-matrix.md`

**Verification:** `hestia-mobile` dry-run and live probes pass.
