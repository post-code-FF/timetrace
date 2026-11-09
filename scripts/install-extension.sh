#!/usr/bin/env bash
set -euo pipefail
project_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
extension_root="${XDG_DATA_HOME:-$HOME/.local/share}/gnome-shell/extensions/timetrace@timetrace.app"
mkdir -p -- "$extension_root"
cp -- "$project_root/src/timetrace/assets/gnome_extension/metadata.json" "$project_root/src/timetrace/assets/gnome_extension/extension.js" "$extension_root/"
echo "Installed TimeTrace extension: $extension_root"
echo 'After updating an existing extension, log out and back in to load the new code.'
if ! gnome-extensions enable timetrace@timetrace.app; then
    echo 'GNOME has not discovered the new extension. Log out/in, then run:'
    echo 'gnome-extensions enable timetrace@timetrace.app'
fi
gnome-extensions info timetrace@timetrace.app || true
