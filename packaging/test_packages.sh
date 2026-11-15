#!/usr/bin/env bash
# Install, resolve dependencies and start real Qt GUI in disposable containers.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERSION=$(sed -n 's/^version = "\([^"]*\)"/\1/p' "$SCRIPT_DIR/../pyproject.toml")
for image in ubuntu:20.04 ubuntu:22.04 ubuntu:24.04 debian:12-slim debian:13-slim; do
    docker run --rm -v "$SCRIPT_DIR/out:/packages:ro" -e "EXPECTED_VERSION=$VERSION" "$image" bash -ec '
        export DEBIAN_FRONTEND=noninteractive
        apt-get update -qq
        apt-get install -y --no-install-recommends /packages/timetrace_*_amd64.deb dbus
        test "$(timetrace --version)" = "timetrace $EXPECTED_VERSION"
        export QT_QPA_PLATFORM=offscreen
        set +e
        dbus-run-session -- timeout 4 timetrace > /tmp/gui.log 2>&1
        status=$?
        set -e
        test "$status" = 124 || { cat /tmp/gui.log; exit 1; }
    '
done
docker run --rm -v "$SCRIPT_DIR/out:/packages:ro" -e "EXPECTED_VERSION=$VERSION" fedora:latest bash -ec '
    dnf install -y /packages/timetrace-*.rpm dbus-daemon
    test "$(timetrace --version)" = "timetrace $EXPECTED_VERSION"
    export QT_QPA_PLATFORM=offscreen
    set +e
    dbus-run-session -- timeout 4 timetrace > /tmp/gui.log 2>&1
    status=$?
    set -e
    test "$status" = 124 || { cat /tmp/gui.log; exit 1; }
'
docker run --rm -v "$SCRIPT_DIR/out:/packages:ro" -e "EXPECTED_VERSION=$VERSION" archlinux:latest bash -ec '
    pacman -Sy --noconfirm
    pacman -U --noconfirm /packages/timetrace-git-*.pkg.tar.zst
    test "$(timetrace --version)" = "timetrace $EXPECTED_VERSION"
    export QT_QPA_PLATFORM=offscreen
    set +e
    dbus-run-session -- timeout 4 timetrace > /tmp/gui.log 2>&1
    status=$?
    set -e
    test "$status" = 124 || { cat /tmp/gui.log; exit 1; }
'
