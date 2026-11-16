# Restart TimeTrace after package upgrades

Approved behavior: upgrading Arch, DEB or RPM packages gracefully restarts already running packaged instances as their existing users. Closed apps stay closed. Preserve the database and the minimized launch flag. Publish version 0.1.8.

The package manager invokes the new installed launcher in a non-GUI maintenance mode. It discovers only executables from the package's private runtimes, groups PyInstaller parent/child processes, and launches one bounded maintenance worker per running instance after dropping supplementary groups, GID and UID. No user-controlled program runs as root. Workers verify PID/start-time/executable/UID again. Managed user services restart through their user manager; manually launched instances receive SIGTERM and restart only after graceful exit. There is no SIGKILL fallback. Failure is reported without failing the package transaction.

Alternatives: restarting a fixed KDE autostart unit misses manual launches and other desktops. An in-app file watcher cannot restart the existing 0.1.7 app during the first upgrade. Package lifecycle scripts plus a shared frozen maintenance command cover all three installers and the first upgrade without adding a Python dependency.

Constraints: Linux x86_64, glibc >=2.31, no new runtime dependency, no restart on fresh install, no launch as root, no changes to user settings/history. Only packaged copies are restarted; independent source/local copies are outside the package's ownership.
