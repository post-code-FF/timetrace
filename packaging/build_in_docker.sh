#!/usr/bin/env bash
# Build all private runtimes; users install one package and never choose a runtime.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
declare -A BASES=([2.31]="ubuntu:20.04" [2.35]="ubuntu:22.04" [2.39]="ubuntu:24.04")
for libc in 2.31 2.35 2.39; do
    image="timetrace-build-glibc-$libc"
    qt_version=6.12.0
    [ "$libc" != 2.31 ] || qt_version=6.9.3
    docker build -f "$SCRIPT_DIR/docker/Dockerfile" --build-arg "BASE_IMAGE=${BASES[$libc]}" --build-arg "PYSIDE_VERSION=$qt_version" -t "$image" "$REPO_ROOT"
    container="$(docker create "$image")"
    trap 'docker rm -f "$container" >/dev/null 2>&1 || true' EXIT
    directory="$SCRIPT_DIR/dist/runtimes/glibc-$libc"
    mkdir -p "$directory"
    docker cp "$container:/build/packaging/dist/timetrace" "$directory/timetrace"
    docker rm -f "$container" >/dev/null
    trap - EXIT
    chmod 755 "$directory/timetrace"
done
