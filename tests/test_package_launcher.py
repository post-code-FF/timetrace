import os
from pathlib import Path
import shutil
import subprocess

import pytest


@pytest.mark.parametrize("version,expected", [
    ("2.31", "2.31"), ("2.34", "2.31"), ("2.35", "2.35"),
    ("2.38", "2.35"), ("2.39", "2.39"), ("2.43", "2.39"), ("3.0", "2.39"),
    ("2.30", None), ("musl", None),
])
def test_launcher_selects_compatible_runtime_and_preserves_arguments(tmp_path, version, expected):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    launcher = bin_dir / "timetrace"
    shutil.copy(Path(__file__).parents[1] / "packaging/launcher.sh", launcher)
    launcher.chmod(0o755)
    getconf = bin_dir / "getconf"
    getconf.write_text(f"#!/bin/sh\nprintf '%s\\n' 'glibc {version}'\n")
    getconf.chmod(0o755)
    for runtime in ("2.31", "2.35", "2.39"):
        path = tmp_path / "lib/timetrace" / f"glibc-{runtime}" / "timetrace"
        path.parent.mkdir(parents=True)
        path.write_text(f"#!/bin/sh\nprintf '%s\\n' '{runtime}' \"$@\"\n")
        path.chmod(0o755)
    result = subprocess.run([str(launcher), "--minimized", "two words", ""],
                            capture_output=True, text=True, env=dict(os.environ, PATH=f"{bin_dir}:/usr/bin:/bin"))
    if expected is None:
        assert result.returncode != 0
        assert result.stdout == ""
    else:
        assert result.returncode == 0, result.stderr
        assert result.stdout.splitlines() == [expected, "--minimized", "two words", ""]
