#!/usr/bin/env bash
set -euo pipefail
fork_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
extension_root="${XDG_DATA_HOME:-$HOME/.local/share}/gnome-shell/extensions/timetrace-fork@local"
if [[ -e "$extension_root" ]]; then
    echo "Refusing to overwrite $extension_root" >&2
    exit 1
fi
mkdir -p -- "$extension_root"
cp -- "$fork_root/src/timetrace/assets/gnome_extension/metadata.json" "$fork_root/src/timetrace/assets/gnome_extension/extension.js" "$extension_root/"
echo "Installed separate extension: $extension_root"
if ! gnome-extensions enable timetrace-fork@local; then
    echo 'GNOME has not discovered the new extension. Log out/in, then run:'
    echo 'gnome-extensions enable timetrace-fork@local'
fi
gnome-extensions info timetrace-fork@local || true
