# Desktop support implementation plan

> Execute inline with superpowers:executing-plans and verify before publication.

**Goal:** broad desktop coverage and three automatically configured packages.
**Architecture:** capability-based Wayland adapters, ICCCM fallback, packaged runtimes.
**Tech stack:** Python, PySide6, pywayland, Unix IPC, PyInstaller, Docker, fpm, makepkg.
**Spec:** ../specs/2026-11-15-desktop-support-design.md

## Constraints and review focus

- Preserve user history, settings, package identity and existing bridges.
- Do not invent universal Wayland focus or niri fullscreen information.
- Loss of a socket/bridge clears foreground; shutdown releases resources.
- Desktop-name overrides (LXQt/Budgie with KWin) must select by actual capabilities.
- Unknown protocols fail visibly; no Xwayland shortcut.
- glibc boundaries and argument forwarding must work without Python on the host.

### Task 1: Broad desktop backends

Files: env_detect.py, backends/window_factory.py, idle_factory.py,
window_wayland.py, window_ipc.py, session_cinnamon.py, window_x11.py,
_wayland_protocols/, tests/test_window_wayland.py, test_window_ipc.py,
test_session_cinnamon.py, test_window_x11.py, factory/environment tests.

- [ ] Write and run failing tests for protocol state batches, socket responses,
  Cinnamon idle/lock snapshots, X11 ancestor focus and capability selection.
- [ ] Generate licensed protocol bindings; implement adapters and generic selection.
- [ ] Run full pytest and integration checks, resolve regressions, commit.

### Task 2: Unified installers

Files: packaging/launcher.sh, build scripts, PKGBUILD, Dockerfile,
.github/workflows/linux-release.yml, tests/test_package_launcher.py, versions.
Consumes Task 1 adapters in frozen packages; produces exactly three installers.

- [ ] Write launcher tests at glibc boundaries, unsupported hosts, argument forwarding.
- [ ] Stage all runtimes in every package, declare dependencies, update CI and version.
- [ ] Build three runtimes/packages and run container smoke tests; commit.

### Task 3: Compatibility evidence and release

Files: README.md, docs/compatibility.md, packaging/docker/README.md.

- [ ] Consolidate upstream-backed DE/WM coverage and explicit limitations.
- [ ] Review changes, run full tests and nested compositor checks.
- [ ] Fast-forward main, push, publish v0.1.7 with three installers and checksums.
- [ ] Verify public release assets and clean repository.
