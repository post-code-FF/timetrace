# Package upgrade restart Implementation Plan

> **For agentic workers:** Execute inline using superpowers:executing-plans. Steps use checkbox syntax.

**Goal:** Release 0.1.8 with automatic restart of running TimeTrace instances after upgrades of all three Linux packages.
**Architecture:** Shared frozen maintenance entry point discovers packaged processes and starts unprivileged workers; installer lifecycle scripts invoke it after an upgrade.
**Tech Stack:** Python stdlib, Linux procfs, optional systemd user manager, pacman .install, dpkg postinst, RPM post script.
**Spec:** docs/superpowers/specs/2026-11-16-package-restart-design.md

## Global Constraints
- Linux x86_64, glibc >=2.31; no new runtime dependency.
- No root GUI, no SIGKILL, preserve history/config and minimized flag.
- No startup on fresh install or when no packaged copy was running.

## Review Focus
- PID reuse or unrelated executables must never be signaled.
- Frozen parent/child pairs must restart once.
- systemd user service workers must survive replacement of the old service.
- Each target keeps its own graphical/session/XDG environment without frozen-loader contamination.
- Upgrade errors must not fail the package transaction.

### Task 1: Shared maintenance command
Files: src/timetrace/package_restart.py, src/timetrace/__main__.py, tests/test_package_restart.py.
- [x] Write failing tests for packaged discovery, PID identity, parent/child grouping, environment filtering, graceful manual restart, failed shutdown and service dispatch.
- [x] Run targeted tests and observe missing implementation failure.
- [x] Implement discovery, identity verification, user privilege drop and bounded worker; route maintenance arguments before importing Qt.
- [x] Run targeted tests and full pytest suite.

### Task 2: Installers and release
Files: packaging lifecycle scripts, PKGBUILD, build_arch.sh, build_deb_rpm.sh, version declarations, README/changelog.
- [x] Execute lifecycle scripts with controlled external launcher; verify fresh-install vs upgrade behavior and failure isolation.
- [x] Add scripts to all installers and bump to 0.1.8.
- [x] Build and test all three frozen runtimes and packages; run isolated real upgrades with running and closed instances.
Publication: commit, push and publish GitHub assets.

Validation completed: 286 tests passed in each runtime before the final transient-service fallback; 28 targeted lifecycle tests passed including that fallback. Real upgrade from packaged 0.1.7 passed on DEB/RPM/Arch with two users, custom history paths and closed-app cases. User explicitly declined further local testing and requested publication.
