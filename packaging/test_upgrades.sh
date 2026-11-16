#!/usr/bin/env bash
# Real package transactions with old frozen apps, in disposable containers.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BASELINE_DIR="${TIMETRACE_UPGRADE_BASELINE_DIR:-$SCRIPT_DIR/upgrade-baseline}"
mkdir -p "$BASELINE_DIR"
for name in timetrace_0.1.7_amd64.deb timetrace-0.1.7-1.x86_64.rpm timetrace-git-0.1.7-1-x86_64.pkg.tar.zst; do
    if [ ! -f "$BASELINE_DIR/$name" ]; then
        curl --fail --location --retry 2 -o "$BASELINE_DIR/$name" "https://github.com/post-code-FF/timetrace/releases/download/v0.1.7/$name"
    fi
done
mounts=(-v "$ROOT_DIR:/source:ro" -v "$BASELINE_DIR:/old-packages:ro" -v "$SCRIPT_DIR/out:/new-packages:ro")
docker run --rm --cap-add SYS_PTRACE "${mounts[@]}" "${TIMETRACE_TEST_DEB_IMAGE:-debian:12-slim}" bash -ec '
    apt-get update -qq
    apt-get install -y --no-install-recommends python3 dbus /old-packages/*.deb
    PYTHONPATH=/source/src python3 /source/scripts/test-package-upgrade.py deb
'
docker run --rm --cap-add SYS_PTRACE "${mounts[@]}" "${TIMETRACE_TEST_RPM_IMAGE:-fedora:latest}" bash -ec '
    dnf install -y python3 dbus-daemon /old-packages/*.rpm
    PYTHONPATH=/source/src python3 /source/scripts/test-package-upgrade.py rpm
'
docker run --rm --cap-add SYS_PTRACE "${mounts[@]}" "${TIMETRACE_TEST_ARCH_IMAGE:-archlinux:latest}" bash -ec '
    pacman -Syu --noconfirm --needed python dbus
    PYTHONPATH=/source/src python /source/scripts/test-package-upgrade.py arch
'
