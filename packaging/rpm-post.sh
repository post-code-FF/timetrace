#!/bin/sh
# RPM passes the count of installed package versions: 1=install, 2=upgrade.
if [ "${1:-0}" -gt 1 ]; then
    /usr/bin/timetrace --restart-running || printf '%s\n' 'TimeTrace: automatic restart failed; please restart the application manually.' >&2
fi
exit 0
