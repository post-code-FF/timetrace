#!/usr/bin/env bash
set -euo pipefail

VERSION="0.1.0"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_DIR="$SCRIPT_DIR/out"
STAGE_DIR="$SCRIPT_DIR/stage"

rm -rf "$STAGE_DIR" "$OUT_DIR"
mkdir -p "$STAGE_DIR/usr/bin" "$STAGE_DIR/usr/share/applications" \
    "$STAGE_DIR/usr/share/icons/hicolor/256x256/apps" "$STAGE_DIR/usr/share/pixmaps" "$OUT_DIR"

cp "$SCRIPT_DIR/dist/timetrace" "$STAGE_DIR/usr/bin/timetrace"
chmod 755 "$STAGE_DIR/usr/bin/timetrace"
cp "$SCRIPT_DIR/timetrace.desktop" "$STAGE_DIR/usr/share/applications/timetrace.desktop"

command -v fpm >/dev/null || {
    echo "fpm not found; install with: gem install --no-document fpm" >&2
    exit 1
}
command -v convert >/dev/null || {
    echo "ImageMagick 'convert' not found; install it to package the app icon" >&2
    exit 1
}

convert "$SCRIPT_DIR/icon.png" -resize 256x256 \
    "$STAGE_DIR/usr/share/icons/hicolor/256x256/apps/timetrace.png"
cp "$STAGE_DIR/usr/share/icons/hicolor/256x256/apps/timetrace.png" \
    "$STAGE_DIR/usr/share/pixmaps/timetrace.png"

fpm -s dir -t deb -n timetrace -v "$VERSION" \
    --description "Time tracker for KDE and GNOME" \
    --license MIT \
    --url "https://github.com/post-code-FF/timetrace" \
    -C "$STAGE_DIR" -p "$OUT_DIR/timetrace_${VERSION}_amd64.deb" .

fpm -s dir -t rpm -n timetrace -v "$VERSION" \
    --description "Time tracker for KDE and GNOME" \
    --license MIT \
    --url "https://github.com/post-code-FF/timetrace" \
    -C "$STAGE_DIR" -p "$OUT_DIR/timetrace-${VERSION}.x86_64.rpm" .

echo "Built:"
ls -la "$OUT_DIR"
