#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERSION=$(sed -n 's/^version = "\([^"]*\)"/\1/p' "$SCRIPT_DIR/../pyproject.toml")
OUT_DIR="$SCRIPT_DIR/out"
STAGE_DIR="$SCRIPT_DIR/stage"
for libc in 2.31 2.35 2.39; do
    test -x "$SCRIPT_DIR/dist/runtimes/glibc-$libc/timetrace"
done
command -v fpm >/dev/null
rm -rf "$STAGE_DIR" "$OUT_DIR"
mkdir -p "$STAGE_DIR/usr/bin" "$STAGE_DIR/usr/lib/timetrace" \
    "$STAGE_DIR/usr/share/applications" "$STAGE_DIR/usr/share/icons/hicolor/256x256/apps" \
    "$STAGE_DIR/usr/share/pixmaps" "$OUT_DIR"
install -m755 "$SCRIPT_DIR/launcher.sh" "$STAGE_DIR/usr/bin/timetrace"
cp -a "$SCRIPT_DIR/dist/runtimes/"* "$STAGE_DIR/usr/lib/timetrace/"
install -m644 "$SCRIPT_DIR/timetrace.desktop" "$STAGE_DIR/usr/share/applications/timetrace.desktop"
convert "$SCRIPT_DIR/icon.png" -resize 256x256 "$STAGE_DIR/usr/share/icons/hicolor/256x256/apps/timetrace.png"
cp "$STAGE_DIR/usr/share/icons/hicolor/256x256/apps/timetrace.png" "$STAGE_DIR/usr/share/pixmaps/timetrace.png"
MAINTAINER="${TIMETRACE_MAINTAINER:-Angel04ek-murrmyau <makushinmaksim07@gmail.com>}"
common=(-s dir -n timetrace -v "$VERSION" --license MIT --maintainer "$MAINTAINER"
    --description "Time tracker for Linux desktops on X11 and Wayland"
    --url "https://github.com/post-code-FF/timetrace" -C "$STAGE_DIR")
fpm "${common[@]}" --after-install "$SCRIPT_DIR/deb-postinst.sh" -t deb --architecture amd64 --deb-compression xz \
    -d 'libc6 (>= 2.31)' -d libgl1 -d libegl1 -d libxkbcommon0 -d libxcb1 \
    -d libfontconfig1 -d libfreetype6 -d libdbus-1-3 -d libglib2.0-0 -d libwayland-client0 \
    -p "$OUT_DIR/timetrace_${VERSION}_amd64.deb" .
fpm "${common[@]}" --after-install "$SCRIPT_DIR/rpm-post.sh" -t rpm --architecture x86_64 --rpm-compression xz \
    -d 'glibc >= 2.31' -d 'libGL.so.1()(64bit)' -d 'libEGL.so.1()(64bit)' \
    -d 'libxkbcommon.so.0()(64bit)' -d 'libxcb.so.1()(64bit)' \
    -d 'libfontconfig.so.1()(64bit)' -d 'libfreetype.so.6()(64bit)' \
    -d 'libdbus-1.so.3()(64bit)' -d 'libglib-2.0.so.0()(64bit)' -d 'libwayland-client.so.0()(64bit)' \
    -p "$OUT_DIR/timetrace-${VERSION}-1.x86_64.rpm" .
sha256sum "$OUT_DIR/timetrace_${VERSION}_amd64.deb" | awk '{print $1}' > "$OUT_DIR/deb.sha256"
# Docker builds must leave output writable by the checkout owner.
if [ "$(id -u)" = 0 ]; then
    chown -R --reference="$SCRIPT_DIR/.." "$OUT_DIR" "$STAGE_DIR"
fi
