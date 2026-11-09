#!/usr/bin/env bash
set -euo pipefail
fork_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
exec "$fork_root/.venv/bin/python" -m timetrace "$@"
