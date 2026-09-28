import os
import sys
from collections.abc import Mapping


def system_subprocess_env(env: Mapping[str, str] | None = None) -> dict[str, str] | None:
    """Environment for spawning a system binary (gdbus, gnome-extensions, ...)
    that must resolve its shared libraries against the host, not this app.

    The PyInstaller onefile bootloader points LD_LIBRARY_PATH at its
    extraction dir so the frozen app's own bundled .so files -- built
    against whatever glib/etc. happened to be on the build machine (Debian
    12/glibc 2.36, see packaging/docker/) -- resolve first. A subprocess
    inherits that by default, so e.g. `gdbus` -- the system's own binary,
    linked against the system's (possibly newer) glib -- can end up loading
    the bundled, older glib instead and fail with a symbol lookup error
    (seen on Ubuntu as "undefined symbol: g_string_free_and_steal", added
    in glib 2.76, absent from Debian 12's 2.74). PyInstaller saves the
    pre-bootloader LD_LIBRARY_PATH under LD_LIBRARY_PATH_ORIG specifically
    so it can be restored for cases like this.
    """
    e = env if env is not None else os.environ
    if not getattr(sys, "frozen", False):
        return None
    result = dict(e)
    original = result.pop("LD_LIBRARY_PATH_ORIG", None)
    if original is not None:
        result["LD_LIBRARY_PATH"] = original
    else:
        result.pop("LD_LIBRARY_PATH", None)
    return result
