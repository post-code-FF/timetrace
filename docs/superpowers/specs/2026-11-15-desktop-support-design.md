# Desktop support and unified packages

The release must extend TimeTrace to as many Linux desktops and window managers
as their public interfaces permit, without claiming unverified universal support.
The user authorizes implementation, testing, GitHub push and release publication.

## Approach

Use capabilities rather than a growing desktop-name whitelist: EWMH plus ICCCM
input-focus fallback on X11; wlr foreign toplevel management and ext idle notify
on Wayland. Retain GNOME and KWin bridges. Add read-only Cinnamon D-Bus snapshots,
Hyprland/niri IPC fallbacks, COSMIC toplevel information, UKUI KWin service/profile
and legacy KDE idle fallback where available. MangoWM and Phosh use the generic
wlr backend, verified against upstream source; do not equate that with live sessions.
Never fall back to Xwayland for native Wayland focus. Missing interfaces must be
visible and must not continue charging a stale application.

An entirely universal Wayland backend is impossible without compositor support.
Separate installers per desktop duplicate code and cannot solve missing APIs.
Native Python-only distribution packages would exclude distributions lacking
PySide6. Instead retain the existing tested frozen runtimes inside each installer
and select by host glibc at launch, allowing desktop changes after installation.

## Packaging

Publish exactly three installable x86_64 packages: deb, rpm, Arch pkg.tar.zst.
Each contains /usr/bin/timetrace launcher, private runtimes built on Ubuntu
20.04/22.04/24.04, icon and desktop entry. The launcher selects the newest runtime
compatible with host glibc (2.31/2.35/2.39). Declare system library dependencies;
never run desktop integration from root package installation scripts. Keep the
existing Arch package identity timetrace-git to preserve upgrades. SHA256SUMS is
auxiliary release metadata, not a fourth installer.

## Validation and limits

Test real socket framing, decoding, focus loss, disconnect/reconnect, shutdown,
idle/fullscreen transitions, X11 focus ancestors and runtime selection boundaries.
Build all runtimes and installers, inspect/extract/install packages in isolated
containers and run frozen version/Qt startup checks on old and current systems.
Use nested compositors where available. Document tested environments separately
from protocol-based compatibility, with links to upstream sources and OpenNET
inventory. No fabricated support claims or artificial fullscreen inference.
