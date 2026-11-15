#!/usr/bin/env bash
set -euo pipefail
# Run only in the disposable test container, under a non-root user.
export XDG_RUNTIME_DIR
XDG_RUNTIME_DIR=$(mktemp -d)
export WLR_BACKENDS=headless WLR_RENDERER=pixman WLR_LIBINPUT_NO_DEVICES=1
export XDG_SESSION_TYPE=wayland XDG_CURRENT_DESKTOP=sway PYTHONPATH=/source/src
export QT_QPA_PLATFORM="${TIMETRACE_TEST_QPA:-offscreen}"
cat > "$XDG_RUNTIME_DIR/sway.conf" <<'CONFIG'
output HEADLESS-1 resolution 1280x720
seat * fallback true
focus_follows_mouse no
CONFIG
if [ "${1:-sway}" = labwc ]; then
    export XDG_CURRENT_DESKTOP=labwc
    labwc --config-dir "$XDG_RUNTIME_DIR" > "$XDG_RUNTIME_DIR/sway.log" 2>&1 &
else
    sway --unsupported-gpu --config "$XDG_RUNTIME_DIR/sway.conf" > "$XDG_RUNTIME_DIR/sway.log" 2>&1 &
fi
compositor=$!
trap 'kill "$compositor" 2>/dev/null || true; rm -rf "$XDG_RUNTIME_DIR"' EXIT
for attempt in {1..100}; do
    sockets=("$XDG_RUNTIME_DIR"/wayland-*)
    if [ -S "${sockets[0]}" ]; then
        export WAYLAND_DISPLAY=${sockets[0]##*/}
        ipc=("$XDG_RUNTIME_DIR"/sway-ipc.*.sock)
        if [ -S "${ipc[0]}" ]; then export SWAYSOCK=${ipc[0]}; fi
        break
    fi
    kill -0 "$compositor" || { cat "$XDG_RUNTIME_DIR/sway.log"; exit 1; }
    sleep 0.1
done
python scripts/test-wayland-integration.py
if [ -n "${TIMETRACE_FROZEN_BIN:-}" ]; then
    dbus-run-session -- python scripts/test-frozen-wayland.py
fi
