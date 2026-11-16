#!/bin/sh
# dpkg supplies the previous configured version only for an upgrade/reinstall.
if [ "${1:-}" = configure ] && [ -n "${2:-}" ]; then
    /usr/bin/timetrace --restart-running || printf '%s\n' 'TimeTrace: automatic restart failed; please restart the application manually.' >&2
fi
exit 0
