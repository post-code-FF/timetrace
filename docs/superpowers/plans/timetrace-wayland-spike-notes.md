# Wayland idle-notify spike outcome

- Date checked: 2026-09-27
- Environment: KDE Plasma, Wayland session (`XDG_SESSION_TYPE=wayland`,
  `WAYLAND_DISPLAY=wayland-0`), kwin 6.7.5.

## Step 1: KWin scripting D-Bus surface

Command:

```
busctl --user introspect org.kde.KWin /Scripting
```

Actual output (relevant excerpt):

```
org.kde.kwin.Scripting              interface -         -            -
.isScriptLoaded                     method    s         b            -
.loadDeclarativeScript              method    s         i            -
.loadDeclarativeScript              method    ss        i            -
.loadScript                         method    s         i            -
.loadScript                         method    ss        i            -
.start                              method    -         -            -
.unloadScript                       method    s         b            -
```

Result: **yes** — `org.kde.kwin.Scripting.loadScript` is present, along with
`start`, `unloadScript`, and `isScriptLoaded`, matching design-time
expectations exactly.

## Step 2: pywayland install and scanner CLI

`pywayland` was already installed in the project venv (via `pyproject.toml`
dependency from Task 1): `pywayland==0.4.19` (satisfies `>=0.4.17`).

`pywayland-scanner` invocation used:

```
venv/bin/pywayland-scanner -i /usr/share/wayland/wayland.xml \
    /usr/share/wayland-protocols/staging/ext-idle-notify/ext-idle-notify-v1.xml \
    -o src/timetrace/_wayland_protocols/
```

Note: passing `-i` with only the `ext-idle-notify-v1.xml` file (as shown as
an "example form" in the task brief) fails, because that protocol's
`get_idle_notification` request takes a `wl_seat` argument and the scanner
needs `wl_seat`'s owning protocol name to generate the cross-module import.
Passing `-i` overrides the scanner's own default input list (which normally
includes `wayland.xml` implicitly), so `wayland.xml` must be listed
explicitly alongside the ext-idle-notify XML. First attempt without it
failed with:

```
KeyError: 'wl_seat'
```

(raised in `pywayland/scanner/interface.py: get_imports`). Adding
`/usr/share/wayland/wayland.xml` as a second `-i` argument fixed this; the
scanner then generated two files:
`src/timetrace/_wayland_protocols/ext_idle_notify_v1.py` (already named as
expected by the brief, containing `ExtIdleNotifierV1`, `ExtIdleNotificationV1`,
and related Proxy/Resource/Global classes) and
`src/timetrace/_wayland_protocols/wayland.py` (generated core `wl_seat` etc.
support module that `ext_idle_notify_v1.py` imports `WlSeat`/`WlSeatProxy`
from). An empty `__init__.py` was added to make the directory an importable
package.

Import verification:

```
$ venv/bin/python -c "
import sys; sys.path.insert(0, 'src')
from timetrace._wayland_protocols.ext_idle_notify_v1 import ExtIdleNotifierV1, ExtIdleNotificationV1
print('import ok', ExtIdleNotifierV1, ExtIdleNotificationV1)
"
import ok <class 'timetrace._wayland_protocols.ext_idle_notify_v1.ExtIdleNotifierV1'> <class 'timetrace._wayland_protocols.ext_idle_notify_v1.ExtIdleNotificationV1'>
```

## Step 4-5: Manual verification script

`scripts/check_wayland_idle.py` written exactly per the brief. Run with a
bounded timeout (no physical mouse movement possible from this environment,
so only the idle half of the cycle was directly observed — see caveat
below):

```
$ timeout 8 venv/bin/python -u scripts/check_wayland_idle.py
watching idle with 3000ms timeout, Ctrl+C to stop
idled
```

(Process was killed by `timeout` after 8s, exit code 124 — expected, since
the script loops on `display.dispatch(block=True)` with no SIGTERM handler.)

An earlier run without `-u` produced no captured output before the timeout
killed the process, due to stdout buffering when not attached to a tty; this
was a buffering artifact of the capture method, not a functional failure —
rerunning with `-u` (unbuffered stdout) showed the real output above.

Result: **`ext_idle_notifier_v1` bound successfully via pywayland: yes**.
The `idled` event fired and printed within the 3000ms timeout window, with
no input sent to the session during the observation window, confirming the
compositor (kwin 6.7.5) implements `ext-idle-notify-v1` and pywayland can
drive it end-to-end (registry bind -> `get_idle_notification` -> dispatched
`idled` event).

`resumed` was **not** physically triggered — this environment has no way to
move a real mouse/keyboard to generate an input event. Per the task's
accepted plan, this is not treated as a blocker: `resumed` is dispatched
through the exact same live `Display`/event-queue connection and the exact
same dispatcher-callback mechanism as `idled` (structurally identical
`notification.dispatcher["resumed"] = lambda n: on_resumed()`), so its
wiring is verified by code symmetry with the proven `idled` path. Full
behavioral coverage of the `resumed` path is deferred to Task 10's automated
unit tests against a fake/mock client.

## Step 6: Rust fallback

**Not needed.** Step 5 succeeded (pywayland bound the protocol and received
a live `idled` event), so the Rust helper under
`packaging/wayland-idle-helper/` was not built.

## Decision

- `org.kde.kwin.Scripting.loadScript` present: **yes**
- pywayland-scanner invocation used:
  `venv/bin/pywayland-scanner -i /usr/share/wayland/wayland.xml /usr/share/wayland-protocols/staging/ext-idle-notify/ext-idle-notify-v1.xml -o src/timetrace/_wayland_protocols/`
- `ext_idle_notifier_v1` bound successfully via pywayland: **yes**
- If no: Rust helper built — **N/A, not needed**
- **Decision: Task 10 uses the pywayland bindings**
  (`src/timetrace/_wayland_protocols/ext_idle_notify_v1.py`), importing
  `ExtIdleNotifierV1` from
  `timetrace._wayland_protocols.ext_idle_notify_v1` as originally planned.
  No Rust subprocess helper is required.
