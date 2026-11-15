#!/bin/sh
# Keep selection at launch: distribution upgrades need no package reinstall.
set -eu
libc=$(getconf GNU_LIBC_VERSION 2>/dev/null || true)
case "$libc" in
    'glibc '*) version=${libc#glibc } ;;
    *) echo 'TimeTrace requires Linux with glibc >= 2.31 (x86_64).' >&2; exit 1 ;;
esac
major=${version%%.*}
minor=${version#*.}
minor=${minor%%.*}
case "$major:$minor" in
    *[!0-9:]*|:*|*:) echo 'TimeTrace: cannot determine glibc version.' >&2; exit 1 ;;
esac
if [ "$major" -gt 2 ] || { [ "$major" -eq 2 ] && [ "$minor" -ge 39 ]; }; then
    runtime=glibc-2.39
elif [ "$major" -eq 2 ] && [ "$minor" -ge 35 ]; then
    runtime=glibc-2.35
elif [ "$major" -eq 2 ] && [ "$minor" -ge 31 ]; then
    runtime=glibc-2.31
else
    echo 'TimeTrace requires glibc >= 2.31.' >&2
    exit 1
fi
directory=$(CDPATH= cd -- "$(dirname -- "$0")/../lib/timetrace" && pwd)
exec "$directory/$runtime/timetrace" "$@"
