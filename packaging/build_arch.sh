#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERSION=$(sed -n 's/^version = "\([^"]*\)"/\1/p' "$SCRIPT_DIR/../pyproject.toml")
BUILD_DIR="$SCRIPT_DIR/arch-build"
mkdir -p "$BUILD_DIR"
cp "$SCRIPT_DIR/PKGBUILD" "$BUILD_DIR/PKGBUILD"
checksum=$(cat "$SCRIPT_DIR/out/deb.sha256")
sed -i "s/^sha256sums=.*/sha256sums=('$checksum')/" "$BUILD_DIR/PKGBUILD"
cp "$SCRIPT_DIR/out/timetrace_${VERSION}_amd64.deb" "$BUILD_DIR/"
if command -v makepkg >/dev/null && command -v fakeroot >/dev/null; then
    (cd "$BUILD_DIR" && makepkg --nodeps --noconfirm --cleanbuild --force)
else
    docker run --rm -v "$BUILD_DIR:/pkg" archlinux:latest bash -ec '
    pacman -Syu --noconfirm --needed fakeroot binutils
    useradd -m builder
    chown -R builder:builder /pkg
    su builder -s /bin/bash -c "cd /pkg && makepkg --nodeps --noconfirm --cleanbuild --force"
    test "$(/pkg/pkg/timetrace-git/usr/bin/timetrace --version)" = "timetrace '"$VERSION"'"
    pacman -Qip /pkg/timetrace-git-*.pkg.tar.zst
'
fi
cp "$BUILD_DIR/"*.pkg.tar.zst "$SCRIPT_DIR/out/"
