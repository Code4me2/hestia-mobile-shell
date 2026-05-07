# Mobile UI Approach Spike

## Current phone facts

The checked phone session is:

```text
PureOS 10 Byzantium
aarch64 Librem 5 kernel
XDG_CURRENT_DESKTOP=Phosh:GNOME
XDG_SESSION_DESKTOP=phosh
XDG_SESSION_TYPE=wayland
phoc + phosh running
```

GTK3 is available. GTK4/libadwaita are not available in the current environment.

## Options

### 1. GTK3 fullscreen app inside Phosh

Pros:

- lowest risk;
- available now;
- easy to launch/kill;
- can subscribe to the assistant socket;
- does not strand the phone if it crashes.

Cons:

- not a true shell replacement;
- app launcher integration is limited at first;
- may not control all surfaces/lockscreen behavior.

### 2. GTK4/libadwaita app

Pros:

- modern GNOME mobile toolkit direction;
- better future fit for adaptive UI.

Cons:

- not installed on the current phone;
- requires system package work before prototyping.

### 3. Phosh plugin/shell integration

Pros:

- better OS integration;
- could expose the bottom-right affordance and overlays more naturally.

Cons:

- more packaging/session risk;
- likely slower iteration;
- requires deeper Phosh internals work.

### 4. Dedicated mobile session/compositor

Pros:

- closest to final Hestia Mobile product direction.

Cons:

- highest risk;
- not appropriate until behavior is validated in a reversible prototype.

## Recommendation

Start with option 1: a GTK3 fullscreen/near-fullscreen app under Phosh. Treat it as the safe AI canvas prototype. Do not replace Phosh yet.

## Safety requirements

- App exits with `Esc`.
- App can run in `--windowed` mode.
- `pkill -f hestia_mobile_shell.app` returns user to Phosh.
- Voice services continue independently of the app.
