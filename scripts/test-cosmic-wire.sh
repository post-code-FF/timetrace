#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
fixture=$(mktemp -d)
trap 'test -z "${server:-}" || kill "$server" 2>/dev/null || true; rm -rf "$fixture"' EXIT
for protocol in "$repo"/packaging/protocols/*.xml; do
    name=${protocol##*/}
    name=${name%.xml}
    wayland-scanner server-header "$protocol" "$fixture/$name.h"
    wayland-scanner private-code "$protocol" "$fixture/$name.c"
done
cc -Wall -Wextra -Werror -I "$fixture" "$repo/tests/cosmic-wire-server.c" "$fixture/"*.c \
    $(pkg-config --cflags --libs wayland-server) -o "$fixture/server"
export XDG_RUNTIME_DIR="$fixture" WAYLAND_DISPLAY=cosmic-test PYTHONPATH="$repo/src"
"$fixture/server" &
server=$!
for attempt in {1..50}; do
    [ ! -S "$fixture/cosmic-test" ] || break
    sleep 0.02
done
python - <<'PY'
import time
import threading
from timetrace.backends.idle_kde_wayland import WaylandExtIdleNotifyBackend
from timetrace.backends.window_wayland import WaylandActiveWindowBackend
windows, fullscreen = [], []
idled, resumed = threading.Event(), threading.Event()
idle = WaylandExtIdleNotifyBackend()
idle.start(200, lambda ts: idled.set(), lambda ts: resumed.set())
assert idled.wait(3) and resumed.wait(3), 'KDE idle fallback wire events missing'
backend = WaylandActiveWindowBackend()
backend.start_fullscreen_monitor(lambda full, ts: fullscreen.append(full))
backend.start(lambda app, title, ts: windows.append((app, title)))
try:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if windows and windows[-1][0] == '' and 'org.timetrace.CosmicFixture' in [a for a,t in windows]:
            break
        time.sleep(0.02)
    assert ('org.timetrace.CosmicFixture', 'COSMIC initial') in windows, windows
    assert ('org.timetrace.CosmicFixture', 'Changed before state commit') in windows, windows
    assert windows[-1] == ('', None), windows
    assert fullscreen[-3:] == [True, True, False], fullscreen
    print('PASS: COSMIC v2 wire protocol, metadata/state transactions, focus loss and KDE idle fallback')
finally:
    idle.stop()
    backend.stop()
PY
