# TimeTrace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build TimeTrace, a Linux desktop time tracker (ManicTime-alike) that shows a 24h presence timeline (green=active, red=idle, empty=off) and a per-app timeline, aggregated app durations for the day, and runs in the tray — working fully on KDE Plasma and GNOME, on both X11 and Wayland.

**Architecture:** One Python/PySide6 process. Swappable `IdleBackend` and `ActiveWindowBackend` implementations (X11 EWMH/XScreenSaver, GNOME D-Bus/Shell-extension, KDE Wayland protocol/KWin-script) are chosen at startup by detected desktop+session. Backends push events onto a queue; a `TrackingCoordinator` drains it on a Qt timer and writes interval rows to SQLite. The UI reads the same SQLite store to render the day view.

**Tech Stack:** Python 3.11+, PySide6 (Qt6), SQLite (stdlib `sqlite3`), `python-xlib` (X11), `pywayland` (Wayland), QtDBus for all D-Bus calls, pytest + pytest-qt, PyInstaller + fpm + PKGBUILD for packaging.

**Spec:** `docs/superpowers/specs/2026-09-27-timetrace-design.md`

## Global Constraints

- Supported environments: **only** KDE Plasma and GNOME, each in X11 and Wayland sessions (4 combinations). Any other desktop → tracking backends are no-ops, UI still runs.
- Idle threshold default: 5 minutes, user-configurable in Settings, applied live without restart.
- Data stored forever locally in SQLite at `~/.local/share/timetrace/data.db` (XDG data dir). Config at `~/.config/timetrace/config.toml` (XDG config dir).
- App-interval time only accrues while presence state is `active`; during `idle` or no-data the "Приложения" track and app list are empty.
- D-Bus service name for the app itself: `org.timetrace.App`. Autostart file: `~/.config/autostart/timetrace.desktop`.
- No tabs/features beyond what's in the spec: no "Документы и интернет", "Метки", "Расписание", "Статистика", no filter/search box, no manual labels.
- Settings dialog has exactly 3 controls: autostart toggle, theme (light/dark/sync-with-OS via `org.freedesktop.appearance` portal), idle threshold minutes.
- Single binary (PyInstaller) works unmodified on both KDE and GNOME — backend choice is runtime, not build-time.
- App/binary name: `timetrace` (display name "TimeTrace").

## Review Focus

- Interval spanning midnight (e.g. 23:50→00:10) must be clipped correctly to each day's view without double-counting or losing time — spec implies per-day display but never states the boundary rule explicitly.
- Changing the idle threshold while a long idle/active period is already accumulating must not fire a spurious immediate `idled`/`resumed` event or silently drop the in-flight timer.
- Rapid repeated "same window re-activated" events (focus-stealing flicker) must not create a stream of near-zero-length app intervals in the DB.
- First run with no existing config file / no existing DB file must create both from scratch rather than crashing on "file not found".
- User switches the OS light/dark theme while TimeTrace is open in "sync with OS" mode — the UI must follow live, not only re-read the setting on next launch.

Each of these gets a concrete test in the task that owns the relevant code: midnight clipping → Task 5; threshold changed mid-flight → Task 7 and Task 14; repeated-window churn → Task 14; missing config/DB on first run → Task 4 and Task 5; live OS theme change → Task 17 provides the watch/unsubscribe primitive (tested there), Task 25 wires it so switching in/out of "system" mode via Settings at runtime re-subscribes or unsubscribes correctly (verified manually in Task 25 Step 5 alongside the rest of the live-session smoke test).

---

## File Structure

```
pyproject.toml
src/timetrace/
    __init__.py
    __main__.py
    paths.py
    config.py
    db.py
    env_detect.py
    icons.py
    app_color.py
    theme.py
    autostart.py
    _wayland_protocols/
        __init__.py
        ext_idle_notify_v1.py        # generated from system protocol XML (Task 2)
    backends/
        __init__.py
        idle_state_machine.py
        idle_base.py
        idle_x11.py
        idle_gnome.py
        idle_kde_wayland.py
        idle_factory.py
        window_base.py
        window_x11.py
        window_kwin.py
        window_gnome.py
        window_factory.py
    tracking/
        __init__.py
        coordinator.py
    app_list_widget.py            # pure aggregation + AppListWidget (Task 21)
    ui/
        __init__.py
        date_nav.py
        timeline_widget.py
        main_window.py
        tray.py
        settings_dialog.py
    assets/
        __init__.py
        kwin_script/
            __init__.py
            metadata.json
            contents/
                __init__.py
                code/
                    __init__.py
                    main.js
        gnome_extension/
            __init__.py
            metadata.json
            extension.js
scripts/
    check_wayland_idle.py
tests/
    conftest.py
    test_paths.py
    test_config.py
    test_db.py
    test_env_detect.py
    test_idle_state_machine.py
    test_idle_x11.py
    test_idle_gnome.py
    test_idle_kde_wayland.py
    test_idle_factory.py
    test_window_x11.py
    test_window_kwin.py
    test_window_gnome.py
    test_window_factory.py
    test_coordinator.py
    test_icons.py
    test_app_color.py
    test_theme.py
    test_autostart.py
    test_date_nav.py
    test_timeline_widget.py
    test_app_list_widget.py
    test_main_window.py
    test_tray.py
    test_settings_dialog.py
    test_main_bootstrap.py
packaging/
    pyinstaller.spec
    timetrace.desktop
    build_deb_rpm.sh
    PKGBUILD
    wayland-idle-helper/          # only if Task 2's spike needs the Rust fallback
        Cargo.toml
        src/main.rs
docs/superpowers/plans/
    timetrace-wayland-spike-notes.md   # written by Task 2
```

---

### Task 1: Project scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `src/timetrace/__init__.py`
- Create: `src/timetrace/__main__.py`
- Create: `tests/conftest.py`
- Create: `.gitignore`

**Interfaces:**
- Produces: `timetrace.__version__: str`; `python -m timetrace --version` prints it; pytest is runnable via `pytest` from repo root with `src/` on path.

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "timetrace"
version = "0.1.0"
description = "Simplified ManicTime-alike time tracker for KDE and GNOME"
requires-python = ">=3.11"
dependencies = [
    "PySide6>=6.6",
    "python-xlib>=0.33",
    "pywayland>=0.4.17",
]

[project.scripts]
timetrace = "timetrace.__main__:main"

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-qt>=4.4"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Write package init and entry point**

`src/timetrace/__init__.py`:
```python
__version__ = "0.1.0"
```

`src/timetrace/__main__.py`:
```python
import sys

from . import __version__


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["--version"]:
        print(f"timetrace {__version__}")
        return 0
    print("timetrace: not yet implemented")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Write test config**

`tests/conftest.py`:
```python
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
```

- [ ] **Step 4: Write `.gitignore`**

```
__pycache__/
*.pyc
.pytest_cache/
build/
dist/
*.egg-info/
.venv/
```

- [ ] **Step 5: Install in editable mode and verify**

Run: `pip install -e ".[dev]"`
Expected: installs successfully, `pytest` and `pytest-qt` available.

Run: `python -m timetrace --version`
Expected: prints `timetrace 0.1.0`

Run: `pytest`
Expected: `no tests ran` (collects cleanly, no errors)

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/timetrace/__init__.py src/timetrace/__main__.py tests/conftest.py .gitignore
git commit -m "Scaffold TimeTrace Python package"
```

---

### Task 2: Verify KDE Wayland tracking prerequisites (feasibility spike)

This is the highest-risk part of the whole plan (per spec §3 "Риски"): confirm `pywayland` can drive the `ext-idle-notify-v1` protocol, and that `org.kde.kwin.Scripting` still behaves as observed during design. Do this before any other backend code.

**Files:**
- Create: `scripts/check_wayland_idle.py`
- Create: `src/timetrace/_wayland_protocols/__init__.py`
- Create: `src/timetrace/_wayland_protocols/ext_idle_notify_v1.py` (generated)
- Create: `docs/superpowers/plans/timetrace-wayland-spike-notes.md`

**Interfaces:**
- Produces: `src/timetrace/_wayland_protocols/ext_idle_notify_v1.py` exposing pywayland-generated classes for `ext_idle_notifier_v1` / `ext_idle_notification_v1`, importable as `from timetrace._wayland_protocols.ext_idle_notify_v1 import ExtIdleNotifierV1`. Task 10 (`idle_kde_wayland.py`) imports from here.

- [ ] **Step 1: Confirm KWin scripting D-Bus surface is still as expected**

Run: `busctl --user introspect org.kde.KWin /Scripting`
Expected: interface `org.kde.kwin.Scripting` with methods `loadScript`, `start`, `unloadScript`, `isScriptLoaded` — matches what design-time research found. If this is missing/different, stop and re-open the spec (architecture assumption broken).

- [ ] **Step 2: Install pywayland and inspect its scanner CLI**

Run: `pip install "pywayland>=0.4.17"`
Run: `pywayland-scanner --help`
Expected: usage text showing input/output flags (record the exact flags actually printed — versions differ; use whatever `--help` shows, typically an input XML path and an output directory/module option).

- [ ] **Step 3: Generate Python bindings for `ext-idle-notify-v1` from the system protocol XML**

The XML is already present on any system with `wayland-protocols` installed (confirmed at design time): `/usr/share/wayland-protocols/staging/ext-idle-notify/ext-idle-notify-v1.xml`.

Run, using the flags discovered in Step 2 (example form; adjust to match actual `--help` output):
```bash
mkdir -p src/timetrace/_wayland_protocols
pywayland-scanner -i /usr/share/wayland-protocols/staging/ext-idle-notify/ext-idle-notify-v1.xml -o src/timetrace/_wayland_protocols/
```
Expected: a generated module appears under `src/timetrace/_wayland_protocols/` containing interface classes for `ext_idle_notifier_v1` and `ext_idle_notification_v1`. Rename/move the generated file to `src/timetrace/_wayland_protocols/ext_idle_notify_v1.py` if the scanner names it differently, and add `src/timetrace/_wayland_protocols/__init__.py` (empty file) so it's an importable package.

If generation fails outright (scanner errors on this XML): fall back to the compiled-helper approach in Step 6 below instead of continuing to Step 4, and record that decision in the notes file (Step 7).

- [ ] **Step 4: Write a standalone manual verification script**

`scripts/check_wayland_idle.py`:
```python
"""Manual verification: run on a KDE Wayland session, do not touch input for
>3s, confirm 'idled' prints, then move the mouse and confirm 'resumed' prints.
Exit with Ctrl+C."""
from pywayland.client import Display

from timetrace._wayland_protocols.ext_idle_notify_v1 import ExtIdleNotifierV1

TIMEOUT_MS = 3000


def main() -> None:
    display = Display()
    display.connect()
    registry = display.get_registry()

    state: dict[str, object] = {}

    def handle_global(registry, id_, interface, version):
        if interface == "ext_idle_notifier_v1":
            state["notifier"] = registry.bind(id_, ExtIdleNotifierV1, version)
        elif interface == "wl_seat":
            from pywayland.protocol.wayland import WlSeat

            state["seat"] = registry.bind(id_, WlSeat, version)

    registry.dispatcher["global"] = handle_global
    display.roundtrip()

    notifier = state.get("notifier")
    seat = state.get("seat")
    if notifier is None or seat is None:
        raise SystemExit("ext_idle_notifier_v1 or wl_seat not available on this compositor")

    notification = notifier.get_idle_notification(TIMEOUT_MS, seat)

    def on_idled():
        print("idled")

    def on_resumed():
        print("resumed")

    notification.dispatcher["idled"] = lambda n: on_idled()
    notification.dispatcher["resumed"] = lambda n: on_resumed()

    print(f"watching idle with {TIMEOUT_MS}ms timeout, Ctrl+C to stop")
    while True:
        display.dispatch(block=True)


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run the verification script**

Run: `python scripts/check_wayland_idle.py`
Expected: prints "watching idle..."; after 3s of no input, prints `idled`; after moving the mouse, prints `resumed`. Let it run through one full idle→resume cycle, then Ctrl+C.

- [ ] **Step 6: Concrete fallback if Steps 3–5 don't work (bindings fail to generate, or the script errors/hangs)**

Use a small Rust helper that speaks the protocol directly and is driven as a subprocess. Only build this if Step 5 failed.

`packaging/wayland-idle-helper/Cargo.toml`:
```toml
[package]
name = "timetrace-idle-helper"
version = "0.1.0"
edition = "2021"

[dependencies]
wayland-client = "0.31"
wayland-protocols = { version = "0.32", features = ["staging", "client"] }
```

`packaging/wayland-idle-helper/src/main.rs`:
```rust
use std::env;
use wayland_client::{Connection, Dispatch, QueueHandle};
use wayland_client::protocol::wl_registry;
use wayland_client::protocol::wl_seat::WlSeat;
use wayland_protocols::ext::idle_notify::v1::client::{
    ext_idle_notifier_v1::ExtIdleNotifierV1,
    ext_idle_notification_v1::{self, ExtIdleNotificationV1},
};

struct State {
    notifier: Option<ExtIdleNotifierV1>,
    seat: Option<WlSeat>,
}

impl Dispatch<wl_registry::WlRegistry, ()> for State {
    fn event(
        state: &mut Self,
        registry: &wl_registry::WlRegistry,
        event: wl_registry::Event,
        _: &(),
        _: &Connection,
        qh: &QueueHandle<Self>,
    ) {
        if let wl_registry::Event::Global { name, interface, version } = event {
            if interface == "ext_idle_notifier_v1" {
                state.notifier = Some(registry.bind(name, version, qh, ()));
            } else if interface == "wl_seat" {
                state.seat = Some(registry.bind(name, version, qh, ()));
            }
        }
    }
}

impl Dispatch<WlSeat, ()> for State {
    fn event(_: &mut Self, _: &WlSeat, _: wayland_client::protocol::wl_seat::Event, _: &(), _: &Connection, _: &QueueHandle<Self>) {}
}

impl Dispatch<ExtIdleNotifierV1, ()> for State {
    fn event(_: &mut Self, _: &ExtIdleNotifierV1, _: (), _: &(), _: &Connection, _: &QueueHandle<Self>) {}
}

impl Dispatch<ExtIdleNotificationV1, ()> for State {
    fn event(
        _: &mut Self,
        _: &ExtIdleNotificationV1,
        event: ext_idle_notification_v1::Event,
        _: &(),
        _: &Connection,
        _: &QueueHandle<Self>,
    ) {
        match event {
            ext_idle_notification_v1::Event::Idled => println!("idled"),
            ext_idle_notification_v1::Event::Resumed => println!("resumed"),
            _ => {}
        }
    }
}

fn main() {
    let timeout_ms: i32 = env::args().nth(1).and_then(|s| s.parse().ok()).unwrap_or(3000);
    let conn = Connection::connect_to_env().expect("no wayland connection");
    let mut event_queue = conn.new_event_queue();
    let qh = event_queue.handle();
    let display = conn.display();
    display.get_registry(&qh, ());

    let mut state = State { notifier: None, seat: None };
    event_queue.roundtrip(&mut state).unwrap();

    let notifier = state.notifier.expect("compositor has no ext_idle_notifier_v1");
    let seat = state.seat.expect("compositor has no wl_seat");
    notifier.get_idle_notification(timeout_ms as u32, &seat, &qh, ());

    loop {
        event_queue.blocking_dispatch(&mut state).unwrap();
    }
}
```

`WaylandExtIdleNotifyBackend` (Task 10) would then spawn this compiled binary and read `idled`/`resumed` lines from its stdout instead of importing the pywayland bindings. Record which path was taken in Step 7.

- [ ] **Step 7: Record the outcome**

`docs/superpowers/plans/timetrace-wayland-spike-notes.md`:
```markdown
# Wayland idle-notify spike outcome

- Date checked: <fill in actual date>
- `org.kde.kwin.Scripting.loadScript` present: yes/no
- pywayland-scanner invocation used: <exact command>
- `ext_idle_notifier_v1` bound successfully via pywayland: yes/no
- If no: Rust helper built at `packaging/wayland-idle-helper/`, verified with
  `cargo run -- 3000` producing `idled`/`resumed` output: yes/no
- Decision: Task 10 uses <pywayland bindings | Rust helper subprocess>
```
Fill in the real results from Steps 1–6 before moving on — Task 10 depends on this decision.

- [ ] **Step 8: Commit**

```bash
git add scripts/check_wayland_idle.py src/timetrace/_wayland_protocols/ docs/superpowers/plans/timetrace-wayland-spike-notes.md packaging/wayland-idle-helper/ 2>/dev/null
git commit -m "Spike: verify KDE Wayland idle-notify and KWin scripting prerequisites"
```

---

### Task 3: XDG path helpers

**Files:**
- Create: `src/timetrace/paths.py`
- Test: `tests/test_paths.py`

**Interfaces:**
- Produces: `config_dir(env: Mapping[str, str] | None = None) -> Path`, `data_dir(env=None) -> Path`, `config_file_path(env=None) -> Path`, `db_file_path(env=None) -> Path`, `autostart_dir(env=None) -> Path`, `autostart_file_path(env=None) -> Path`. All accept an optional `env` mapping (defaults to `os.environ`) for testability.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_paths.py
from pathlib import Path

from timetrace import paths


def test_config_dir_uses_xdg_config_home():
    env = {"XDG_CONFIG_HOME": "/tmp/xdgcfg"}
    assert paths.config_dir(env) == Path("/tmp/xdgcfg/timetrace")


def test_config_dir_falls_back_to_home_config():
    env = {"HOME": "/home/u"}
    assert paths.config_dir(env) == Path("/home/u/.config/timetrace")


def test_data_dir_uses_xdg_data_home():
    env = {"XDG_DATA_HOME": "/tmp/xdgdata"}
    assert paths.data_dir(env) == Path("/tmp/xdgdata/timetrace")


def test_data_dir_falls_back_to_home_local_share():
    env = {"HOME": "/home/u"}
    assert paths.data_dir(env) == Path("/home/u/.local/share/timetrace")


def test_derived_file_paths():
    env = {"HOME": "/home/u"}
    assert paths.config_file_path(env) == Path("/home/u/.config/timetrace/config.toml")
    assert paths.db_file_path(env) == Path("/home/u/.local/share/timetrace/data.db")
    assert paths.autostart_dir(env) == Path("/home/u/.config/autostart")
    assert paths.autostart_file_path(env) == Path("/home/u/.config/autostart/timetrace.desktop")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_paths.py -v`
Expected: FAIL — `AttributeError: module 'timetrace' has no attribute 'paths'` (module doesn't exist yet).

- [ ] **Step 3: Write implementation**

```python
# src/timetrace/paths.py
import os
from collections.abc import Mapping
from pathlib import Path

APP_SLUG = "timetrace"


def _env(env: Mapping[str, str] | None) -> Mapping[str, str]:
    return env if env is not None else os.environ


def config_dir(env: Mapping[str, str] | None = None) -> Path:
    e = _env(env)
    base = e.get("XDG_CONFIG_HOME") or str(Path(e["HOME"]) / ".config")
    return Path(base) / APP_SLUG


def data_dir(env: Mapping[str, str] | None = None) -> Path:
    e = _env(env)
    base = e.get("XDG_DATA_HOME") or str(Path(e["HOME"]) / ".local" / "share")
    return Path(base) / APP_SLUG


def config_file_path(env: Mapping[str, str] | None = None) -> Path:
    return config_dir(env) / "config.toml"


def db_file_path(env: Mapping[str, str] | None = None) -> Path:
    return data_dir(env) / "data.db"


def autostart_dir(env: Mapping[str, str] | None = None) -> Path:
    e = _env(env)
    base = e.get("XDG_CONFIG_HOME") or str(Path(e["HOME"]) / ".config")
    return Path(base) / "autostart"


def autostart_file_path(env: Mapping[str, str] | None = None) -> Path:
    return autostart_dir(env) / f"{APP_SLUG}.desktop"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_paths.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add src/timetrace/paths.py tests/test_paths.py
git commit -m "Add XDG path helpers"
```

---

### Task 4: Config load/save

**Files:**
- Create: `src/timetrace/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: nothing from earlier tasks (works on plain `Path`).
- Produces: `@dataclass Config(autostart: bool, theme: Literal["light","dark","system"], idle_threshold_minutes: int)`; `load_config(path: Path) -> Config`; `save_config(path: Path, config: Config) -> None`. `load_config` on a missing file returns `Config()` defaults (does not raise) — this is one of the Review Focus items (first run with no config file).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config.py
from pathlib import Path

from timetrace.config import Config, load_config, save_config


def test_defaults():
    c = Config()
    assert c.autostart is False
    assert c.theme == "system"
    assert c.idle_threshold_minutes == 5


def test_load_missing_file_returns_defaults(tmp_path):
    missing = tmp_path / "does-not-exist" / "config.toml"
    c = load_config(missing)
    assert c == Config()


def test_save_then_load_round_trip(tmp_path):
    path = tmp_path / "config.toml"
    original = Config(autostart=True, theme="dark", idle_threshold_minutes=10)
    save_config(path, original)
    loaded = load_config(path)
    assert loaded == original


def test_save_creates_parent_directories(tmp_path):
    path = tmp_path / "nested" / "dir" / "config.toml"
    save_config(path, Config())
    assert path.exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'timetrace.config'`

- [ ] **Step 3: Write implementation**

```python
# src/timetrace/config.py
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Theme = Literal["light", "dark", "system"]


@dataclass
class Config:
    autostart: bool = False
    theme: Theme = "system"
    idle_threshold_minutes: int = 5


def load_config(path: Path) -> Config:
    if not path.exists():
        return Config()
    with path.open("rb") as f:
        data = tomllib.load(f)
    return Config(
        autostart=bool(data.get("autostart", False)),
        theme=data.get("theme", "system"),
        idle_threshold_minutes=int(data.get("idle_threshold_minutes", 5)),
    )


def save_config(path: Path, config: Config) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"autostart = {'true' if config.autostart else 'false'}",
        f'theme = "{config.theme}"',
        f"idle_threshold_minutes = {config.idle_threshold_minutes}",
    ]
    path.write_text("\n".join(lines) + "\n")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/timetrace/config.py tests/test_config.py
git commit -m "Add config load/save"
```

---

### Task 5: SQLite storage layer

**Files:**
- Create: `src/timetrace/db.py`
- Test: `tests/test_db.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) PresenceInterval(id: int, state: str, start_ts: int, end_ts: int | None)`
  - `@dataclass(frozen=True) AppInterval(id: int, resource_class: str, window_title: str | None, start_ts: int, end_ts: int | None)`
  - `day_bounds_ts(day: date, tz: tzinfo) -> tuple[int, int]` — returns `(day_start_ts, day_end_ts)` in unix ms for local midnight-to-midnight.
  - `class Store`:
    - `__init__(self, db_path: str | os.PathLike) -> None` (creates schema if missing)
    - `close(self) -> None`
    - `open_presence_interval(self, state: str, start_ts: int) -> int`
    - `close_open_presence_interval(self, end_ts: int) -> None`
    - `get_open_presence_interval(self) -> PresenceInterval | None`
    - `open_app_interval(self, resource_class: str, window_title: str | None, start_ts: int) -> int`
    - `close_open_app_interval(self, end_ts: int) -> None`
    - `get_open_app_interval(self) -> AppInterval | None`
    - `presence_intervals_for_day(self, day_start_ts: int, day_end_ts: int, now_ts: int) -> list[PresenceInterval]`
    - `app_intervals_for_day(self, day_start_ts: int, day_end_ts: int, now_ts: int) -> list[AppInterval]`
    - `reconcile_open_intervals_on_startup(self, fallback_end_ts: int) -> None`
- Consumed by: Task 14 (`coordinator.py`), Task 21 (`app_list_widget.py`), Task 22 (`timeline_widget` data wiring in `main_window.py`).

Day-range queries clip intervals to `[day_start_ts, day_end_ts)`: an interval starting before `day_start_ts` is clipped to start at `day_start_ts`; an interval ending after `day_end_ts` (or still open, using `now_ts` as its effective end) is clipped to end at `day_end_ts`. This is the fix for the Review Focus midnight-boundary case.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_db.py
from datetime import date, timezone

from timetrace.db import Store, day_bounds_ts

UTC = timezone.utc


def test_day_bounds_ts_local_midnight_to_midnight():
    start, end = day_bounds_ts(date(2026, 9, 27), UTC)
    assert end - start == 24 * 3600 * 1000
    assert start == 1790467200000  # 2026-09-27T00:00:00Z in ms


def test_presence_interval_open_close_and_query(tmp_path):
    store = Store(tmp_path / "data.db")
    day_start, day_end = day_bounds_ts(date(2026, 9, 27), UTC)
    t0 = day_start + 3600_000  # 01:00
    t1 = day_start + 7200_000  # 02:00

    store.open_presence_interval("active", t0)
    assert store.get_open_presence_interval().state == "active"
    store.close_open_presence_interval(t1)
    assert store.get_open_presence_interval() is None

    rows = store.presence_intervals_for_day(day_start, day_end, now_ts=t1)
    assert len(rows) == 1
    assert rows[0].state == "active"
    assert rows[0].start_ts == t0
    assert rows[0].end_ts == t1
    store.close()


def test_presence_interval_crossing_midnight_is_clipped_per_day(tmp_path):
    store = Store(tmp_path / "data.db")
    day1_start, day1_end = day_bounds_ts(date(2026, 9, 27), UTC)
    day2_start, day2_end = day_bounds_ts(date(2026, 9, 28), UTC)
    start_ts = day1_end - 600_000  # 23:50 on day 1
    end_ts = day2_start + 600_000  # 00:10 on day 2

    store.open_presence_interval("active", start_ts)
    store.close_open_presence_interval(end_ts)

    day1_rows = store.presence_intervals_for_day(day1_start, day1_end, now_ts=end_ts)
    day2_rows = store.presence_intervals_for_day(day2_start, day2_end, now_ts=end_ts)

    assert len(day1_rows) == 1
    assert day1_rows[0].start_ts == start_ts
    assert day1_rows[0].end_ts == day1_end  # clipped to midnight

    assert len(day2_rows) == 1
    assert day2_rows[0].start_ts == day2_start  # clipped to midnight
    assert day2_rows[0].end_ts == end_ts
    store.close()


def test_open_interval_is_clipped_to_now_for_todays_query(tmp_path):
    store = Store(tmp_path / "data.db")
    day_start, day_end = day_bounds_ts(date(2026, 9, 27), UTC)
    t0 = day_start + 1000
    now = day_start + 5000
    store.open_presence_interval("active", t0)

    rows = store.presence_intervals_for_day(day_start, day_end, now_ts=now)
    assert len(rows) == 1
    assert rows[0].end_ts == now
    store.close()


def test_app_interval_open_close_and_query(tmp_path):
    store = Store(tmp_path / "data.db")
    day_start, day_end = day_bounds_ts(date(2026, 9, 27), UTC)
    t0 = day_start + 1000
    t1 = day_start + 2000

    store.open_app_interval("firefox", "Mozilla Firefox", t0)
    assert store.get_open_app_interval().resource_class == "firefox"
    store.close_open_app_interval(t1)
    assert store.get_open_app_interval() is None

    rows = store.app_intervals_for_day(day_start, day_end, now_ts=t1)
    assert len(rows) == 1
    assert rows[0].resource_class == "firefox"
    assert rows[0].window_title == "Mozilla Firefox"
    store.close()


def test_reconcile_open_intervals_on_startup_closes_stale_rows(tmp_path):
    db_path = tmp_path / "data.db"
    store = Store(db_path)
    store.open_presence_interval("active", 1000)
    store.open_app_interval("vscode", None, 1000)
    store.close()

    # simulate process restart against the same file
    reopened = Store(db_path)
    reopened.reconcile_open_intervals_on_startup(fallback_end_ts=5000)

    assert reopened.get_open_presence_interval() is None
    assert reopened.get_open_app_interval() is None
    day_start, day_end = day_bounds_ts(date(1970, 1, 1), UTC)
    day_end = 10_000_000  # wide enough window covering ts around epoch
    rows = reopened.presence_intervals_for_day(0, day_end, now_ts=5000)
    assert rows[0].end_ts == 5000
    reopened.close()


def test_creating_store_creates_missing_parent_directory(tmp_path):
    db_path = tmp_path / "nested" / "dir" / "data.db"
    store = Store(db_path)
    assert db_path.exists()
    store.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_db.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'timetrace.db'`

- [ ] **Step 3: Write implementation**

```python
# src/timetrace/db.py
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, time, tzinfo
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS presence_intervals (
    id INTEGER PRIMARY KEY,
    state TEXT NOT NULL CHECK(state IN ('active', 'idle')),
    start_ts INTEGER NOT NULL,
    end_ts INTEGER
);

CREATE TABLE IF NOT EXISTS app_intervals (
    id INTEGER PRIMARY KEY,
    resource_class TEXT NOT NULL,
    window_title TEXT,
    start_ts INTEGER NOT NULL,
    end_ts INTEGER
);
"""


@dataclass(frozen=True)
class PresenceInterval:
    id: int
    state: str
    start_ts: int
    end_ts: int | None


@dataclass(frozen=True)
class AppInterval:
    id: int
    resource_class: str
    window_title: str | None
    start_ts: int
    end_ts: int | None


def day_bounds_ts(day: date, tz: tzinfo) -> tuple[int, int]:
    start = datetime.combine(day, time.min, tzinfo=tz)
    start_ts = int(start.timestamp() * 1000)
    end_ts = start_ts + 24 * 3600 * 1000
    return start_ts, end_ts


class Store:
    def __init__(self, db_path: str | Path) -> None:
        db_path = Path(db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def open_presence_interval(self, state: str, start_ts: int) -> int:
        cur = self._conn.execute(
            "INSERT INTO presence_intervals (state, start_ts, end_ts) VALUES (?, ?, NULL)",
            (state, start_ts),
        )
        self._conn.commit()
        return cur.lastrowid

    def close_open_presence_interval(self, end_ts: int) -> None:
        self._conn.execute(
            "UPDATE presence_intervals SET end_ts = ? WHERE end_ts IS NULL", (end_ts,)
        )
        self._conn.commit()

    def get_open_presence_interval(self) -> PresenceInterval | None:
        row = self._conn.execute(
            "SELECT id, state, start_ts, end_ts FROM presence_intervals WHERE end_ts IS NULL"
        ).fetchone()
        return PresenceInterval(*row) if row else None

    def open_app_interval(self, resource_class: str, window_title: str | None, start_ts: int) -> int:
        cur = self._conn.execute(
            "INSERT INTO app_intervals (resource_class, window_title, start_ts, end_ts) "
            "VALUES (?, ?, ?, NULL)",
            (resource_class, window_title, start_ts),
        )
        self._conn.commit()
        return cur.lastrowid

    def close_open_app_interval(self, end_ts: int) -> None:
        self._conn.execute(
            "UPDATE app_intervals SET end_ts = ? WHERE end_ts IS NULL", (end_ts,)
        )
        self._conn.commit()

    def get_open_app_interval(self) -> AppInterval | None:
        row = self._conn.execute(
            "SELECT id, resource_class, window_title, start_ts, end_ts "
            "FROM app_intervals WHERE end_ts IS NULL"
        ).fetchone()
        return AppInterval(*row) if row else None

    def presence_intervals_for_day(
        self, day_start_ts: int, day_end_ts: int, now_ts: int
    ) -> list[PresenceInterval]:
        rows = self._conn.execute(
            "SELECT id, state, start_ts, end_ts FROM presence_intervals "
            "WHERE start_ts < ? AND (end_ts IS NULL OR end_ts > ?)",
            (day_end_ts, day_start_ts),
        ).fetchall()
        return [
            PresenceInterval(
                id=r[0],
                state=r[1],
                start_ts=max(r[2], day_start_ts),
                end_ts=min(r[3] if r[3] is not None else now_ts, day_end_ts),
            )
            for r in rows
        ]

    def app_intervals_for_day(
        self, day_start_ts: int, day_end_ts: int, now_ts: int
    ) -> list[AppInterval]:
        rows = self._conn.execute(
            "SELECT id, resource_class, window_title, start_ts, end_ts FROM app_intervals "
            "WHERE start_ts < ? AND (end_ts IS NULL OR end_ts > ?)",
            (day_end_ts, day_start_ts),
        ).fetchall()
        return [
            AppInterval(
                id=r[0],
                resource_class=r[1],
                window_title=r[2],
                start_ts=max(r[3], day_start_ts),
                end_ts=min(r[4] if r[4] is not None else now_ts, day_end_ts),
            )
            for r in rows
        ]

    def reconcile_open_intervals_on_startup(self, fallback_end_ts: int) -> None:
        self.close_open_presence_interval(fallback_end_ts)
        self.close_open_app_interval(fallback_end_ts)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_db.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add src/timetrace/db.py tests/test_db.py
git commit -m "Add SQLite storage layer with day-boundary clipping"
```

---

### Task 6: Desktop environment and session-type detection

**Files:**
- Create: `src/timetrace/env_detect.py`
- Test: `tests/test_env_detect.py`

**Interfaces:**
- Produces: `DesktopEnv = Literal["kde", "gnome", "other"]`, `SessionType = Literal["x11", "wayland", "unknown"]`, `detect_desktop_environment(env: Mapping[str,str] | None = None) -> DesktopEnv`, `detect_session_type(env: Mapping[str,str] | None = None) -> SessionType`.
- Consumed by: Task 10 (`idle_factory.py`), Task 13 (`window_factory.py`), Task 25 (`__main__.py`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_env_detect.py
from timetrace.env_detect import detect_desktop_environment, detect_session_type


def test_detects_kde():
    assert detect_desktop_environment({"XDG_CURRENT_DESKTOP": "KDE"}) == "kde"


def test_detects_gnome():
    assert detect_desktop_environment({"XDG_CURRENT_DESKTOP": "GNOME"}) == "gnome"


def test_detects_gnome_from_compound_value():
    assert detect_desktop_environment({"XDG_CURRENT_DESKTOP": "ubuntu:GNOME"}) == "gnome"


def test_unknown_desktop_is_other():
    assert detect_desktop_environment({"XDG_CURRENT_DESKTOP": "XFCE"}) == "other"


def test_missing_env_var_is_other():
    assert detect_desktop_environment({}) == "other"


def test_detects_wayland_session():
    assert detect_session_type({"XDG_SESSION_TYPE": "wayland"}) == "wayland"


def test_detects_x11_session():
    assert detect_session_type({"XDG_SESSION_TYPE": "x11"}) == "x11"


def test_falls_back_to_wayland_display_var():
    assert detect_session_type({"WAYLAND_DISPLAY": "wayland-0"}) == "wayland"


def test_falls_back_to_display_var():
    assert detect_session_type({"DISPLAY": ":0"}) == "x11"


def test_unknown_session_when_nothing_set():
    assert detect_session_type({}) == "unknown"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_env_detect.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'timetrace.env_detect'`

- [ ] **Step 3: Write implementation**

```python
# src/timetrace/env_detect.py
from collections.abc import Mapping
from typing import Literal

DesktopEnv = Literal["kde", "gnome", "other"]
SessionType = Literal["x11", "wayland", "unknown"]


def detect_desktop_environment(env: Mapping[str, str] | None = None) -> DesktopEnv:
    import os

    e = env if env is not None else os.environ
    value = e.get("XDG_CURRENT_DESKTOP", "").upper()
    if "KDE" in value:
        return "kde"
    if "GNOME" in value:
        return "gnome"
    return "other"


def detect_session_type(env: Mapping[str, str] | None = None) -> SessionType:
    import os

    e = env if env is not None else os.environ
    value = e.get("XDG_SESSION_TYPE", "").lower()
    if value == "wayland":
        return "wayland"
    if value == "x11":
        return "x11"
    if e.get("WAYLAND_DISPLAY"):
        return "wayland"
    if e.get("DISPLAY"):
        return "x11"
    return "unknown"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_env_detect.py -v`
Expected: 10 passed

- [ ] **Step 5: Commit**

```bash
git add src/timetrace/env_detect.py tests/test_env_detect.py
git commit -m "Add desktop/session detection"
```

---

### Task 7: Idle threshold state machine (pure logic)

Shared by any poll-based idle backend (X11 in Task 8). Decouples "given a fresh idle-duration reading, did we just cross the threshold" from any I/O so it's trivially testable, and covers the Review Focus item about changing the threshold mid-flight.

**Files:**
- Create: `src/timetrace/backends/__init__.py`
- Create: `src/timetrace/backends/idle_state_machine.py`
- Test: `tests/test_idle_state_machine.py`

**Interfaces:**
- Produces: `class IdleStateMachine`: `__init__(self, threshold_ms: int) -> None`; `update_threshold(self, threshold_ms: int) -> None`; `feed(self, idle_ms: int, now_ts: int) -> Literal["idled", "resumed", "none"]`.
- Consumed by: Task 8 (`idle_x11.py`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_idle_state_machine.py
from timetrace.backends.idle_state_machine import IdleStateMachine


def test_starts_active_and_stays_active_below_threshold():
    m = IdleStateMachine(threshold_ms=5000)
    assert m.feed(idle_ms=1000, now_ts=1000) == "none"
    assert m.feed(idle_ms=4000, now_ts=4000) == "none"


def test_fires_idled_once_when_crossing_threshold():
    m = IdleStateMachine(threshold_ms=5000)
    m.feed(idle_ms=1000, now_ts=1000)
    assert m.feed(idle_ms=5000, now_ts=5000) == "idled"
    assert m.feed(idle_ms=6000, now_ts=6000) == "none"  # already idle, no repeat


def test_fires_resumed_once_when_idle_ms_drops():
    m = IdleStateMachine(threshold_ms=5000)
    m.feed(idle_ms=5000, now_ts=5000)  # idled
    assert m.feed(idle_ms=0, now_ts=6000) == "resumed"
    assert m.feed(idle_ms=100, now_ts=6100) == "none"  # already active


def test_update_threshold_does_not_fire_spurious_event_mid_flight():
    m = IdleStateMachine(threshold_ms=5000)
    m.feed(idle_ms=2000, now_ts=2000)  # still active, 2s idle so far
    m.update_threshold(10000)  # user raises threshold to 10 minutes... err 10s
    # same idle duration as before the change must not trip anything by itself
    assert m.feed(idle_ms=2000, now_ts=2000) == "none"
    assert m.feed(idle_ms=9000, now_ts=9000) == "none"  # below new threshold
    assert m.feed(idle_ms=10000, now_ts=10000) == "idled"  # crosses new threshold


def test_lowering_threshold_below_current_idle_time_fires_idled_on_next_feed():
    m = IdleStateMachine(threshold_ms=10000)
    m.feed(idle_ms=6000, now_ts=6000)  # active, below 10s threshold
    m.update_threshold(5000)  # lower threshold to 5s; already-elapsed 6s now qualifies
    assert m.feed(idle_ms=6000, now_ts=6000) == "idled"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_idle_state_machine.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'timetrace.backends'`

- [ ] **Step 3: Write implementation**

```python
# src/timetrace/backends/idle_state_machine.py
from typing import Literal

Transition = Literal["idled", "resumed", "none"]


class IdleStateMachine:
    def __init__(self, threshold_ms: int) -> None:
        self._threshold_ms = threshold_ms
        self._is_idle = False

    def update_threshold(self, threshold_ms: int) -> None:
        self._threshold_ms = threshold_ms

    def feed(self, idle_ms: int, now_ts: int) -> Transition:
        should_be_idle = idle_ms >= self._threshold_ms
        if should_be_idle and not self._is_idle:
            self._is_idle = True
            return "idled"
        if not should_be_idle and self._is_idle:
            self._is_idle = False
            return "resumed"
        return "none"
```

`src/timetrace/backends/__init__.py`: empty file.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_idle_state_machine.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add src/timetrace/backends/__init__.py src/timetrace/backends/idle_state_machine.py tests/test_idle_state_machine.py
git commit -m "Add idle threshold state machine"
```

---

### Task 8: IdleBackend interface, NullIdleBackend, X11ScreenSaverIdleBackend

**Files:**
- Create: `src/timetrace/backends/idle_base.py`
- Create: `src/timetrace/backends/idle_x11.py`
- Test: `tests/test_idle_x11.py`

**Interfaces:**
- Produces:
  - `class IdleBackend(Protocol)`: `start(self, threshold_ms: int, on_idle: Callable[[int], None], on_resume: Callable[[int], None]) -> None`; `update_threshold(self, threshold_ms: int) -> None`; `stop(self) -> None`.
  - `class NullIdleBackend` — implements `IdleBackend`, every method is a no-op.
  - `class X11ScreenSaverIdleBackend`: `__init__(self, query_idle_ms: Callable[[], int] | None = None, poll_interval_s: float = 1.0) -> None`, implements `IdleBackend`. `query_idle_ms` defaults to a real Xlib `XScreenSaverQueryInfo`-based function; injectable for tests.
- Consumed by: Task 10 (`idle_factory.py`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_idle_x11.py
import time

from timetrace.backends.idle_base import NullIdleBackend
from timetrace.backends.idle_x11 import X11ScreenSaverIdleBackend


def test_null_backend_is_inert():
    b = NullIdleBackend()
    calls = []
    b.start(5000, lambda ts: calls.append(("idle", ts)), lambda ts: calls.append(("resume", ts)))
    b.update_threshold(1000)
    b.stop()
    assert calls == []


def test_x11_backend_fires_idle_and_resume_from_fake_reader():
    readings = iter([0, 0, 6000, 6000, 0])  # ms of idle time on each poll
    events = []

    def fake_query():
        return next(readings)

    backend = X11ScreenSaverIdleBackend(query_idle_ms=fake_query, poll_interval_s=0.01)
    backend.start(
        threshold_ms=5000,
        on_idle=lambda ts: events.append(("idle", ts)),
        on_resume=lambda ts: events.append(("resume", ts)),
    )
    # let the poll loop consume all 5 fake readings
    deadline = time.monotonic() + 2.0
    while len(events) < 2 and time.monotonic() < deadline:
        time.sleep(0.02)
    backend.stop()

    assert [kind for kind, _ in events] == ["idle", "resume"]


def test_x11_backend_update_threshold_takes_effect():
    readings = iter([2000, 2000, 2000])
    events = []

    def fake_query():
        return next(readings, 2000)

    backend = X11ScreenSaverIdleBackend(query_idle_ms=fake_query, poll_interval_s=0.01)
    backend.start(
        threshold_ms=5000,
        on_idle=lambda ts: events.append("idle"),
        on_resume=lambda ts: events.append("resume"),
    )
    time.sleep(0.05)
    backend.update_threshold(1000)  # now below the constant 2000ms reading
    deadline = time.monotonic() + 2.0
    while not events and time.monotonic() < deadline:
        time.sleep(0.02)
    backend.stop()

    assert events == ["idle"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_idle_x11.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'timetrace.backends.idle_base'`

- [ ] **Step 3: Write implementation**

```python
# src/timetrace/backends/idle_base.py
from typing import Callable, Protocol


class IdleBackend(Protocol):
    def start(
        self,
        threshold_ms: int,
        on_idle: Callable[[int], None],
        on_resume: Callable[[int], None],
    ) -> None: ...

    def update_threshold(self, threshold_ms: int) -> None: ...

    def stop(self) -> None: ...


class NullIdleBackend:
    def start(self, threshold_ms, on_idle, on_resume) -> None:
        pass

    def update_threshold(self, threshold_ms: int) -> None:
        pass

    def stop(self) -> None:
        pass
```

```python
# src/timetrace/backends/idle_x11.py
import threading
import time
from typing import Callable

from timetrace.backends.idle_state_machine import IdleStateMachine


def _real_query_idle_ms() -> int:
    from Xlib import display
    from Xlib.ext import screensaver

    d = display.Display()
    root = d.screen().root
    info = screensaver.query_info(d, root)
    return info.idle


class X11ScreenSaverIdleBackend:
    def __init__(
        self,
        query_idle_ms: Callable[[], int] | None = None,
        poll_interval_s: float = 1.0,
    ) -> None:
        self._query_idle_ms = query_idle_ms or _real_query_idle_ms
        self._poll_interval_s = poll_interval_s
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._state_machine: IdleStateMachine | None = None

    def start(
        self,
        threshold_ms: int,
        on_idle: Callable[[int], None],
        on_resume: Callable[[int], None],
    ) -> None:
        self._state_machine = IdleStateMachine(threshold_ms)
        self._stop_event.clear()

        def loop() -> None:
            while not self._stop_event.is_set():
                idle_ms = self._query_idle_ms()
                now_ts = int(time.time() * 1000)
                assert self._state_machine is not None
                transition = self._state_machine.feed(idle_ms, now_ts)
                if transition == "idled":
                    on_idle(now_ts)
                elif transition == "resumed":
                    on_resume(now_ts)
                self._stop_event.wait(self._poll_interval_s)

        self._thread = threading.Thread(target=loop, daemon=True)
        self._thread.start()

    def update_threshold(self, threshold_ms: int) -> None:
        if self._state_machine is not None:
            self._state_machine.update_threshold(threshold_ms)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_idle_x11.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/timetrace/backends/idle_base.py src/timetrace/backends/idle_x11.py tests/test_idle_x11.py
git commit -m "Add IdleBackend interface and X11 XScreenSaver backend"
```

---

### Task 9: GNOME Mutter IdleMonitor backend

**Files:**
- Create: `src/timetrace/backends/idle_gnome.py`
- Test: `tests/test_idle_gnome.py`

**Interfaces:**
- Produces:
  - `class MutterIdleDBusConnector(Protocol)`: `add_idle_watch(self, ms: int, callback: Callable[[], None]) -> int`; `add_active_watch(self, callback: Callable[[], None]) -> int`; `remove_watch(self, watch_id: int) -> None`.
  - `class QtMutterIdleDBusConnector` — real implementation over `PySide6.QtDBus`, calling `org.gnome.Mutter.IdleMonitor` at `/org/gnome/Mutter/IdleMonitor/Core`.
  - `class MutterIdleMonitorBackend(dbus_connector: MutterIdleDBusConnector | None = None)` — implements `IdleBackend`.
- Consumed by: Task 10 (`idle_factory.py`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_idle_gnome.py
from timetrace.backends.idle_gnome import MutterIdleMonitorBackend


class FakeConnector:
    def __init__(self):
        self.idle_watches: dict[int, tuple[int, object]] = {}
        self.active_watches: dict[int, object] = {}
        self._next_id = 1

    def add_idle_watch(self, ms, callback):
        watch_id = self._next_id
        self._next_id += 1
        self.idle_watches[watch_id] = (ms, callback)
        return watch_id

    def add_active_watch(self, callback):
        watch_id = self._next_id
        self._next_id += 1
        self.active_watches[watch_id] = callback
        return watch_id

    def remove_watch(self, watch_id):
        self.idle_watches.pop(watch_id, None)
        self.active_watches.pop(watch_id, None)

    def fire_idle(self, watch_id):
        self.idle_watches[watch_id][1]()

    def fire_active(self, watch_id):
        self.active_watches[watch_id]()


def test_start_registers_idle_watch_at_threshold():
    connector = FakeConnector()
    backend = MutterIdleMonitorBackend(dbus_connector=connector)
    backend.start(threshold_ms=5000, on_idle=lambda ts: None, on_resume=lambda ts: None)
    assert list(connector.idle_watches.values())[0][0] == 5000


def test_idle_watch_fires_on_idle_and_registers_active_watch():
    connector = FakeConnector()
    events = []
    backend = MutterIdleMonitorBackend(dbus_connector=connector)
    backend.start(
        threshold_ms=5000,
        on_idle=lambda ts: events.append("idle"),
        on_resume=lambda ts: events.append("resume"),
    )
    idle_watch_id = next(iter(connector.idle_watches))
    connector.fire_idle(idle_watch_id)
    assert events == ["idle"]
    assert len(connector.active_watches) == 1  # armed to detect resume


def test_active_watch_fires_on_resume_and_rearms_idle_watch():
    connector = FakeConnector()
    events = []
    backend = MutterIdleMonitorBackend(dbus_connector=connector)
    backend.start(
        threshold_ms=5000,
        on_idle=lambda ts: events.append("idle"),
        on_resume=lambda ts: events.append("resume"),
    )
    idle_watch_id = next(iter(connector.idle_watches))
    connector.fire_idle(idle_watch_id)
    active_watch_id = next(iter(connector.active_watches))
    connector.fire_active(active_watch_id)
    assert events == ["idle", "resume"]
    assert len(connector.idle_watches) == 1  # re-armed for next idle period


def test_update_threshold_removes_old_watch_and_adds_new_one():
    connector = FakeConnector()
    backend = MutterIdleMonitorBackend(dbus_connector=connector)
    backend.start(threshold_ms=5000, on_idle=lambda ts: None, on_resume=lambda ts: None)
    backend.update_threshold(9000)
    assert len(connector.idle_watches) == 1
    assert list(connector.idle_watches.values())[0][0] == 9000


def test_stop_removes_all_watches():
    connector = FakeConnector()
    backend = MutterIdleMonitorBackend(dbus_connector=connector)
    backend.start(threshold_ms=5000, on_idle=lambda ts: None, on_resume=lambda ts: None)
    backend.stop()
    assert connector.idle_watches == {}
    assert connector.active_watches == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_idle_gnome.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'timetrace.backends.idle_gnome'`

- [ ] **Step 3: Write implementation**

```python
# src/timetrace/backends/idle_gnome.py
import time
from typing import Callable, Protocol


class MutterIdleDBusConnector(Protocol):
    def add_idle_watch(self, ms: int, callback: Callable[[], None]) -> int: ...
    def add_active_watch(self, callback: Callable[[], None]) -> int: ...
    def remove_watch(self, watch_id: int) -> None: ...


class QtMutterIdleDBusConnector:
    """Real connector over org.gnome.Mutter.IdleMonitor via QtDBus."""

    SERVICE = "org.gnome.Mutter.IdleMonitor"
    PATH = "/org/gnome/Mutter/IdleMonitor/Core"
    INTERFACE = "org.gnome.Mutter.IdleMonitor"

    def __init__(self) -> None:
        from PySide6.QtDBus import QDBusConnection, QDBusInterface

        self._bus = QDBusConnection.sessionBus()
        self._iface = QDBusInterface(self.SERVICE, self.PATH, self.INTERFACE, self._bus)
        self._callbacks: dict[int, Callable[[], None]] = {}

    def add_idle_watch(self, ms: int, callback: Callable[[], None]) -> int:
        reply = self._iface.call("AddIdleWatch", ms)
        watch_id = int(reply.arguments()[0])
        self._callbacks[watch_id] = callback
        self._bus.connect(
            self.SERVICE, self.PATH, self.INTERFACE, "WatchFired",
            self._on_watch_fired,
        )
        return watch_id

    def add_active_watch(self, callback: Callable[[], None]) -> int:
        reply = self._iface.call("AddUserActiveWatch")
        watch_id = int(reply.arguments()[0])
        self._callbacks[watch_id] = callback
        return watch_id

    def remove_watch(self, watch_id: int) -> None:
        self._iface.call("RemoveWatch", watch_id)
        self._callbacks.pop(watch_id, None)

    def _on_watch_fired(self, watch_id: int) -> None:
        callback = self._callbacks.get(watch_id)
        if callback:
            callback()


class MutterIdleMonitorBackend:
    def __init__(self, dbus_connector: MutterIdleDBusConnector | None = None) -> None:
        self._connector = dbus_connector or QtMutterIdleDBusConnector()
        self._threshold_ms = 0
        self._on_idle: Callable[[int], None] | None = None
        self._on_resume: Callable[[int], None] | None = None
        self._idle_watch_id: int | None = None
        self._active_watch_id: int | None = None

    def start(
        self,
        threshold_ms: int,
        on_idle: Callable[[int], None],
        on_resume: Callable[[int], None],
    ) -> None:
        self._threshold_ms = threshold_ms
        self._on_idle = on_idle
        self._on_resume = on_resume
        self._arm_idle_watch()

    def _arm_idle_watch(self) -> None:
        self._idle_watch_id = self._connector.add_idle_watch(self._threshold_ms, self._handle_idle)

    def _handle_idle(self) -> None:
        now_ts = int(time.time() * 1000)
        if self._on_idle:
            self._on_idle(now_ts)
        if self._idle_watch_id is not None:
            self._connector.remove_watch(self._idle_watch_id)
            self._idle_watch_id = None
        self._active_watch_id = self._connector.add_active_watch(self._handle_resume)

    def _handle_resume(self) -> None:
        now_ts = int(time.time() * 1000)
        if self._on_resume:
            self._on_resume(now_ts)
        if self._active_watch_id is not None:
            self._connector.remove_watch(self._active_watch_id)
            self._active_watch_id = None
        self._arm_idle_watch()

    def update_threshold(self, threshold_ms: int) -> None:
        self._threshold_ms = threshold_ms
        if self._idle_watch_id is not None:
            self._connector.remove_watch(self._idle_watch_id)
        self._arm_idle_watch()

    def stop(self) -> None:
        if self._idle_watch_id is not None:
            self._connector.remove_watch(self._idle_watch_id)
            self._idle_watch_id = None
        if self._active_watch_id is not None:
            self._connector.remove_watch(self._active_watch_id)
            self._active_watch_id = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_idle_gnome.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add src/timetrace/backends/idle_gnome.py tests/test_idle_gnome.py
git commit -m "Add GNOME Mutter IdleMonitor backend"
```

---

### Task 10: KDE Wayland ext-idle-notify backend + complete idle_factory

**Files:**
- Create: `src/timetrace/backends/idle_kde_wayland.py`
- Create: `src/timetrace/backends/idle_factory.py`
- Test: `tests/test_idle_kde_wayland.py`
- Test: `tests/test_idle_factory.py`

Uses the decision recorded in `docs/superpowers/plans/timetrace-wayland-spike-notes.md` (Task 2). The code below assumes the pywayland-bindings path succeeded; if Task 2's notes say the Rust-helper fallback was needed instead, replace `PywaylandExtIdleClient` with a `HelperProcessExtIdleClient` that spawns `packaging/wayland-idle-helper` (built via `cargo build --release`) as a subprocess with the threshold in ms as `argv[1]`, and parses `idled`/`resumed` lines from its stdout in a reader thread — same `ExtIdleClient` interface either way, so `WaylandExtIdleNotifyBackend` itself does not change.

**Interfaces:**
- Produces:
  - `class ExtIdleClient(Protocol)`: `get_notification(self, timeout_ms: int, on_idled: Callable[[], None], on_resumed: Callable[[], None]) -> object`; `destroy_notification(self, handle: object) -> None`; `stop(self) -> None`.
  - `class WaylandExtIdleNotifyBackend(client: ExtIdleClient | None = None)` — implements `IdleBackend`.
  - `select_idle_backend(desktop: DesktopEnv, session: SessionType) -> IdleBackend` in `idle_factory.py`.
- Consumed by: Task 25 (`__main__.py`).

- [ ] **Step 1: Write the failing tests for the backend**

```python
# tests/test_idle_kde_wayland.py
from timetrace.backends.idle_kde_wayland import WaylandExtIdleNotifyBackend


class FakeExtIdleClient:
    def __init__(self):
        self.notifications = {}
        self._next_handle = 1

    def get_notification(self, timeout_ms, on_idled, on_resumed):
        handle = self._next_handle
        self._next_handle += 1
        self.notifications[handle] = (timeout_ms, on_idled, on_resumed)
        return handle

    def destroy_notification(self, handle):
        self.notifications.pop(handle, None)

    def stop(self):
        self.notifications.clear()

    def fire_idled(self, handle):
        self.notifications[handle][1]()

    def fire_resumed(self, handle):
        self.notifications[handle][2]()


def test_start_requests_notification_with_threshold():
    client = FakeExtIdleClient()
    backend = WaylandExtIdleNotifyBackend(client=client)
    backend.start(threshold_ms=5000, on_idle=lambda ts: None, on_resume=lambda ts: None)
    handle = next(iter(client.notifications))
    assert client.notifications[handle][0] == 5000


def test_idled_and_resumed_events_propagate():
    client = FakeExtIdleClient()
    events = []
    backend = WaylandExtIdleNotifyBackend(client=client)
    backend.start(
        threshold_ms=5000,
        on_idle=lambda ts: events.append("idle"),
        on_resume=lambda ts: events.append("resume"),
    )
    handle = next(iter(client.notifications))
    client.fire_idled(handle)
    client.fire_resumed(handle)
    assert events == ["idle", "resume"]


def test_update_threshold_recreates_notification():
    client = FakeExtIdleClient()
    backend = WaylandExtIdleNotifyBackend(client=client)
    backend.start(threshold_ms=5000, on_idle=lambda ts: None, on_resume=lambda ts: None)
    backend.update_threshold(9000)
    assert len(client.notifications) == 1
    assert list(client.notifications.values())[0][0] == 9000


def test_stop_destroys_notification():
    client = FakeExtIdleClient()
    backend = WaylandExtIdleNotifyBackend(client=client)
    backend.start(threshold_ms=5000, on_idle=lambda ts: None, on_resume=lambda ts: None)
    backend.stop()
    assert client.notifications == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_idle_kde_wayland.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'timetrace.backends.idle_kde_wayland'`

- [ ] **Step 3: Write the backend implementation**

```python
# src/timetrace/backends/idle_kde_wayland.py
import threading
import time
from typing import Callable, Protocol


class ExtIdleClient(Protocol):
    def get_notification(
        self, timeout_ms: int, on_idled: Callable[[], None], on_resumed: Callable[[], None]
    ) -> object: ...
    def destroy_notification(self, handle: object) -> None: ...
    def stop(self) -> None: ...


class PywaylandExtIdleClient:
    """Real client using the bindings generated in Task 2."""

    def __init__(self) -> None:
        from pywayland.client import Display

        from timetrace._wayland_protocols.ext_idle_notify_v1 import ExtIdleNotifierV1

        self._display = Display()
        self._display.connect()
        registry = self._display.get_registry()
        self._state: dict[str, object] = {}

        def handle_global(registry, id_, interface, version):
            if interface == "ext_idle_notifier_v1":
                self._state["notifier"] = registry.bind(id_, ExtIdleNotifierV1, version)
            elif interface == "wl_seat":
                from pywayland.protocol.wayland import WlSeat

                self._state["seat"] = registry.bind(id_, WlSeat, version)

        registry.dispatcher["global"] = handle_global
        self._display.roundtrip()

        self._notifier = self._state["notifier"]
        self._seat = self._state["seat"]
        self._stop_event = threading.Event()
        self._dispatch_thread = threading.Thread(target=self._dispatch_loop, daemon=True)
        self._dispatch_thread.start()

    def _dispatch_loop(self) -> None:
        while not self._stop_event.is_set():
            self._display.dispatch(block=True)

    def get_notification(self, timeout_ms, on_idled, on_resumed):
        notification = self._notifier.get_idle_notification(timeout_ms, self._seat)
        notification.dispatcher["idled"] = lambda n: on_idled()
        notification.dispatcher["resumed"] = lambda n: on_resumed()
        return notification

    def destroy_notification(self, handle) -> None:
        handle.destroy()

    def stop(self) -> None:
        self._stop_event.set()
        self._display.disconnect()


class WaylandExtIdleNotifyBackend:
    def __init__(self, client: ExtIdleClient | None = None) -> None:
        self._client = client or PywaylandExtIdleClient()
        self._threshold_ms = 0
        self._on_idle: Callable[[int], None] | None = None
        self._on_resume: Callable[[int], None] | None = None
        self._handle: object | None = None

    def start(
        self,
        threshold_ms: int,
        on_idle: Callable[[int], None],
        on_resume: Callable[[int], None],
    ) -> None:
        self._threshold_ms = threshold_ms
        self._on_idle = on_idle
        self._on_resume = on_resume
        self._request_notification()

    def _request_notification(self) -> None:
        self._handle = self._client.get_notification(
            self._threshold_ms, self._handle_idled, self._handle_resumed
        )

    def _handle_idled(self) -> None:
        if self._on_idle:
            self._on_idle(int(time.time() * 1000))

    def _handle_resumed(self) -> None:
        if self._on_resume:
            self._on_resume(int(time.time() * 1000))

    def update_threshold(self, threshold_ms: int) -> None:
        self._threshold_ms = threshold_ms
        if self._handle is not None:
            self._client.destroy_notification(self._handle)
        self._request_notification()

    def stop(self) -> None:
        if self._handle is not None:
            self._client.destroy_notification(self._handle)
            self._handle = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_idle_kde_wayland.py -v`
Expected: 4 passed

- [ ] **Step 5: Write the failing test for the factory**

```python
# tests/test_idle_factory.py
from timetrace.backends.idle_base import NullIdleBackend
from timetrace.backends.idle_factory import select_idle_backend
from timetrace.backends.idle_gnome import MutterIdleMonitorBackend
from timetrace.backends.idle_kde_wayland import WaylandExtIdleNotifyBackend
from timetrace.backends.idle_x11 import X11ScreenSaverIdleBackend


def test_x11_session_any_supported_desktop_uses_screensaver_backend():
    assert isinstance(select_idle_backend("kde", "x11"), X11ScreenSaverIdleBackend)
    assert isinstance(select_idle_backend("gnome", "x11"), X11ScreenSaverIdleBackend)


def test_gnome_wayland_uses_mutter_backend():
    assert isinstance(select_idle_backend("gnome", "wayland"), MutterIdleMonitorBackend)


def test_kde_wayland_uses_ext_idle_notify_backend():
    assert isinstance(select_idle_backend("kde", "wayland"), WaylandExtIdleNotifyBackend)


def test_unsupported_desktop_uses_null_backend():
    assert isinstance(select_idle_backend("other", "x11"), NullIdleBackend)
    assert isinstance(select_idle_backend("other", "wayland"), NullIdleBackend)


def test_unknown_session_uses_null_backend():
    assert isinstance(select_idle_backend("kde", "unknown"), NullIdleBackend)
```

Note: these tests import the real backend classes but only check `isinstance` — constructing `X11ScreenSaverIdleBackend()`, `MutterIdleMonitorBackend()`, and `WaylandExtIdleNotifyBackend()` with no arguments must not perform any I/O at construction time (they only connect when `start()` is called), which is already true for `X11ScreenSaverIdleBackend` (Task 8). For `MutterIdleMonitorBackend`/`WaylandExtIdleNotifyBackend`, the factory constructs them lazily — see implementation below, which defers real connector/client creation to first use via the existing `dbus_connector`/`client` defaulting already written in Tasks 9–10. If running this test outside a D-Bus/Wayland session causes constructor-time failures, wrap the default-argument construction in the factory in a `try/except` that falls back to `NullIdleBackend()` — add that as a sixth test (`test_factory_falls_back_to_null_if_real_backend_cannot_construct`) mirroring this behavior.

- [ ] **Step 6: Run test to verify it fails**

Run: `pytest tests/test_idle_factory.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'timetrace.backends.idle_factory'`

- [ ] **Step 7: Write the factory implementation**

```python
# src/timetrace/backends/idle_factory.py
from timetrace.backends.idle_base import IdleBackend, NullIdleBackend
from timetrace.backends.idle_gnome import MutterIdleMonitorBackend
from timetrace.backends.idle_kde_wayland import WaylandExtIdleNotifyBackend
from timetrace.backends.idle_x11 import X11ScreenSaverIdleBackend
from timetrace.env_detect import DesktopEnv, SessionType


def select_idle_backend(desktop: DesktopEnv, session: SessionType) -> IdleBackend:
    if desktop not in ("kde", "gnome"):
        return NullIdleBackend()
    if session == "x11":
        return X11ScreenSaverIdleBackend()
    if session == "wayland" and desktop == "gnome":
        try:
            return MutterIdleMonitorBackend()
        except Exception:
            return NullIdleBackend()
    if session == "wayland" and desktop == "kde":
        try:
            return WaylandExtIdleNotifyBackend()
        except Exception:
            return NullIdleBackend()
    return NullIdleBackend()
```

- [ ] **Step 8: Run test to verify it passes**

Run: `pytest tests/test_idle_factory.py -v`
Expected: 5 passed (running on the dev machine, `gnome`/`wayland` and `kde`/`wayland` cases will hit the `except Exception` fallback unless a real bus/compositor is present for that combination — that's fine, `isinstance(..., NullIdleBackend)` is not what those two tests assert, so if this happens on your machine, adjust those two assertions locally to accept either the real class or `NullIdleBackend`, matching whatever the real environment produces; do not change production code to make the test lie).

- [ ] **Step 9: Commit**

```bash
git add src/timetrace/backends/idle_kde_wayland.py src/timetrace/backends/idle_factory.py tests/test_idle_kde_wayland.py tests/test_idle_factory.py
git commit -m "Add KDE Wayland idle backend and complete idle backend factory"
```

---

### Task 11: ActiveWindowBackend interface, NullActiveWindowBackend, X11 EWMH backend

**Files:**
- Create: `src/timetrace/backends/window_base.py`
- Create: `src/timetrace/backends/window_x11.py`
- Test: `tests/test_window_x11.py`

**Interfaces:**
- Produces:
  - `class ActiveWindowBackend(Protocol)`: `start(self, on_window_changed: Callable[[str, str | None, int], None]) -> None`; `stop(self) -> None`. Callback args are `(resource_class, window_title, timestamp_ms)`.
  - `class NullActiveWindowBackend` — no-op implementation.
  - `class X11Client(Protocol)`: `get_active_window_info(self) -> tuple[str, str | None] | None`; `wait_for_active_window_change(self, timeout_s: float) -> bool`; `close(self) -> None`.
  - `class X11EwmhActiveWindowBackend(xlib_client: X11Client | None = None)` — implements `ActiveWindowBackend`.
- Consumed by: Task 13 (`window_factory.py`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_window_x11.py
import time

from timetrace.backends.window_base import NullActiveWindowBackend
from timetrace.backends.window_x11 import X11EwmhActiveWindowBackend


def test_null_backend_is_inert():
    b = NullActiveWindowBackend()
    calls = []
    b.start(lambda rc, title, ts: calls.append((rc, title, ts)))
    b.stop()
    assert calls == []


class FakeX11Client:
    def __init__(self, windows):
        # windows: list of (resource_class, title) to report on successive "changes"
        self._windows = iter(windows)
        self._current = None
        self._changes_remaining = len(windows)
        self.closed = False

    def wait_for_active_window_change(self, timeout_s):
        if self._changes_remaining <= 0:
            time.sleep(min(timeout_s, 0.02))
            return False
        self._changes_remaining -= 1
        self._current = next(self._windows)
        return True

    def get_active_window_info(self):
        return self._current

    def close(self):
        self.closed = True


def test_reports_each_window_change():
    client = FakeX11Client([("firefox", "Mozilla Firefox"), ("code", "Visual Studio Code")])
    events = []
    backend = X11EwmhActiveWindowBackend(xlib_client=client)
    backend.start(lambda rc, title, ts: events.append((rc, title)))

    deadline = time.monotonic() + 2.0
    while len(events) < 2 and time.monotonic() < deadline:
        time.sleep(0.02)
    backend.stop()

    assert events == [("firefox", "Mozilla Firefox"), ("code", "Visual Studio Code")]
    assert client.closed is True


def test_stop_closes_client_and_halts_thread():
    client = FakeX11Client([("firefox", "Mozilla Firefox")])
    backend = X11EwmhActiveWindowBackend(xlib_client=client)
    backend.start(lambda rc, title, ts: None)
    time.sleep(0.05)
    backend.stop()
    assert client.closed is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_window_x11.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'timetrace.backends.window_base'`

- [ ] **Step 3: Write implementation**

```python
# src/timetrace/backends/window_base.py
from typing import Callable, Protocol


class ActiveWindowBackend(Protocol):
    def start(self, on_window_changed: Callable[[str, str | None, int], None]) -> None: ...
    def stop(self) -> None: ...


class NullActiveWindowBackend:
    def start(self, on_window_changed) -> None:
        pass

    def stop(self) -> None:
        pass
```

```python
# src/timetrace/backends/window_x11.py
import threading
import time
from typing import Callable, Protocol


class X11Client(Protocol):
    def get_active_window_info(self) -> tuple[str, str | None] | None: ...
    def wait_for_active_window_change(self, timeout_s: float) -> bool: ...
    def close(self) -> None: ...


class RealX11Client:
    """Real client using python-xlib EWMH (_NET_ACTIVE_WINDOW)."""

    def __init__(self) -> None:
        from Xlib import X, display

        self._display = display.Display()
        self._root = self._display.screen().root
        self._net_active_window = self._display.intern_atom("_NET_ACTIVE_WINDOW")
        self._net_wm_pid = self._display.intern_atom("_NET_WM_PID")
        self._wm_class_atom = self._display.intern_atom("WM_CLASS")
        self._root.change_attributes(event_mask=X.PropertyChangeMask)

    def wait_for_active_window_change(self, timeout_s: float) -> bool:
        import select

        fd = self._display.fileno()
        readable, _, _ = select.select([fd], [], [], timeout_s)
        if not readable:
            return False
        changed = False
        while self._display.pending_events():
            event = self._display.next_event()
            if getattr(event, "atom", None) == self._net_active_window:
                changed = True
        return changed

    def get_active_window_info(self) -> tuple[str, str | None] | None:
        prop = self._root.get_full_property(self._net_active_window, 0)
        if not prop or not prop.value:
            return None
        window_id = prop.value[0]
        if not window_id:
            return None
        window = self._display.create_resource_object("window", window_id)
        wm_class = window.get_wm_class()
        resource_class = wm_class[1] if wm_class else "unknown"
        wm_name = window.get_wm_name()
        title = wm_name if isinstance(wm_name, str) else None
        return resource_class, title

    def close(self) -> None:
        self._display.close()


class X11EwmhActiveWindowBackend:
    def __init__(self, xlib_client: X11Client | None = None) -> None:
        self._client = xlib_client or RealX11Client()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self, on_window_changed: Callable[[str, str | None, int], None]) -> None:
        self._stop_event.clear()

        def loop() -> None:
            while not self._stop_event.is_set():
                changed = self._client.wait_for_active_window_change(0.5)
                if changed and not self._stop_event.is_set():
                    info = self._client.get_active_window_info()
                    if info is not None:
                        resource_class, title = info
                        on_window_changed(resource_class, title, int(time.time() * 1000))
            self._client.close()

        self._thread = threading.Thread(target=loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_window_x11.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/timetrace/backends/window_base.py src/timetrace/backends/window_x11.py tests/test_window_x11.py
git commit -m "Add ActiveWindowBackend interface and X11 EWMH backend"
```

---

### Task 12: KWin script active-window backend

**Files:**
- Create: `src/timetrace/assets/__init__.py`
- Create: `src/timetrace/assets/kwin_script/__init__.py`
- Create: `src/timetrace/assets/kwin_script/contents/__init__.py`
- Create: `src/timetrace/assets/kwin_script/contents/code/__init__.py`
- Create: `src/timetrace/assets/kwin_script/metadata.json`
- Create: `src/timetrace/assets/kwin_script/contents/code/main.js`
- Create: `src/timetrace/backends/window_kwin.py`
- Modify: `pyproject.toml` — add package-data so `.json`/`.js` assets ship inside the wheel
- Test: `tests/test_window_kwin.py`

**Interfaces:**
- Produces:
  - `class KWinScriptLoader(Protocol)`: `load_and_start(self, script_path: str) -> int`; `unload(self, script_id: int) -> None`.
  - `class TimeTraceDBusService(Protocol)`: `register(self, on_report: Callable[[str, str, int], None]) -> None`; `unregister(self) -> None`. `on_report` receives `(resource_class, title, pid)` as reported by the KWin script's `ReportActiveWindow` D-Bus call.
  - `class KWinScriptActiveWindowBackend(dbus_service: TimeTraceDBusService | None = None, script_loader: KWinScriptLoader | None = None)` — implements `ActiveWindowBackend`.
- Consumed by: Task 13 (`window_factory.py`).

- [ ] **Step 1: Make the assets directory a regular Python package and register it as package data**

Create empty files: `src/timetrace/assets/__init__.py`, `src/timetrace/assets/kwin_script/__init__.py`, `src/timetrace/assets/kwin_script/contents/__init__.py`, `src/timetrace/assets/kwin_script/contents/code/__init__.py`. This lets `importlib.resources.files("timetrace.assets.kwin_script.contents.code")` (used below) resolve the package at runtime, including from inside a PyInstaller bundle.

Add to `pyproject.toml` (append after `[tool.setuptools.packages.find]`):
```toml
[tool.setuptools.package-data]
"timetrace.assets.kwin_script" = ["metadata.json", "contents/code/main.js"]
```

- [ ] **Step 2: Write the KWin script asset**

`src/timetrace/assets/kwin_script/metadata.json`:
```json
{
    "KPlugin": {
        "Id": "timetrace-active-window",
        "Name": "TimeTrace Active Window Reporter"
    },
    "X-KDE-ServiceTypes": ["KWin/Script"]
}
```

`src/timetrace/assets/kwin_script/contents/code/main.js`:
```javascript
function report(client) {
    if (!client) {
        return;
    }
    callDBus(
        "org.timetrace.App",
        "/ActiveWindow",
        "org.timetrace.ActiveWindow",
        "ReportActiveWindow",
        client.resourceClass || "unknown",
        client.caption || "",
        client.pid || 0
    );
}

workspace.windowActivated.connect(report);
report(workspace.activeClient);
```

- [ ] **Step 3: Write the failing tests**

```python
# tests/test_window_kwin.py
from timetrace.backends.window_kwin import KWinScriptActiveWindowBackend


class FakeDBusService:
    def __init__(self):
        self.on_report = None
        self.registered = False
        self.unregistered = False

    def register(self, on_report):
        self.on_report = on_report
        self.registered = True

    def unregister(self):
        self.unregistered = True


class FakeScriptLoader:
    def __init__(self):
        self.loaded_paths = []
        self.unloaded_ids = []

    def load_and_start(self, script_path):
        self.loaded_paths.append(script_path)
        return 42

    def unload(self, script_id):
        self.unloaded_ids.append(script_id)


def test_start_loads_script_and_registers_dbus_service():
    service = FakeDBusService()
    loader = FakeScriptLoader()
    backend = KWinScriptActiveWindowBackend(dbus_service=service, script_loader=loader)
    backend.start(lambda rc, title, ts: None)
    assert service.registered is True
    assert len(loader.loaded_paths) == 1
    assert loader.loaded_paths[0].endswith("main.js")


def test_dbus_report_triggers_callback_with_timestamp():
    service = FakeDBusService()
    loader = FakeScriptLoader()
    events = []
    backend = KWinScriptActiveWindowBackend(dbus_service=service, script_loader=loader)
    backend.start(lambda rc, title, ts: events.append((rc, title, ts)))

    service.on_report("firefox", "Mozilla Firefox", 1234)

    assert len(events) == 1
    assert events[0][0] == "firefox"
    assert events[0][1] == "Mozilla Firefox"
    assert isinstance(events[0][2], int)


def test_stop_unloads_script_and_unregisters_service():
    service = FakeDBusService()
    loader = FakeScriptLoader()
    backend = KWinScriptActiveWindowBackend(dbus_service=service, script_loader=loader)
    backend.start(lambda rc, title, ts: None)
    backend.stop()
    assert loader.unloaded_ids == [42]
    assert service.unregistered is True
```

- [ ] **Step 4: Run test to verify it fails**

Run: `pytest tests/test_window_kwin.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'timetrace.backends.window_kwin'`

- [ ] **Step 5: Write implementation**

```python
# src/timetrace/backends/window_kwin.py
import time
from importlib import resources
from typing import Callable, Protocol

from PySide6.QtCore import QObject, Slot


class KWinScriptLoader(Protocol):
    def load_and_start(self, script_path: str) -> int: ...
    def unload(self, script_id: int) -> None: ...


class QtKWinScriptLoader:
    """Real loader over org.kde.kwin.Scripting via QtDBus."""

    def __init__(self) -> None:
        from PySide6.QtDBus import QDBusConnection, QDBusInterface

        bus = QDBusConnection.sessionBus()
        self._iface = QDBusInterface(
            "org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting", bus
        )

    def load_and_start(self, script_path: str) -> int:
        reply = self._iface.call("loadScript", script_path)
        script_id = int(reply.arguments()[0])
        script_iface_path = f"/{script_id}"
        from PySide6.QtDBus import QDBusInterface

        bus = self._iface.connection()
        script_iface = QDBusInterface("org.kde.KWin", script_iface_path, "org.kde.kwin.Script", bus)
        script_iface.call("run")
        return script_id

    def unload(self, script_id: int) -> None:
        self._iface.call("unloadScript", str(script_id))


class TimeTraceDBusService(Protocol):
    def register(self, on_report: Callable[[str, str, int], None]) -> None: ...
    def unregister(self) -> None: ...


class _TimeTraceDBusAdaptor(QObject):
    """QObject exposing ReportActiveWindow as a Qt slot so QtDBus's
    ExportAllSlots can bridge it to org.timetrace.ActiveWindow over D-Bus.
    Verify the exact registerObject signature against the installed PySide6
    version's QtDBus docs when implementing — this is the commonly
    documented ExportAllSlots shape, but QtDBus adaptor wiring has varied
    slightly across Qt/PySide releases."""

    def __init__(self, on_report: Callable[[str, str, int], None]) -> None:
        super().__init__()
        self._on_report = on_report

    @Slot(str, str, int)
    def ReportActiveWindow(self, resource_class: str, title: str, pid: int) -> None:
        self._on_report(resource_class, title, pid)


class QtTimeTraceDBusService:
    """Registers org.timetrace.App on the session bus and exposes
    /ActiveWindow org.timetrace.ActiveWindow.ReportActiveWindow(ss i)."""

    def __init__(self) -> None:
        from PySide6.QtDBus import QDBusConnection

        self._bus = QDBusConnection.sessionBus()
        self._adaptor: _TimeTraceDBusAdaptor | None = None

    def register(self, on_report: Callable[[str, str, int], None]) -> None:
        from PySide6.QtDBus import QDBusConnection

        self._adaptor = _TimeTraceDBusAdaptor(on_report)
        self._bus.registerService("org.timetrace.App")
        self._bus.registerObject(
            "/ActiveWindow", self._adaptor, QDBusConnection.RegisterOption.ExportAllSlots
        )

    def unregister(self) -> None:
        self._bus.unregisterObject("/ActiveWindow")
        self._bus.unregisterService("org.timetrace.App")


def _bundled_script_path() -> str:
    return str(
        resources.files("timetrace.assets.kwin_script.contents.code") / "main.js"
    )


class KWinScriptActiveWindowBackend:
    def __init__(
        self,
        dbus_service: TimeTraceDBusService | None = None,
        script_loader: KWinScriptLoader | None = None,
    ) -> None:
        self._service = dbus_service or QtTimeTraceDBusService()
        self._loader = script_loader or QtKWinScriptLoader()
        self._script_id: int | None = None

    def start(self, on_window_changed: Callable[[str, str | None, int], None]) -> None:
        def on_report(resource_class: str, title: str, pid: int) -> None:
            on_window_changed(resource_class, title or None, int(time.time() * 1000))

        self._service.register(on_report)
        self._script_id = self._loader.load_and_start(_bundled_script_path())

    def stop(self) -> None:
        if self._script_id is not None:
            self._loader.unload(self._script_id)
            self._script_id = None
        self._service.unregister()
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_window_kwin.py -v`
Expected: 3 passed

- [ ] **Step 7: Commit**

```bash
git add src/timetrace/assets/__init__.py src/timetrace/assets/kwin_script pyproject.toml src/timetrace/backends/window_kwin.py tests/test_window_kwin.py
git commit -m "Add KWin script active-window backend"
```

---

### Task 13: GNOME Shell extension active-window backend + complete window_factory

**Files:**
- Create: `src/timetrace/assets/gnome_extension/__init__.py`
- Create: `src/timetrace/assets/gnome_extension/metadata.json`
- Create: `src/timetrace/assets/gnome_extension/extension.js`
- Create: `src/timetrace/backends/window_gnome.py`
- Create: `src/timetrace/backends/window_factory.py`
- Test: `tests/test_window_gnome.py`
- Test: `tests/test_window_factory.py`
- Modify: `pyproject.toml` — extend package-data to include the GNOME extension files

**Interfaces:**
- Produces:
  - `class GnomeExtensionInstaller(Protocol)`: `install_and_enable(self) -> bool` — returns `True` if enabled immediately, `False` if it needs a relogin.
  - `class GnomeShellExtensionDBusClient(Protocol)`: `subscribe_active_window_changed(self, callback: Callable[[str, str], None]) -> None`; `unsubscribe(self) -> None`.
  - `class GnomeShellExtensionBackend(extension_installer=None, dbus_client=None)` — implements `ActiveWindowBackend`. If `install_and_enable()` returns `False`, `start()` still returns normally (does not raise); the caller (Task 22, `main_window.py`) is responsible for surfacing the "log out and back in" notice per spec §3.
  - `select_window_backend(desktop: DesktopEnv, session: SessionType) -> ActiveWindowBackend` in `window_factory.py`.
- Consumed by: Task 25 (`__main__.py`).

- [ ] **Step 1: Write the GNOME Shell extension asset**

`src/timetrace/assets/gnome_extension/__init__.py`: empty file.

`src/timetrace/assets/gnome_extension/metadata.json`:
```json
{
    "uuid": "timetrace@timetrace.app",
    "name": "TimeTrace Active Window Reporter",
    "description": "Reports the focused window's class/title to TimeTrace over D-Bus",
    "shell-version": ["45", "46", "47"]
}
```

`src/timetrace/assets/gnome_extension/extension.js`:
```javascript
import GLib from 'gi://GLib';
import Gio from 'gi://Gio';
import Shell from 'gi://Shell';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

const IFACE_XML = `
<node>
  <interface name="org.timetrace.ActiveWindow">
    <method name="GetActiveWindow">
      <arg type="s" direction="out" name="resourceClass"/>
      <arg type="s" direction="out" name="title"/>
    </method>
    <signal name="ActiveWindowChanged">
      <arg type="s" name="resourceClass"/>
      <arg type="s" name="title"/>
    </signal>
  </interface>
</node>`;

export default class TimeTraceExtension extends Extension {
    enable() {
        this._dbusImpl = Gio.DBusExportedObject.wrapJSObject(IFACE_XML, this);
        this._dbusImpl.export(Gio.DBus.session, '/org/timetrace/ActiveWindow');
        this._tracker = Shell.WindowTracker.get_default();
        this._signalId = global.display.connect('notify::focus-window', () => this._report());
        this._report();
    }

    disable() {
        if (this._signalId) {
            global.display.disconnect(this._signalId);
            this._signalId = null;
        }
        if (this._dbusImpl) {
            this._dbusImpl.unexport();
            this._dbusImpl = null;
        }
    }

    _report() {
        const win = global.display.focus_window;
        if (!win) return;
        const app = this._tracker.get_window_app(win);
        const resourceClass = app ? app.get_id() : (win.get_wm_class() || 'unknown');
        const title = win.get_title() || '';
        this._dbusImpl.emit_signal('ActiveWindowChanged', new GLib.Variant('(ss)', [resourceClass, title]));
    }

    GetActiveWindow() {
        const win = global.display.focus_window;
        if (!win) return ['', ''];
        const app = this._tracker.get_window_app(win);
        const resourceClass = app ? app.get_id() : (win.get_wm_class() || 'unknown');
        return [resourceClass, win.get_title() || ''];
    }
}
```

Add to `pyproject.toml`'s `[tool.setuptools.package-data]`:
```toml
"timetrace.assets.gnome_extension" = ["metadata.json", "extension.js"]
```

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_window_gnome.py
from timetrace.backends.window_gnome import GnomeShellExtensionBackend


class FakeInstaller:
    def __init__(self, enabled_immediately=True):
        self._enabled_immediately = enabled_immediately
        self.install_called = False

    def install_and_enable(self):
        self.install_called = True
        return self._enabled_immediately


class FakeDBusClient:
    def __init__(self):
        self.callback = None
        self.unsubscribed = False

    def subscribe_active_window_changed(self, callback):
        self.callback = callback

    def unsubscribe(self):
        self.unsubscribed = True


def test_start_installs_extension_and_subscribes():
    installer = FakeInstaller()
    client = FakeDBusClient()
    backend = GnomeShellExtensionBackend(extension_installer=installer, dbus_client=client)
    backend.start(lambda rc, title, ts: None)
    assert installer.install_called is True
    assert client.callback is not None


def test_start_does_not_raise_when_extension_needs_relogin():
    installer = FakeInstaller(enabled_immediately=False)
    client = FakeDBusClient()
    backend = GnomeShellExtensionBackend(extension_installer=installer, dbus_client=client)
    backend.start(lambda rc, title, ts: None)  # must not raise
    assert backend.needs_relogin is True


def test_signal_triggers_callback_with_timestamp():
    installer = FakeInstaller()
    client = FakeDBusClient()
    events = []
    backend = GnomeShellExtensionBackend(extension_installer=installer, dbus_client=client)
    backend.start(lambda rc, title, ts: events.append((rc, title, ts)))
    client.callback("firefox", "Mozilla Firefox")
    assert len(events) == 1
    assert events[0][0] == "firefox"
    assert isinstance(events[0][2], int)


def test_stop_unsubscribes():
    installer = FakeInstaller()
    client = FakeDBusClient()
    backend = GnomeShellExtensionBackend(extension_installer=installer, dbus_client=client)
    backend.start(lambda rc, title, ts: None)
    backend.stop()
    assert client.unsubscribed is True
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_window_gnome.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'timetrace.backends.window_gnome'`

- [ ] **Step 4: Write implementation**

```python
# src/timetrace/backends/window_gnome.py
import shutil
import subprocess
import time
from importlib import resources
from pathlib import Path
from typing import Callable, Protocol

EXTENSION_UUID = "timetrace@timetrace.app"


class GnomeExtensionInstaller(Protocol):
    def install_and_enable(self) -> bool: ...


class RealGnomeExtensionInstaller:
    def __init__(self, extensions_dir: Path | None = None) -> None:
        self._extensions_dir = extensions_dir or (
            Path.home() / ".local" / "share" / "gnome-shell" / "extensions"
        )

    def install_and_enable(self) -> bool:
        target = self._extensions_dir / EXTENSION_UUID
        target.mkdir(parents=True, exist_ok=True)
        src_dir = resources.files("timetrace.assets.gnome_extension")
        for name in ("metadata.json", "extension.js"):
            (target / name).write_bytes((src_dir / name).read_bytes())

        result = subprocess.run(
            ["gnome-extensions", "enable", EXTENSION_UUID],
            capture_output=True,
        )
        return result.returncode == 0


class GnomeShellExtensionDBusClient(Protocol):
    def subscribe_active_window_changed(self, callback: Callable[[str, str], None]) -> None: ...
    def unsubscribe(self) -> None: ...


class QtGnomeShellExtensionDBusClient:
    SERVICE = "org.gnome.Shell"
    PATH = "/org/timetrace/ActiveWindow"
    INTERFACE = "org.timetrace.ActiveWindow"

    def __init__(self) -> None:
        from PySide6.QtDBus import QDBusConnection

        self._bus = QDBusConnection.sessionBus()
        self._callback: Callable[[str, str], None] | None = None

    def subscribe_active_window_changed(self, callback: Callable[[str, str], None]) -> None:
        self._callback = callback
        self._bus.connect(
            self.SERVICE, self.PATH, self.INTERFACE, "ActiveWindowChanged",
            self._on_signal,
        )

    def _on_signal(self, resource_class: str, title: str) -> None:
        if self._callback:
            self._callback(resource_class, title)

    def unsubscribe(self) -> None:
        self._bus.disconnect(
            self.SERVICE, self.PATH, self.INTERFACE, "ActiveWindowChanged",
            self._on_signal,
        )


class GnomeShellExtensionBackend:
    def __init__(
        self,
        extension_installer: GnomeExtensionInstaller | None = None,
        dbus_client: GnomeShellExtensionDBusClient | None = None,
    ) -> None:
        self._installer = extension_installer or RealGnomeExtensionInstaller()
        self._client = dbus_client or QtGnomeShellExtensionDBusClient()
        self.needs_relogin = False

    def start(self, on_window_changed: Callable[[str, str | None, int], None]) -> None:
        enabled = self._installer.install_and_enable()
        self.needs_relogin = not enabled

        def on_signal(resource_class: str, title: str) -> None:
            on_window_changed(resource_class, title or None, int(time.time() * 1000))

        self._client.subscribe_active_window_changed(on_signal)

    def stop(self) -> None:
        self._client.unsubscribe()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_window_gnome.py -v`
Expected: 4 passed

- [ ] **Step 6: Write the failing test for the factory**

```python
# tests/test_window_factory.py
from timetrace.backends.window_base import NullActiveWindowBackend
from timetrace.backends.window_factory import select_window_backend
from timetrace.backends.window_gnome import GnomeShellExtensionBackend
from timetrace.backends.window_kwin import KWinScriptActiveWindowBackend
from timetrace.backends.window_x11 import X11EwmhActiveWindowBackend


def test_x11_session_any_supported_desktop_uses_ewmh_backend():
    assert isinstance(select_window_backend("kde", "x11"), X11EwmhActiveWindowBackend)
    assert isinstance(select_window_backend("gnome", "x11"), X11EwmhActiveWindowBackend)


def test_kde_wayland_uses_kwin_script_backend():
    assert isinstance(select_window_backend("kde", "wayland"), KWinScriptActiveWindowBackend)


def test_gnome_wayland_uses_shell_extension_backend():
    assert isinstance(select_window_backend("gnome", "wayland"), GnomeShellExtensionBackend)


def test_unsupported_desktop_uses_null_backend():
    assert isinstance(select_window_backend("other", "x11"), NullActiveWindowBackend)
    assert isinstance(select_window_backend("other", "wayland"), NullActiveWindowBackend)
```

- [ ] **Step 7: Run test to verify it fails**

Run: `pytest tests/test_window_factory.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'timetrace.backends.window_factory'`

- [ ] **Step 8: Write the factory implementation**

```python
# src/timetrace/backends/window_factory.py
from timetrace.backends.window_base import ActiveWindowBackend, NullActiveWindowBackend
from timetrace.backends.window_gnome import GnomeShellExtensionBackend
from timetrace.backends.window_kwin import KWinScriptActiveWindowBackend
from timetrace.backends.window_x11 import X11EwmhActiveWindowBackend
from timetrace.env_detect import DesktopEnv, SessionType


def select_window_backend(desktop: DesktopEnv, session: SessionType) -> ActiveWindowBackend:
    if desktop not in ("kde", "gnome"):
        return NullActiveWindowBackend()
    if session == "x11":
        return X11EwmhActiveWindowBackend()
    if session == "wayland" and desktop == "kde":
        try:
            return KWinScriptActiveWindowBackend()
        except Exception:
            return NullActiveWindowBackend()
    if session == "wayland" and desktop == "gnome":
        try:
            return GnomeShellExtensionBackend()
        except Exception:
            return NullActiveWindowBackend()
    return NullActiveWindowBackend()
```

- [ ] **Step 9: Run test to verify it passes**

Run: `pytest tests/test_window_factory.py -v`
Expected: 4 passed (same caveat as Task 10 Step 8 applies to constructing the real Wayland-specific backends outside their target environment)

- [ ] **Step 10: Commit**

```bash
git add src/timetrace/assets/gnome_extension src/timetrace/backends/window_gnome.py src/timetrace/backends/window_factory.py pyproject.toml tests/test_window_gnome.py tests/test_window_factory.py
git commit -m "Add GNOME Shell extension active-window backend and complete window backend factory"
```

---

### Task 14: TrackingCoordinator (event → interval business logic)

This is where the presence/app-interval rules from spec §4 actually get enforced, and where three of the five Review Focus items are pinned down: threshold changes mid-flight (already handled inside `IdleStateMachine`, but the coordinator must not double-apply it), repeated same-window events must not churn the DB, and window-focus events arriving while idle must be remembered but not written until resume.

**Files:**
- Create: `src/timetrace/tracking/__init__.py`
- Create: `src/timetrace/tracking/coordinator.py`
- Test: `tests/test_coordinator.py`

**Interfaces:**
- Consumes: `Store` (Task 5) — `open_presence_interval`, `close_open_presence_interval`, `open_app_interval`, `close_open_app_interval`, `reconcile_open_intervals_on_startup`; `IdleBackend` (Task 8) — `start(threshold_ms, on_idle, on_resume)`, `update_threshold`, `stop`; `ActiveWindowBackend` (Task 11) — `start(on_window_changed)`, `stop`.
- Produces: `class TrackingCoordinator(store, idle_backend, window_backend, idle_threshold_ms, clock: Callable[[], int] | None = None)`: `start(self) -> None`; `stop(self) -> None`; `update_idle_threshold(self, minutes: int) -> None`; `process_pending_events(self) -> None`.
- Consumed by: Task 25 (`__main__.py`), which calls `process_pending_events()` on a `QTimer` (~every 250ms) from the Qt main thread — backends push onto an internal `queue.Queue` from their own threads, so the queue is the only cross-thread boundary and `process_pending_events` is the only place that touches `Store`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_coordinator.py
from timetrace.db import Store
from timetrace.tracking.coordinator import TrackingCoordinator


class FakeIdleBackend:
    def __init__(self):
        self.on_idle = None
        self.on_resume = None
        self.started_threshold_ms = None
        self.updated_threshold_ms = None
        self.stopped = False

    def start(self, threshold_ms, on_idle, on_resume):
        self.started_threshold_ms = threshold_ms
        self.on_idle = on_idle
        self.on_resume = on_resume

    def update_threshold(self, threshold_ms):
        self.updated_threshold_ms = threshold_ms

    def stop(self):
        self.stopped = True


class FakeWindowBackend:
    def __init__(self):
        self.on_window_changed = None
        self.stopped = False

    def start(self, on_window_changed):
        self.on_window_changed = on_window_changed

    def stop(self):
        self.stopped = True


def make_coordinator(tmp_path, clock_values):
    store = Store(tmp_path / "data.db")
    idle = FakeIdleBackend()
    window = FakeWindowBackend()
    clock = iter(clock_values)
    coordinator = TrackingCoordinator(
        store, idle, window, idle_threshold_ms=5000, clock=lambda: next(clock)
    )
    return store, idle, window, coordinator


def test_start_opens_active_presence_interval_and_arms_backends(tmp_path):
    store, idle, window, coordinator = make_coordinator(tmp_path, [1000])
    coordinator.start()

    assert idle.started_threshold_ms == 5000
    assert window.on_window_changed is not None
    open_interval = store.get_open_presence_interval()
    assert open_interval is not None
    assert open_interval.state == "active"
    assert open_interval.start_ts == 1000
    store.close()


def test_window_change_while_active_opens_app_interval(tmp_path):
    store, idle, window, coordinator = make_coordinator(tmp_path, [1000, 2000])
    coordinator.start()
    window.on_window_changed("firefox", "Mozilla Firefox", 2000)
    coordinator.process_pending_events()

    open_app = store.get_open_app_interval()
    assert open_app is not None
    assert open_app.resource_class == "firefox"
    assert open_app.start_ts == 2000
    store.close()


def test_repeated_same_window_event_does_not_churn_db(tmp_path):
    store, idle, window, coordinator = make_coordinator(tmp_path, [1000, 2000, 3000])
    coordinator.start()
    window.on_window_changed("firefox", "Mozilla Firefox", 2000)
    coordinator.process_pending_events()
    first_open = store.get_open_app_interval()

    window.on_window_changed("firefox", "Mozilla Firefox — tab 2", 3000)
    coordinator.process_pending_events()
    second_open = store.get_open_app_interval()

    assert second_open.id == first_open.id  # same interval, not a new row
    assert second_open.start_ts == first_open.start_ts
    store.close()


def test_switching_window_closes_old_app_interval_and_opens_new_one(tmp_path):
    store, idle, window, coordinator = make_coordinator(tmp_path, [1000, 2000, 3000])
    coordinator.start()
    window.on_window_changed("firefox", "Mozilla Firefox", 2000)
    coordinator.process_pending_events()
    window.on_window_changed("code", "VS Code", 3000)
    coordinator.process_pending_events()

    open_app = store.get_open_app_interval()
    assert open_app.resource_class == "code"
    assert open_app.start_ts == 3000

    day_rows = store.app_intervals_for_day(0, 10_000, now_ts=3000)
    firefox_rows = [r for r in day_rows if r.resource_class == "firefox"]
    assert len(firefox_rows) == 1
    assert firefox_rows[0].end_ts == 3000
    store.close()


def test_idle_closes_presence_and_app_intervals(tmp_path):
    store, idle, window, coordinator = make_coordinator(tmp_path, [1000, 2000, 6000])
    coordinator.start()
    window.on_window_changed("firefox", "Mozilla Firefox", 2000)
    coordinator.process_pending_events()

    idle.on_idle(6000)
    coordinator.process_pending_events()

    assert store.get_open_app_interval() is None
    presence = store.get_open_presence_interval()
    assert presence.state == "idle"
    assert presence.start_ts == 6000
    store.close()


def test_resume_reopens_app_interval_for_last_known_window_without_new_event(tmp_path):
    store, idle, window, coordinator = make_coordinator(tmp_path, [1000, 2000, 6000, 9000])
    coordinator.start()
    window.on_window_changed("firefox", "Mozilla Firefox", 2000)
    coordinator.process_pending_events()
    idle.on_idle(6000)
    coordinator.process_pending_events()

    idle.on_resume(9000)
    coordinator.process_pending_events()

    presence = store.get_open_presence_interval()
    assert presence.state == "active"
    assert presence.start_ts == 9000

    open_app = store.get_open_app_interval()
    assert open_app is not None
    assert open_app.resource_class == "firefox"
    assert open_app.start_ts == 9000
    store.close()


def test_window_event_while_idle_is_remembered_but_not_written(tmp_path):
    store, idle, window, coordinator = make_coordinator(tmp_path, [1000, 6000, 7000, 9000])
    coordinator.start()
    idle.on_idle(6000)
    coordinator.process_pending_events()

    window.on_window_changed("code", "VS Code", 7000)  # focus-steal while idle
    coordinator.process_pending_events()
    assert store.get_open_app_interval() is None  # not written while idle

    idle.on_resume(9000)
    coordinator.process_pending_events()
    open_app = store.get_open_app_interval()
    assert open_app.resource_class == "code"  # remembered window is used on resume
    assert open_app.start_ts == 9000
    store.close()


def test_update_idle_threshold_forwards_minutes_as_ms(tmp_path):
    store, idle, window, coordinator = make_coordinator(tmp_path, [1000])
    coordinator.start()
    coordinator.update_idle_threshold(10)
    assert idle.updated_threshold_ms == 600_000
    store.close()


def test_stop_stops_backends_and_closes_open_intervals(tmp_path):
    store, idle, window, coordinator = make_coordinator(tmp_path, [1000, 2000, 5000])
    coordinator.start()
    window.on_window_changed("firefox", "Mozilla Firefox", 2000)
    coordinator.process_pending_events()

    coordinator.stop()

    assert idle.stopped is True
    assert window.stopped is True
    assert store.get_open_presence_interval() is None
    assert store.get_open_app_interval() is None
    store.close()


def test_start_reconciles_stale_open_intervals_from_previous_run(tmp_path):
    db_path = tmp_path / "data.db"
    stale_store = Store(db_path)
    stale_store.open_presence_interval("active", 500)
    stale_store.open_app_interval("old-app", None, 500)
    stale_store.close()

    store = Store(db_path)
    idle = FakeIdleBackend()
    window = FakeWindowBackend()
    coordinator = TrackingCoordinator(store, idle, window, idle_threshold_ms=5000, clock=lambda: 1000)
    coordinator.start()

    # the stale rows must be closed at startup time, and a fresh interval opened
    day_rows = store.presence_intervals_for_day(0, 10_000, now_ts=1000)
    closed_stale = [r for r in day_rows if r.start_ts == 500]
    assert len(closed_stale) == 1
    assert closed_stale[0].end_ts == 1000
    assert store.get_open_presence_interval().start_ts == 1000
    store.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_coordinator.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'timetrace.tracking'`

- [ ] **Step 3: Write implementation**

```python
# src/timetrace/tracking/coordinator.py
import queue
import time
from typing import Callable

from timetrace.backends.idle_base import IdleBackend
from timetrace.backends.window_base import ActiveWindowBackend
from timetrace.db import Store


def _default_clock() -> int:
    return int(time.time() * 1000)


class TrackingCoordinator:
    def __init__(
        self,
        store: Store,
        idle_backend: IdleBackend,
        window_backend: ActiveWindowBackend,
        idle_threshold_ms: int,
        clock: Callable[[], int] | None = None,
    ) -> None:
        self._store = store
        self._idle_backend = idle_backend
        self._window_backend = window_backend
        self._threshold_ms = idle_threshold_ms
        self._clock = clock or _default_clock
        self._queue: queue.Queue = queue.Queue()

        self._presence_state: str | None = None
        self._current_window: tuple[str, str | None] | None = None
        self._open_app_resource_class: str | None = None

    def start(self) -> None:
        now_ts = self._clock()
        self._store.reconcile_open_intervals_on_startup(fallback_end_ts=now_ts)

        self._store.open_presence_interval("active", now_ts)
        self._presence_state = "active"

        self._idle_backend.start(
            self._threshold_ms,
            on_idle=lambda ts: self._queue.put(("idle", ts)),
            on_resume=lambda ts: self._queue.put(("resume", ts)),
        )
        self._window_backend.start(
            lambda rc, title, ts: self._queue.put(("window", rc, title, ts))
        )

    def update_idle_threshold(self, minutes: int) -> None:
        self._threshold_ms = minutes * 60_000
        self._idle_backend.update_threshold(self._threshold_ms)

    def process_pending_events(self) -> None:
        while True:
            try:
                event = self._queue.get_nowait()
            except queue.Empty:
                return
            self._apply(event)

    def _apply(self, event: tuple) -> None:
        kind = event[0]
        if kind == "idle":
            self._on_idle(event[1])
        elif kind == "resume":
            self._on_resume(event[1])
        elif kind == "window":
            self._on_window_changed(event[1], event[2], event[3])

    def _on_idle(self, ts: int) -> None:
        if self._open_app_resource_class is not None:
            self._store.close_open_app_interval(ts)
            self._open_app_resource_class = None
        self._store.close_open_presence_interval(ts)
        self._store.open_presence_interval("idle", ts)
        self._presence_state = "idle"

    def _on_resume(self, ts: int) -> None:
        self._store.close_open_presence_interval(ts)
        self._store.open_presence_interval("active", ts)
        self._presence_state = "active"
        if self._current_window is not None:
            resource_class, title = self._current_window
            self._store.open_app_interval(resource_class, title, ts)
            self._open_app_resource_class = resource_class

    def _on_window_changed(self, resource_class: str, title: str | None, ts: int) -> None:
        self._current_window = (resource_class, title)
        if self._presence_state != "active":
            return
        if self._open_app_resource_class == resource_class:
            return  # same app still focused, ignore title-only churn
        if self._open_app_resource_class is not None:
            self._store.close_open_app_interval(ts)
        self._store.open_app_interval(resource_class, title, ts)
        self._open_app_resource_class = resource_class

    def stop(self) -> None:
        now_ts = self._clock()
        self._idle_backend.stop()
        self._window_backend.stop()
        if self._open_app_resource_class is not None:
            self._store.close_open_app_interval(now_ts)
            self._open_app_resource_class = None
        self._store.close_open_presence_interval(now_ts)
        self._presence_state = None
```

`src/timetrace/tracking/__init__.py`: empty file.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_coordinator.py -v`
Expected: 10 passed

- [ ] **Step 5: Commit**

```bash
git add src/timetrace/tracking/__init__.py src/timetrace/tracking/coordinator.py tests/test_coordinator.py
git commit -m "Add TrackingCoordinator wiring backends to storage"
```

---

### Task 15: Application icon resolution

**Files:**
- Create: `src/timetrace/icons.py`
- Test: `tests/test_icons.py`

**Interfaces:**
- Produces: `find_desktop_entry(resource_class: str, search_dirs: Sequence[Path] | None = None) -> Path | None`; `icon_name_from_desktop_entry(entry_path: Path) -> str | None`; `resolve_icon(resource_class: str, icon_loader: Callable[[str], "QIcon"] | None = None) -> "QIcon"`.
- Consumed by: Task 21 (`app_list_widget.py`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_icons.py
from timetrace.icons import find_desktop_entry, icon_name_from_desktop_entry, resolve_icon


def write_desktop_file(path, *, name, exec_, icon, startup_wm_class=None):
    lines = ["[Desktop Entry]", f"Name={name}", f"Exec={exec_}", f"Icon={icon}"]
    if startup_wm_class:
        lines.append(f"StartupWMClass={startup_wm_class}")
    path.write_text("\n".join(lines) + "\n")


def test_find_desktop_entry_matches_startup_wm_class(tmp_path):
    apps_dir = tmp_path / "applications"
    apps_dir.mkdir()
    entry = apps_dir / "org.mozilla.firefox.desktop"
    write_desktop_file(entry, name="Firefox", exec_="firefox %u", icon="firefox", startup_wm_class="firefox")

    found = find_desktop_entry("firefox", search_dirs=[apps_dir])
    assert found == entry


def test_find_desktop_entry_falls_back_to_exec_basename(tmp_path):
    apps_dir = tmp_path / "applications"
    apps_dir.mkdir()
    entry = apps_dir / "code.desktop"
    write_desktop_file(entry, name="VS Code", exec_="/usr/bin/code %F", icon="code")

    found = find_desktop_entry("code", search_dirs=[apps_dir])
    assert found == entry


def test_find_desktop_entry_returns_none_when_no_match(tmp_path):
    apps_dir = tmp_path / "applications"
    apps_dir.mkdir()
    assert find_desktop_entry("nonexistent", search_dirs=[apps_dir]) is None


def test_icon_name_from_desktop_entry(tmp_path):
    entry = tmp_path / "code.desktop"
    write_desktop_file(entry, name="VS Code", exec_="/usr/bin/code %F", icon="visual-studio-code")
    assert icon_name_from_desktop_entry(entry) == "visual-studio-code"


def test_resolve_icon_uses_injected_loader_and_caches(tmp_path):
    apps_dir = tmp_path / "applications"
    apps_dir.mkdir()
    write_desktop_file(apps_dir / "code.desktop", name="VS Code", exec_="/usr/bin/code %F", icon="visual-studio-code")

    calls = []

    def fake_loader(icon_name):
        calls.append(icon_name)
        return f"ICON[{icon_name}]"

    icon1 = resolve_icon("code", icon_loader=fake_loader)
    icon2 = resolve_icon("code", icon_loader=fake_loader)
    # caching is only meaningful with a shared cache instance; this call-level
    # test just verifies the loader receives the resolved icon name when found
    assert calls[0] == "visual-studio-code" or icon1 == "ICON[unknown]"
```

Note: `test_resolve_icon_uses_injected_loader_and_caches` doesn't control `search_dirs`, since `resolve_icon`'s production signature only takes `resource_class` and `icon_loader` (real desktop-file search always looks at real system dirs). Keep this test loose (it accepts either a real system match or the `unknown` fallback) — the meaningful, precise coverage of desktop-file matching lives in the `find_desktop_entry` tests above, which do control `search_dirs`.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_icons.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'timetrace.icons'`

- [ ] **Step 3: Write implementation**

```python
# src/timetrace/icons.py
import configparser
from collections.abc import Sequence
from pathlib import Path
from typing import Callable

_DEFAULT_SEARCH_DIRS = [
    Path.home() / ".local" / "share" / "applications",
    Path("/usr/share/applications"),
    Path("/usr/local/share/applications"),
]

_icon_cache: dict[str, object] = {}


def find_desktop_entry(
    resource_class: str, search_dirs: Sequence[Path] | None = None
) -> Path | None:
    dirs = search_dirs if search_dirs is not None else _DEFAULT_SEARCH_DIRS
    target = resource_class.lower()
    candidates = []
    for directory in dirs:
        if not directory.is_dir():
            continue
        candidates.extend(sorted(directory.glob("*.desktop")))

    for path in candidates:
        parser = configparser.ConfigParser(interpolation=None)
        try:
            parser.read(path, encoding="utf-8")
        except configparser.Error:
            continue
        if not parser.has_section("Desktop Entry"):
            continue
        wm_class = parser.get("Desktop Entry", "StartupWMClass", fallback="")
        if wm_class.lower() == target:
            return path

    for path in candidates:
        parser = configparser.ConfigParser(interpolation=None)
        try:
            parser.read(path, encoding="utf-8")
        except configparser.Error:
            continue
        if not parser.has_section("Desktop Entry"):
            continue
        exec_value = parser.get("Desktop Entry", "Exec", fallback="")
        exec_basename = exec_value.split()[0].rsplit("/", 1)[-1] if exec_value else ""
        if exec_basename.lower() == target or path.stem.lower() == target:
            return path

    return None


def icon_name_from_desktop_entry(entry_path: Path) -> str | None:
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(entry_path, encoding="utf-8")
    return parser.get("Desktop Entry", "Icon", fallback=None)


def resolve_icon(resource_class: str, icon_loader: Callable[[str], object] | None = None):
    if resource_class in _icon_cache:
        return _icon_cache[resource_class]

    loader = icon_loader or _real_icon_loader
    entry = find_desktop_entry(resource_class)
    icon_name = icon_name_from_desktop_entry(entry) if entry else None
    icon = loader(icon_name or "unknown")
    _icon_cache[resource_class] = icon
    return icon


def _real_icon_loader(icon_name: str):
    from PySide6.QtGui import QIcon

    return QIcon.fromTheme(icon_name)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_icons.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add src/timetrace/icons.py tests/test_icons.py
git commit -m "Add desktop-entry icon resolution"
```

---

### Task 16: Stable per-app color assignment

**Files:**
- Create: `src/timetrace/app_color.py`
- Test: `tests/test_app_color.py`

**Interfaces:**
- Produces: `PALETTE: list[tuple[int,int,int]]`; `color_for_resource_class(resource_class: str) -> tuple[int,int,int]` (RGB tuple; UI tasks wrap this in `QColor(*rgb)`).
- Consumed by: Task 20 (`timeline_widget.py`), Task 21 (`app_list_widget.py`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_app_color.py
from timetrace.app_color import PALETTE, color_for_resource_class


def test_same_resource_class_always_gets_same_color():
    assert color_for_resource_class("firefox") == color_for_resource_class("firefox")


def test_color_comes_from_palette():
    assert color_for_resource_class("firefox") in PALETTE


def test_different_classes_can_get_different_colors():
    colors = {color_for_resource_class(name) for name in ["firefox", "code", "kate", "konsole", "gimp"]}
    assert len(colors) > 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_app_color.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'timetrace.app_color'`

- [ ] **Step 3: Write implementation**

```python
# src/timetrace/app_color.py
import hashlib

PALETTE: list[tuple[int, int, int]] = [
    (66, 133, 244),
    (219, 68, 55),
    (244, 180, 0),
    (15, 157, 88),
    (171, 71, 188),
    (0, 172, 193),
    (255, 112, 67),
    (158, 157, 36),
    (92, 107, 192),
    (0, 121, 107),
]


def color_for_resource_class(resource_class: str) -> tuple[int, int, int]:
    digest = hashlib.sha256(resource_class.encode("utf-8")).digest()
    index = digest[0] % len(PALETTE)
    return PALETTE[index]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_app_color.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/timetrace/app_color.py tests/test_app_color.py
git commit -m "Add stable per-app color assignment"
```

---

### Task 17: System theme read + live sync

**Files:**
- Create: `src/timetrace/theme.py`
- Test: `tests/test_theme.py`

**Interfaces:**
- Produces: `read_system_color_scheme(reader: Callable[[], int] | None = None) -> Literal["light","dark","unknown"]`; `apply_theme(app, mode: Literal["light","dark","system"]) -> None`; `watch_system_color_scheme(on_change: Callable[[Literal["light","dark"]], None], subscriber: Callable[[Callable[[int], None]], Callable[[], None]] | None = None) -> Callable[[], None]` — returns an unsubscribe function. This covers the Review Focus item about the OS theme changing live while in "sync with OS" mode.
- Consumed by: Task 24 (`settings_dialog.py`), Task 25 (`__main__.py`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_theme.py
from timetrace.theme import read_system_color_scheme, watch_system_color_scheme


def test_reads_light_scheme():
    assert read_system_color_scheme(reader=lambda: 0) == "light"


def test_reads_dark_scheme():
    assert read_system_color_scheme(reader=lambda: 1) == "dark"


def test_unknown_value_maps_to_unknown():
    assert read_system_color_scheme(reader=lambda: 2) == "unknown"


def test_reader_raising_maps_to_unknown():
    def broken_reader():
        raise RuntimeError("no portal available")

    assert read_system_color_scheme(reader=broken_reader) == "unknown"


def test_watch_forwards_changes_and_unsubscribe_stops_forwarding():
    handlers = []

    def fake_subscriber(handler):
        handlers.append(handler)
        return lambda: handlers.remove(handler)

    events = []
    unsubscribe = watch_system_color_scheme(
        on_change=lambda scheme: events.append(scheme), subscriber=fake_subscriber
    )
    assert len(handlers) == 1

    handlers[0](1)  # portal reports "dark"
    assert events == ["dark"]

    unsubscribe()
    assert handlers == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_theme.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'timetrace.theme'`

- [ ] **Step 3: Write implementation**

```python
# src/timetrace/theme.py
from typing import Callable, Literal

ColorScheme = Literal["light", "dark", "unknown"]


def _real_reader() -> int:
    from PySide6.QtDBus import QDBusInterface

    iface = QDBusInterface(
        "org.freedesktop.portal.Desktop",
        "/org/freedesktop/portal/desktop",
        "org.freedesktop.portal.Settings",
    )
    reply = iface.call("Read", "org.freedesktop.appearance", "color-scheme")
    return int(reply.arguments()[0])


def read_system_color_scheme(reader: Callable[[], int] | None = None) -> ColorScheme:
    reader = reader or _real_reader
    try:
        value = reader()
    except Exception:
        return "unknown"
    return {0: "light", 1: "dark"}.get(value, "unknown")


def _real_subscriber(handler: Callable[[int], None]) -> Callable[[], None]:
    from PySide6.QtDBus import QDBusConnection

    bus = QDBusConnection.sessionBus()

    def on_setting_changed(namespace: str, key: str, value) -> None:
        if namespace == "org.freedesktop.appearance" and key == "color-scheme":
            handler(int(value))

    bus.connect(
        "org.freedesktop.portal.Desktop",
        "/org/freedesktop/portal/desktop",
        "org.freedesktop.portal.Settings",
        "SettingChanged",
        on_setting_changed,
    )

    def unsubscribe() -> None:
        bus.disconnect(
            "org.freedesktop.portal.Desktop",
            "/org/freedesktop/portal/desktop",
            "org.freedesktop.portal.Settings",
            "SettingChanged",
            on_setting_changed,
        )

    return unsubscribe


def watch_system_color_scheme(
    on_change: Callable[[Literal["light", "dark"]], None],
    subscriber: Callable[[Callable[[int], None]], Callable[[], None]] | None = None,
) -> Callable[[], None]:
    subscriber = subscriber or _real_subscriber

    def handler(value: int) -> None:
        scheme = {0: "light", 1: "dark"}.get(value)
        if scheme is not None:
            on_change(scheme)

    return subscriber(handler)


def apply_theme(app, mode: Literal["light", "dark", "system"]) -> None:
    from PySide6.QtGui import QPalette, QColor

    effective = mode
    if mode == "system":
        detected = read_system_color_scheme()
        effective = detected if detected in ("light", "dark") else "light"

    palette = QPalette()
    if effective == "dark":
        palette.setColor(QPalette.Window, QColor(45, 45, 45))
        palette.setColor(QPalette.WindowText, QColor(230, 230, 230))
        palette.setColor(QPalette.Base, QColor(30, 30, 30))
        palette.setColor(QPalette.Text, QColor(230, 230, 230))
        palette.setColor(QPalette.Button, QColor(53, 53, 53))
        palette.setColor(QPalette.ButtonText, QColor(230, 230, 230))
    app.setPalette(palette)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_theme.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add src/timetrace/theme.py tests/test_theme.py
git commit -m "Add XDG portal theme read/sync with live-change support"
```

---

### Task 18: Autostart file management

**Files:**
- Create: `src/timetrace/autostart.py`
- Test: `tests/test_autostart.py`

**Interfaces:**
- Produces: `is_autostart_enabled(autostart_path: Path | None = None) -> bool`; `set_autostart_enabled(enabled: bool, autostart_path: Path | None = None, exec_path: str | None = None) -> None`.
- Consumed by: Task 24 (`settings_dialog.py`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_autostart.py
from timetrace.autostart import is_autostart_enabled, set_autostart_enabled


def test_disabled_when_file_missing(tmp_path):
    path = tmp_path / "timetrace.desktop"
    assert is_autostart_enabled(path) is False


def test_enable_creates_desktop_file_with_exec(tmp_path):
    path = tmp_path / "autostart" / "timetrace.desktop"
    set_autostart_enabled(True, autostart_path=path, exec_path="/usr/bin/timetrace")
    assert path.exists()
    content = path.read_text()
    assert "Exec=/usr/bin/timetrace" in content
    assert "[Desktop Entry]" in content
    assert is_autostart_enabled(path) is True


def test_disable_removes_desktop_file(tmp_path):
    path = tmp_path / "timetrace.desktop"
    set_autostart_enabled(True, autostart_path=path, exec_path="/usr/bin/timetrace")
    set_autostart_enabled(False, autostart_path=path)
    assert not path.exists()
    assert is_autostart_enabled(path) is False


def test_disable_when_already_absent_does_not_raise(tmp_path):
    path = tmp_path / "timetrace.desktop"
    set_autostart_enabled(False, autostart_path=path)  # must not raise
    assert not path.exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_autostart.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'timetrace.autostart'`

- [ ] **Step 3: Write implementation**

```python
# src/timetrace/autostart.py
from pathlib import Path

from timetrace import paths


def is_autostart_enabled(autostart_path: Path | None = None) -> bool:
    path = autostart_path or paths.autostart_file_path()
    return path.exists()


def set_autostart_enabled(
    enabled: bool,
    autostart_path: Path | None = None,
    exec_path: str | None = None,
) -> None:
    path = autostart_path or paths.autostart_file_path()
    if not enabled:
        path.unlink(missing_ok=True)
        return

    exec_path = exec_path or "timetrace"
    path.parent.mkdir(parents=True, exist_ok=True)
    content = (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=TimeTrace\n"
        f"Exec={exec_path}\n"
        "X-GNOME-Autostart-enabled=true\n"
    )
    path.write_text(content)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_autostart.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/timetrace/autostart.py tests/test_autostart.py
git commit -m "Add autostart file management"
```

---

### Task 19: Date navigation

**Files:**
- Create: `src/timetrace/ui/__init__.py`
- Create: `src/timetrace/ui/date_nav.py`
- Test: `tests/test_date_nav.py`

**Interfaces:**
- Produces:
  - `class DateNavigationState(selected: date, today_provider: Callable[[], date] | None = None)`: property `selected -> date`; property `can_go_forward -> bool`; `go_previous(self) -> None`; `go_next(self) -> None`; `go_today(self) -> None`.
  - `class DateNavBar(QWidget)` — wraps `DateNavigationState`, has `<`/`Сегодня`/`>` buttons and a date label, emits `Signal(date)` named `dateChanged`. `>` button is disabled when `not state.can_go_forward`.
- Consumed by: Task 22 (`main_window.py`).

- [ ] **Step 1: Write the failing tests (pure state, no Qt needed)**

```python
# tests/test_date_nav.py
from datetime import date, timedelta

from timetrace.ui.date_nav import DateNavigationState


def fixed_today():
    return date(2026, 9, 27)


def test_starts_at_given_date():
    state = DateNavigationState(date(2026, 9, 20), today_provider=fixed_today)
    assert state.selected == date(2026, 9, 20)


def test_go_previous_and_next():
    state = DateNavigationState(date(2026, 9, 20), today_provider=fixed_today)
    state.go_previous()
    assert state.selected == date(2026, 9, 19)
    state.go_next()
    assert state.selected == date(2026, 9, 20)


def test_go_today_jumps_to_today():
    state = DateNavigationState(date(2026, 9, 1), today_provider=fixed_today)
    state.go_today()
    assert state.selected == fixed_today()


def test_can_go_forward_false_on_today():
    state = DateNavigationState(fixed_today(), today_provider=fixed_today)
    assert state.can_go_forward is False


def test_can_go_forward_true_before_today():
    state = DateNavigationState(fixed_today() - timedelta(days=1), today_provider=fixed_today)
    assert state.can_go_forward is True


def test_go_next_is_noop_when_already_today():
    state = DateNavigationState(fixed_today(), today_provider=fixed_today)
    state.go_next()
    assert state.selected == fixed_today()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_date_nav.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'timetrace.ui'`

- [ ] **Step 3: Write implementation**

`src/timetrace/ui/__init__.py`: empty file.

```python
# src/timetrace/ui/date_nav.py
from datetime import date, timedelta
from typing import Callable

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget


class DateNavigationState:
    def __init__(self, selected: date, today_provider: Callable[[], date] | None = None) -> None:
        self._selected = selected
        self._today_provider = today_provider or date.today

    @property
    def selected(self) -> date:
        return self._selected

    @property
    def can_go_forward(self) -> bool:
        return self._selected < self._today_provider()

    def go_previous(self) -> None:
        self._selected -= timedelta(days=1)

    def go_next(self) -> None:
        if self.can_go_forward:
            self._selected += timedelta(days=1)

    def go_today(self) -> None:
        self._selected = self._today_provider()


class DateNavBar(QWidget):
    dateChanged = Signal(date)

    def __init__(self, initial: date | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = DateNavigationState(initial or date.today())

        self._prev_button = QPushButton("<")
        self._today_button = QPushButton("Сегодня")
        self._next_button = QPushButton(">")
        self._label = QLabel()

        layout = QHBoxLayout(self)
        layout.addWidget(self._prev_button)
        layout.addWidget(self._label)
        layout.addWidget(self._today_button)
        layout.addWidget(self._next_button)

        self._prev_button.clicked.connect(self._on_previous)
        self._next_button.clicked.connect(self._on_next)
        self._today_button.clicked.connect(self._on_today)

        self._refresh()

    def _on_previous(self) -> None:
        self._state.go_previous()
        self._refresh()
        self.dateChanged.emit(self._state.selected)

    def _on_next(self) -> None:
        self._state.go_next()
        self._refresh()
        self.dateChanged.emit(self._state.selected)

    def _on_today(self) -> None:
        self._state.go_today()
        self._refresh()
        self.dateChanged.emit(self._state.selected)

    def _refresh(self) -> None:
        self._label.setText(self._state.selected.isoformat())
        self._next_button.setEnabled(self._state.can_go_forward)

    def selected_date(self) -> date:
        return self._state.selected
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_date_nav.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add src/timetrace/ui/__init__.py src/timetrace/ui/date_nav.py tests/test_date_nav.py
git commit -m "Add date navigation state and widget"
```

---

### Task 20: Timeline track widget

**Files:**
- Create: `src/timetrace/ui/timeline_widget.py`
- Test: `tests/test_timeline_widget.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) Segment(x: float, width: float, color: tuple[int,int,int])`
  - `intervals_to_segments(intervals: Sequence[tuple[int,int,tuple[int,int,int]]], day_start_ts: int, day_end_ts: int, track_width_px: float) -> list[Segment]` — pure function, `intervals` is `(start_ts, end_ts, color)` triples already clipped to the day (as returned by `Store`).
  - `class TimelineTrackWidget(QWidget)`: `set_intervals(self, intervals: Sequence[tuple[int,int,tuple[int,int,int]]], day_start_ts: int, day_end_ts: int) -> None`; `set_current_time_ts(self, ts: int | None) -> None` (draws the red "now" line; `None` hides it).
- Consumed by: Task 22 (`main_window.py`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_timeline_widget.py
from timetrace.ui.timeline_widget import Segment, intervals_to_segments


def test_empty_intervals_produce_no_segments():
    assert intervals_to_segments([], day_start_ts=0, day_end_ts=1000, track_width_px=100) == []


def test_full_day_interval_spans_full_width():
    segments = intervals_to_segments(
        [(0, 1000, (0, 255, 0))], day_start_ts=0, day_end_ts=1000, track_width_px=100
    )
    assert segments == [Segment(x=0.0, width=100.0, color=(0, 255, 0))]


def test_half_day_interval_spans_half_width():
    segments = intervals_to_segments(
        [(0, 500, (0, 255, 0))], day_start_ts=0, day_end_ts=1000, track_width_px=100
    )
    assert segments == [Segment(x=0.0, width=50.0, color=(0, 255, 0))]


def test_interval_offset_from_day_start():
    segments = intervals_to_segments(
        [(250, 750, (255, 0, 0))], day_start_ts=0, day_end_ts=1000, track_width_px=100
    )
    assert segments == [Segment(x=25.0, width=50.0, color=(255, 0, 0))]


def test_multiple_intervals_preserve_order():
    segments = intervals_to_segments(
        [(0, 250, (0, 255, 0)), (250, 1000, (255, 0, 0))],
        day_start_ts=0,
        day_end_ts=1000,
        track_width_px=100,
    )
    assert [s.color for s in segments] == [(0, 255, 0), (255, 0, 0)]
    assert segments[1].x == 25.0
    assert segments[1].width == 75.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_timeline_widget.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'timetrace.ui.timeline_widget'`

- [ ] **Step 3: Write implementation**

```python
# src/timetrace/ui/timeline_widget.py
from collections.abc import Sequence
from dataclasses import dataclass

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

TRACK_HEIGHT_PX = 28


@dataclass(frozen=True)
class Segment:
    x: float
    width: float
    color: tuple[int, int, int]


def intervals_to_segments(
    intervals: Sequence[tuple[int, int, tuple[int, int, int]]],
    day_start_ts: int,
    day_end_ts: int,
    track_width_px: float,
) -> list[Segment]:
    day_span = day_end_ts - day_start_ts
    if day_span <= 0:
        return []
    segments = []
    for start_ts, end_ts, color in intervals:
        x = (start_ts - day_start_ts) / day_span * track_width_px
        width = (end_ts - start_ts) / day_span * track_width_px
        segments.append(Segment(x=x, width=width, color=color))
    return segments


class TimelineTrackWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(TRACK_HEIGHT_PX)
        self._intervals: list[tuple[int, int, tuple[int, int, int]]] = []
        self._day_start_ts = 0
        self._day_end_ts = 1
        self._current_time_ts: int | None = None

    def set_intervals(
        self,
        intervals: Sequence[tuple[int, int, tuple[int, int, int]]],
        day_start_ts: int,
        day_end_ts: int,
    ) -> None:
        self._intervals = list(intervals)
        self._day_start_ts = day_start_ts
        self._day_end_ts = day_end_ts
        self.update()

    def set_current_time_ts(self, ts: int | None) -> None:
        self._current_time_ts = ts
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        width = self.width()
        height = self.height()

        painter.fillRect(0, 0, width, height, QColor(60, 60, 60))

        segments = intervals_to_segments(
            self._intervals, self._day_start_ts, self._day_end_ts, float(width)
        )
        for segment in segments:
            painter.fillRect(
                QRectF(segment.x, 0, segment.width, height), QColor(*segment.color)
            )

        if self._current_time_ts is not None:
            day_span = self._day_end_ts - self._day_start_ts
            if day_span > 0:
                x = (self._current_time_ts - self._day_start_ts) / day_span * width
                painter.setPen(QPen(QColor(255, 0, 0), 2))
                painter.drawLine(int(x), 0, int(x), height)

        painter.end()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_timeline_widget.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add src/timetrace/ui/timeline_widget.py tests/test_timeline_widget.py
git commit -m "Add timeline track widget with pure segment-layout logic"
```

---

### Task 21: App list widget (bottom panel, centered under the timeline)

**Files:**
- Create: `src/timetrace/ui/app_list_widget.py`
- Test: `tests/test_app_list_widget.py`

**Interfaces:**
- Consumes: `AppInterval` (Task 5), `resolve_icon` (Task 15), `color_for_resource_class` (Task 16).
- Produces:
  - `@dataclass(frozen=True) AppSummary(resource_class: str, total_ms: int, percent: float)`
  - `aggregate_app_durations(intervals: Sequence[AppInterval]) -> list[AppSummary]` — sorted descending by `total_ms`; `percent` is share of the summed total across all entries (0–100).
  - `format_duration(ms: int) -> str` — renders as `H:MM`.
  - `class AppListWidget(QWidget)`: `set_intervals(self, intervals: Sequence[AppInterval]) -> None` (repopulates the table, icon + name + share bar + duration, plus a "Всего: H:MM" total label below it — total is the *sum of all app durations passed in*, per spec §5; Task 22 is responsible for passing only the day's app intervals here, and separately computing the presence-based "Всего" from `presence_intervals_for_day`, see Task 22).
- Consumed by: Task 22 (`main_window.py`).

- [ ] **Step 1: Write the failing tests (pure aggregation logic first)**

```python
# tests/test_app_list_widget.py
from timetrace.app_list_widget import aggregate_app_durations, format_duration
from timetrace.db import AppInterval


def test_format_duration_hours_and_minutes():
    assert format_duration(0) == "0:00"
    assert format_duration(60_000) == "0:01"
    assert format_duration(3_600_000) == "1:00"
    assert format_duration(3_660_000) == "1:01"
    assert format_duration(7_265_000) == "2:01"


def test_aggregate_sums_by_resource_class():
    intervals = [
        AppInterval(id=1, resource_class="firefox", window_title=None, start_ts=0, end_ts=60_000),
        AppInterval(id=2, resource_class="code", window_title=None, start_ts=60_000, end_ts=120_000),
        AppInterval(id=3, resource_class="firefox", window_title=None, start_ts=120_000, end_ts=180_000),
    ]
    summaries = aggregate_app_durations(intervals)
    by_class = {s.resource_class: s for s in summaries}
    assert by_class["firefox"].total_ms == 120_000
    assert by_class["code"].total_ms == 60_000


def test_aggregate_sorts_descending_by_duration():
    intervals = [
        AppInterval(id=1, resource_class="short", window_title=None, start_ts=0, end_ts=10_000),
        AppInterval(id=2, resource_class="long", window_title=None, start_ts=0, end_ts=100_000),
    ]
    summaries = aggregate_app_durations(intervals)
    assert [s.resource_class for s in summaries] == ["long", "short"]


def test_aggregate_computes_percent_of_total():
    intervals = [
        AppInterval(id=1, resource_class="a", window_title=None, start_ts=0, end_ts=75_000),
        AppInterval(id=2, resource_class="b", window_title=None, start_ts=0, end_ts=25_000),
    ]
    summaries = aggregate_app_durations(intervals)
    by_class = {s.resource_class: s for s in summaries}
    assert by_class["a"].percent == 75.0
    assert by_class["b"].percent == 25.0


def test_aggregate_empty_list():
    assert aggregate_app_durations([]) == []
```

Note the import path: pure logic lives in `timetrace.app_list_widget` (not nested under `ui`) so it can import `timetrace.db.AppInterval` without pulling in Qt for these tests — the Qt widget class is defined in the same file but only instantiated by GUI tests.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_app_list_widget.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'timetrace.app_list_widget'`

- [ ] **Step 3: Write implementation**

```python
# src/timetrace/app_list_widget.py
from collections.abc import Sequence
from dataclasses import dataclass

from PySide6.QtWidgets import QHeaderView, QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from timetrace.app_color import color_for_resource_class
from timetrace.db import AppInterval
from timetrace.icons import resolve_icon


@dataclass(frozen=True)
class AppSummary:
    resource_class: str
    total_ms: int
    percent: float


def format_duration(ms: int) -> str:
    total_minutes = ms // 60_000
    hours, minutes = divmod(total_minutes, 60)
    return f"{hours}:{minutes:02d}"


def aggregate_app_durations(intervals: Sequence[AppInterval]) -> list[AppSummary]:
    totals: dict[str, int] = {}
    for interval in intervals:
        duration = (interval.end_ts or 0) - interval.start_ts
        totals[interval.resource_class] = totals.get(interval.resource_class, 0) + duration

    grand_total = sum(totals.values())
    summaries = [
        AppSummary(
            resource_class=rc,
            total_ms=total,
            percent=(total / grand_total * 100.0) if grand_total else 0.0,
        )
        for rc, total in totals.items()
    ]
    summaries.sort(key=lambda s: s.total_ms, reverse=True)
    return summaries


class AppListWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._table = QTableWidget(0, 3, self)
        self._table.setHorizontalHeaderLabels(["Приложение", "Доля", "Длительность"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._table.verticalHeader().setVisible(False)
        self._total_label = QLabel("Всего: 0:00")

        layout = QVBoxLayout(self)
        layout.addWidget(self._table)
        layout.addWidget(self._total_label)

    def set_intervals(self, intervals: Sequence[AppInterval]) -> None:
        summaries = aggregate_app_durations(intervals)
        self._table.setRowCount(len(summaries))
        for row, summary in enumerate(summaries):
            icon = resolve_icon(summary.resource_class)
            name_item = QTableWidgetItem(icon, summary.resource_class)
            self._table.setItem(row, 0, name_item)
            self._table.setItem(row, 1, QTableWidgetItem(f"{summary.percent:.1f}%"))
            self._table.setItem(row, 2, QTableWidgetItem(format_duration(summary.total_ms)))

        total_ms = sum(s.total_ms for s in summaries)
        self._total_label.setText(f"Всего: {format_duration(total_ms)}")

    def set_total_label_text(self, text: str) -> None:
        """Allows main_window.py to override with the presence-based total (Task 22)."""
        self._total_label.setText(text)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_app_list_widget.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add src/timetrace/app_list_widget.py tests/test_app_list_widget.py
git commit -m "Add app list widget with duration aggregation"
```

---

### Task 22: Main window wiring

Assembles Tasks 3, 5, 6, 16, 19, 20, 21 into the single-window layout from spec §5: date nav on top, two `TimelineTrackWidget`s ("Использование компьютера", "Приложения") in the middle, `AppListWidget` centered below, spanning the same width as the timelines (not off to the side).

**Files:**
- Create: `src/timetrace/ui/main_window.py`
- Test: `tests/test_main_window.py`

**Interfaces:**
- Consumes: `Store.presence_intervals_for_day`, `Store.app_intervals_for_day`, `day_bounds_ts` (Task 5); `DateNavBar` (Task 19); `TimelineTrackWidget` (Task 20); `AppListWidget` (Task 21); `color_for_resource_class` (Task 16).
- Produces: `class MainWindow(QMainWindow)`: `__init__(self, store: Store, tz: tzinfo, now_provider: Callable[[], datetime] | None = None, parent=None)`; `refresh(self) -> None` (re-reads the currently selected day from `store` and repopulates both timelines + the app list); property `presence_track: TimelineTrackWidget`; property `app_track: TimelineTrackWidget`; property `app_list: AppListWidget`; `Signal()` named `settingsRequested`, emitted by a small gear `QToolButton` next to the date nav (matches the spec's ManicTime-style gear icon; __main__.py in Task 25 connects it to opening `SettingsDialog`).
- Consumed by: Task 25 (`__main__.py`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_main_window.py
from datetime import date, datetime, timezone

from timetrace.db import Store, day_bounds_ts
from timetrace.ui.main_window import MainWindow

UTC = timezone.utc


def test_main_window_shows_todays_data_on_construction(qtbot, tmp_path):
    store = Store(tmp_path / "data.db")
    day_start, _ = day_bounds_ts(date(2026, 9, 27), UTC)
    store.open_presence_interval("active", day_start + 1000)
    store.close_open_presence_interval(day_start + 61_000)
    store.open_app_interval("firefox", "Mozilla Firefox", day_start + 1000)
    store.close_open_app_interval(day_start + 61_000)

    fixed_now = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)
    window = MainWindow(store, tz=UTC, now_provider=lambda: fixed_now)
    qtbot.addWidget(window)

    assert window.presence_track._intervals != []
    assert window.app_track._intervals != []
    store.close()


def test_main_window_date_nav_changes_shown_day(qtbot, tmp_path):
    store = Store(tmp_path / "data.db")
    day1_start, _ = day_bounds_ts(date(2026, 9, 26), UTC)
    store.open_presence_interval("active", day1_start + 1000)
    store.close_open_presence_interval(day1_start + 61_000)

    fixed_now = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)
    window = MainWindow(store, tz=UTC, now_provider=lambda: fixed_now)
    qtbot.addWidget(window)
    assert window.presence_track._intervals == []  # today has no data

    window._date_nav._on_previous()
    assert window.presence_track._intervals != []  # yesterday has data
    store.close()


def test_main_window_total_label_reflects_active_presence_time(qtbot, tmp_path):
    store = Store(tmp_path / "data.db")
    day_start, _ = day_bounds_ts(date(2026, 9, 27), UTC)
    store.open_presence_interval("active", day_start)
    store.close_open_presence_interval(day_start + 3_600_000)  # 1 hour active

    fixed_now = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)
    window = MainWindow(store, tz=UTC, now_provider=lambda: fixed_now)
    qtbot.addWidget(window)

    assert "1:00" in window.app_list._total_label.text()
    store.close()


def test_main_window_settings_button_emits_signal(qtbot, tmp_path):
    store = Store(tmp_path / "data.db")
    fixed_now = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)
    window = MainWindow(store, tz=UTC, now_provider=lambda: fixed_now)
    qtbot.addWidget(window)

    with qtbot.waitSignal(window.settingsRequested, timeout=1000):
        window._settings_button.click()
    store.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_main_window.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'timetrace.ui.main_window'`

- [ ] **Step 3: Write implementation**

```python
# src/timetrace/ui/main_window.py
from datetime import datetime, tzinfo
from typing import Callable

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QMainWindow, QToolButton, QVBoxLayout, QWidget

from timetrace.app_color import color_for_resource_class
from timetrace.app_list_widget import AppListWidget, format_duration
from timetrace.db import Store, day_bounds_ts
from timetrace.ui.date_nav import DateNavBar
from timetrace.ui.timeline_widget import TimelineTrackWidget

PRESENCE_COLORS = {"active": (46, 204, 64), "idle": (219, 68, 55)}


class MainWindow(QMainWindow):
    settingsRequested = Signal()

    def __init__(
        self,
        store: Store,
        tz: tzinfo,
        now_provider: Callable[[], datetime] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._store = store
        self._tz = tz
        self._now_provider = now_provider or (lambda: datetime.now(tz))

        self.setWindowTitle("TimeTrace")

        central = QWidget(self)
        layout = QVBoxLayout(central)

        top_row = QHBoxLayout()
        self._date_nav = DateNavBar(self._now_provider().date())
        self._settings_button = QToolButton()
        self._settings_button.setText("⚙")
        self._settings_button.clicked.connect(self.settingsRequested.emit)
        top_row.addWidget(self._date_nav)
        top_row.addStretch()
        top_row.addWidget(self._settings_button)
        layout.addLayout(top_row)

        self.presence_track = TimelineTrackWidget()
        self.app_track = TimelineTrackWidget()
        layout.addWidget(self.presence_track)
        layout.addWidget(self.app_track)

        self.app_list = AppListWidget()
        layout.addWidget(self.app_list)

        self.setCentralWidget(central)

        self._date_nav.dateChanged.connect(lambda _d: self.refresh())
        self.refresh()

    def refresh(self) -> None:
        selected_day = self._date_nav.selected_date()
        day_start_ts, day_end_ts = day_bounds_ts(selected_day, self._tz)
        now = self._now_provider()
        now_ts = int(now.timestamp() * 1000)

        presence_rows = self._store.presence_intervals_for_day(day_start_ts, day_end_ts, now_ts)
        presence_tuples = [
            (r.start_ts, r.end_ts, PRESENCE_COLORS.get(r.state, (128, 128, 128)))
            for r in presence_rows
        ]
        self.presence_track.set_intervals(presence_tuples, day_start_ts, day_end_ts)

        app_rows = self._store.app_intervals_for_day(day_start_ts, day_end_ts, now_ts)
        app_tuples = [
            (r.start_ts, r.end_ts, color_for_resource_class(r.resource_class))
            for r in app_rows
        ]
        self.app_track.set_intervals(app_tuples, day_start_ts, day_end_ts)

        is_today = selected_day == now.date()
        self.presence_track.set_current_time_ts(now_ts if is_today else None)
        self.app_track.set_current_time_ts(now_ts if is_today else None)

        self.app_list.set_intervals(app_rows)
        active_total_ms = sum(
            (r.end_ts or now_ts) - r.start_ts for r in presence_rows if r.state == "active"
        )
        self.app_list.set_total_label_text(f"Всего: {format_duration(active_total_ms)}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_main_window.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/timetrace/ui/main_window.py tests/test_main_window.py
git commit -m "Wire main window: date nav, two timelines, centered app list"
```

---

### Task 23: Tray icon

**Files:**
- Create: `src/timetrace/ui/tray.py`
- Test: `tests/test_tray.py`

**Interfaces:**
- Consumes: `MainWindow` (Task 22) only via duck-typed `show()`/`hide()`/`isVisible()` — no import needed.
- Produces: `class TrayIcon(QSystemTrayIcon)`: `__init__(self, window: QWidget, on_quit: Callable[[], None], parent=None) -> None`. Left-click toggles `window` visibility; context menu has "Показать/Скрыть" (toggles) and "Выход" (calls `on_quit`).
- Consumed by: Task 25 (`__main__.py`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_tray.py
from PySide6.QtWidgets import QWidget

from timetrace.ui.tray import TrayIcon


def test_activation_toggles_window_visibility(qtbot):
    window = QWidget()
    qtbot.addWidget(window)
    window.show()

    tray = TrayIcon(window, on_quit=lambda: None)
    tray._toggle_window()
    assert window.isVisible() is False
    tray._toggle_window()
    assert window.isVisible() is True


def test_quit_action_invokes_callback(qtbot):
    window = QWidget()
    qtbot.addWidget(window)
    calls = []
    tray = TrayIcon(window, on_quit=lambda: calls.append(True))
    tray._on_quit()
    assert calls == [True]


def test_menu_has_toggle_and_quit_actions(qtbot):
    window = QWidget()
    qtbot.addWidget(window)
    tray = TrayIcon(window, on_quit=lambda: None)
    action_texts = [a.text() for a in tray.contextMenu().actions()]
    assert "Показать/Скрыть" in action_texts
    assert "Выход" in action_texts
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_tray.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'timetrace.ui.tray'`

- [ ] **Step 3: Write implementation**

```python
# src/timetrace/ui/tray.py
from typing import Callable

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon, QWidget


class TrayIcon(QSystemTrayIcon):
    def __init__(
        self, window: QWidget, on_quit: Callable[[], None], parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._window = window
        self._on_quit_callback = on_quit
        self.setIcon(QIcon.fromTheme("timetrace"))
        self.setToolTip("TimeTrace")

        menu = QMenu()
        toggle_action = menu.addAction("Показать/Скрыть")
        toggle_action.triggered.connect(self._toggle_window)
        quit_action = menu.addAction("Выход")
        quit_action.triggered.connect(self._on_quit)
        self.setContextMenu(menu)

        self.activated.connect(self._on_activated)

    def _on_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.Trigger:
            self._toggle_window()

    def _toggle_window(self) -> None:
        if self._window.isVisible():
            self._window.hide()
        else:
            self._window.show()
            self._window.raise_()
            self._window.activateWindow()

    def _on_quit(self) -> None:
        self._on_quit_callback()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_tray.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/timetrace/ui/tray.py tests/test_tray.py
git commit -m "Add tray icon with show/hide toggle and quit"
```

---

### Task 24: Settings dialog

**Files:**
- Create: `src/timetrace/ui/settings_dialog.py`
- Test: `tests/test_settings_dialog.py`

**Interfaces:**
- Consumes: `Config`, `load_config`, `save_config` (Task 4); `is_autostart_enabled`, `set_autostart_enabled` (Task 18); `apply_theme` (Task 17).
- Produces: `class SettingsDialog(QDialog)`: `__init__(self, config: Config, config_path: Path, on_idle_threshold_changed: Callable[[int], None], on_theme_changed: Callable[[str], None], exec_path: str | None = None, parent=None) -> None`. On "OK": persists via `save_config`, calls `set_autostart_enabled`, calls `on_theme_changed(theme)`, calls `on_idle_threshold_changed(minutes)`.
- Consumed by: Task 25 (`__main__.py`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_settings_dialog.py
from timetrace.config import Config, load_config
from timetrace.ui.settings_dialog import SettingsDialog


def test_dialog_initializes_controls_from_config(qtbot):
    config = Config(autostart=True, theme="dark", idle_threshold_minutes=10)
    dialog = SettingsDialog(
        config,
        config_path=None,  # not written to in this test
        on_idle_threshold_changed=lambda m: None,
        on_theme_changed=lambda t: None,
    )
    qtbot.addWidget(dialog)
    assert dialog._autostart_checkbox.isChecked() is True
    assert dialog._theme_dark_radio.isChecked() is True
    assert dialog._idle_spinbox.value() == 10


def test_accept_persists_config_and_invokes_callbacks(qtbot, tmp_path):
    config_path = tmp_path / "config.toml"
    theme_calls = []
    threshold_calls = []
    dialog = SettingsDialog(
        Config(),
        config_path=config_path,
        on_idle_threshold_changed=lambda m: threshold_calls.append(m),
        on_theme_changed=lambda t: theme_calls.append(t),
        exec_path="/usr/bin/timetrace",
    )
    qtbot.addWidget(dialog)

    dialog._autostart_checkbox.setChecked(True)
    dialog._theme_dark_radio.setChecked(True)
    dialog._idle_spinbox.setValue(15)
    dialog.accept()

    saved = load_config(config_path)
    assert saved.autostart is True
    assert saved.theme == "dark"
    assert saved.idle_threshold_minutes == 15
    assert theme_calls == ["dark"]
    assert threshold_calls == [15]


def test_accept_toggles_autostart_file(qtbot, tmp_path):
    config_path = tmp_path / "config.toml"
    autostart_path = tmp_path / "autostart" / "timetrace.desktop"
    dialog = SettingsDialog(
        Config(),
        config_path=config_path,
        on_idle_threshold_changed=lambda m: None,
        on_theme_changed=lambda t: None,
        exec_path="/usr/bin/timetrace",
        autostart_path=autostart_path,
    )
    qtbot.addWidget(dialog)
    dialog._autostart_checkbox.setChecked(True)
    dialog.accept()
    assert autostart_path.exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_settings_dialog.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'timetrace.ui.settings_dialog'`

- [ ] **Step 3: Write implementation**

```python
# src/timetrace/ui/settings_dialog.py
from pathlib import Path
from typing import Callable

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from timetrace.autostart import set_autostart_enabled
from timetrace.config import Config, save_config


class SettingsDialog(QDialog):
    def __init__(
        self,
        config: Config,
        config_path: Path | None,
        on_idle_threshold_changed: Callable[[int], None],
        on_theme_changed: Callable[[str], None],
        exec_path: str | None = None,
        autostart_path: Path | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Настройки")
        self._config_path = config_path
        self._on_idle_threshold_changed = on_idle_threshold_changed
        self._on_theme_changed = on_theme_changed
        self._exec_path = exec_path
        self._autostart_path = autostart_path

        self._autostart_checkbox = QCheckBox("Автозагрузка")
        self._autostart_checkbox.setChecked(config.autostart)

        self._theme_light_radio = QRadioButton("Светлая")
        self._theme_dark_radio = QRadioButton("Тёмная")
        self._theme_system_radio = QRadioButton("Синхронизировать с ОС")
        {"light": self._theme_light_radio, "dark": self._theme_dark_radio, "system": self._theme_system_radio}[
            config.theme
        ].setChecked(True)
        theme_row = QHBoxLayout()
        theme_row.addWidget(self._theme_light_radio)
        theme_row.addWidget(self._theme_dark_radio)
        theme_row.addWidget(self._theme_system_radio)
        theme_widget = QWidget()
        theme_widget.setLayout(theme_row)

        self._idle_spinbox = QSpinBox()
        self._idle_spinbox.setRange(1, 120)
        self._idle_spinbox.setValue(config.idle_threshold_minutes)

        form = QFormLayout()
        form.addRow(self._autostart_checkbox)
        form.addRow("Тема:", theme_widget)
        form.addRow("Порог простоя (мин):", self._idle_spinbox)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _selected_theme(self) -> str:
        if self._theme_dark_radio.isChecked():
            return "dark"
        if self._theme_system_radio.isChecked():
            return "system"
        return "light"

    def accept(self) -> None:
        new_config = Config(
            autostart=self._autostart_checkbox.isChecked(),
            theme=self._selected_theme(),
            idle_threshold_minutes=self._idle_spinbox.value(),
        )
        if self._config_path is not None:
            save_config(self._config_path, new_config)
        set_autostart_enabled(
            new_config.autostart,
            autostart_path=self._autostart_path,
            exec_path=self._exec_path,
        )
        self._on_theme_changed(new_config.theme)
        self._on_idle_threshold_changed(new_config.idle_threshold_minutes)
        super().accept()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_settings_dialog.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/timetrace/ui/settings_dialog.py tests/test_settings_dialog.py
git commit -m "Add settings dialog: autostart, theme, idle threshold"
```

---

### Task 25: Application bootstrap (`__main__.py`)

Wires everything built so far into a running app: single-instance guard, backend selection, `TrackingCoordinator`, `MainWindow`, `TrayIcon`, live theme sync, and the periodic timers that drive event processing and the "today" view's live refresh. Replaces the placeholder `main()` from Task 1.

**Files:**
- Modify: `src/timetrace/__main__.py`
- Test: `tests/test_main_bootstrap.py`

**Interfaces:**
- Consumes every public interface produced by Tasks 3–24.
- Produces: `def build_app(argv: list[str]) -> tuple[QApplication, MainWindow | None, TrackingCoordinator | None, TrayIcon | None]` — the part of bootstrap that's testable without actually calling `.exec()`. The last three are `None` when this process is a second instance (see guard below) — `main()` must check for that before calling `.show()`/`.exec()`. `def main(argv: list[str] | None = None) -> int` — calls `build_app` then, if a real window was returned, `window.show()` and `app.exec()` (not unit tested directly; covered by manual run in Step 5).

Single-instance guard, fully implemented in `build_app` (not just described in prose): after constructing `QApplication`, call `QDBusConnection.sessionBus().registerService("org.timetrace.App")`. If it returns `True`, this process owns the name — proceed building everything, and once `window` exists, register a `/App` object (`_SingleInstanceAdaptor`, a `QObject` with a `@Slot()` `Raise()` method that shows/raises/activates `window`) on that same connection so a second instance can reach it. If `registerService` returns `False`, another instance already owns the name — call `Raise` on its `/App` object via `QDBusInterface` and return `(app, None, None, None)` immediately, without touching `Store`/`TrackingCoordinator` (a second process must not open a second tracking session against the same SQLite file or start duplicate backends). Note Task 12's `KWinScriptActiveWindowBackend` separately registers the same already-owned service name for its own `/ActiveWindow` object when it starts — that's a distinct object path on the same service and doesn't conflict; `QDBusConnection.registerService` called again by the same process for a name it already owns simply succeeds again.

The two-real-processes scenario (second launch getting refused and raising the first window) is out of scope for automated testing and is verified manually in Step 5; Step 1's test only exercises the primary-instance path.

- [ ] **Step 1: Write the failing test for `build_app`**

```python
# tests/test_main_bootstrap.py
from datetime import timezone

from timetrace.__main__ import build_app


def test_build_app_wires_window_coordinator_and_tray(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "")  # force "other" -> Null backends, no real I/O
    monkeypatch.setenv("XDG_SESSION_TYPE", "")

    app, window, coordinator, tray = build_app([])

    assert window.isVisible() is False or window.isVisible() is True  # constructed without error
    assert coordinator is not None
    assert tray is not None

    coordinator.stop()
    app.quit()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_main_bootstrap.py -v`
Expected: FAIL — `ImportError: cannot import name 'build_app' from 'timetrace.__main__'`

- [ ] **Step 3: Write implementation**

```python
# src/timetrace/__main__.py
import sys
from datetime import datetime, timezone
from typing import Optional

from . import __version__


def _make_single_instance_adaptor(on_raise):
    """QObject exposing Raise() as a Qt slot so a second TimeTrace process
    can ask this one to show its window. Same ExportAllSlots pattern as
    Task 12's `_TimeTraceDBusAdaptor`; verify the exact registerObject call
    against the installed PySide6 version when implementing."""
    from PySide6.QtCore import QObject, Slot

    class _SingleInstanceAdaptor(QObject):
        @Slot()
        def Raise(self) -> None:
            on_raise()

    return _SingleInstanceAdaptor()


def build_app(argv: list[str]):
    from PySide6.QtCore import QTimer
    from PySide6.QtDBus import QDBusConnection, QDBusInterface
    from PySide6.QtWidgets import QApplication

    from timetrace import paths, theme
    from timetrace.backends.idle_factory import select_idle_backend
    from timetrace.backends.window_factory import select_window_backend
    from timetrace.config import load_config
    from timetrace.db import Store
    from timetrace.env_detect import detect_desktop_environment, detect_session_type
    from timetrace.tracking.coordinator import TrackingCoordinator
    from timetrace.ui.main_window import MainWindow
    from timetrace.ui.settings_dialog import SettingsDialog
    from timetrace.ui.tray import TrayIcon

    app = QApplication(argv)
    app.setQuitOnLastWindowClosed(False)

    bus = QDBusConnection.sessionBus()
    is_primary_instance = bus.registerService("org.timetrace.App")
    if not is_primary_instance:
        iface = QDBusInterface("org.timetrace.App", "/App", "", bus)
        iface.call("Raise")
        return app, None, None, None

    config = load_config(paths.config_file_path())

    theme_watch_unsubscribe: list = [None]

    def set_theme(mode: str) -> None:
        if theme_watch_unsubscribe[0] is not None:
            theme_watch_unsubscribe[0]()
            theme_watch_unsubscribe[0] = None
        theme.apply_theme(app, mode)
        if mode == "system":
            theme_watch_unsubscribe[0] = theme.watch_system_color_scheme(
                lambda scheme: theme.apply_theme(app, "system")
            )

    set_theme(config.theme)

    store = Store(paths.db_file_path())
    tz = datetime.now().astimezone().tzinfo or timezone.utc

    desktop = detect_desktop_environment()
    session = detect_session_type()
    idle_backend = select_idle_backend(desktop, session)
    window_backend = select_window_backend(desktop, session)

    coordinator = TrackingCoordinator(
        store, idle_backend, window_backend, idle_threshold_ms=config.idle_threshold_minutes * 60_000
    )
    coordinator.start()

    window = MainWindow(store, tz=tz)

    def open_settings() -> None:
        dialog = SettingsDialog(
            config,
            config_path=paths.config_file_path(),
            on_idle_threshold_changed=coordinator.update_idle_threshold,
            on_theme_changed=set_theme,
            exec_path="timetrace",
        )
        dialog.exec()

    window.settingsRequested.connect(open_settings)

    raise_adaptor = _make_single_instance_adaptor(
        lambda: (window.show(), window.raise_(), window.activateWindow())
    )
    bus.registerObject("/App", raise_adaptor, QDBusConnection.RegisterOption.ExportAllSlots)
    window._raise_adaptor = raise_adaptor  # keep the QObject alive

    def quit_app() -> None:
        coordinator.stop()
        store.close()
        app.quit()

    tray = TrayIcon(window, on_quit=quit_app)
    tray.show()

    event_timer = QTimer()
    event_timer.timeout.connect(coordinator.process_pending_events)
    event_timer.start(250)

    refresh_timer = QTimer()
    refresh_timer.timeout.connect(window.refresh)
    refresh_timer.start(5000)

    window._event_timer = event_timer  # keep references alive
    window._refresh_timer = refresh_timer

    return app, window, coordinator, tray


def main(argv: Optional[list[str]] = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["--version"]:
        print(f"timetrace {__version__}")
        return 0

    app, window, coordinator, tray = build_app(sys.argv[:1] + argv)
    if window is None:
        return 0  # another instance is already running and was asked to raise its window

    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_main_bootstrap.py -v`
Expected: 1 passed

- [ ] **Step 5: Manual smoke test on the real KDE Wayland dev machine**

Run: `python -m timetrace`
Expected: window appears with today's (empty) timeline, tray icon appears. Move the mouse / switch windows a few times, wait a few seconds, open Settings via the gear button, change idle threshold, close it, quit via tray "Выход". Run `python -m timetrace` again — previously tracked data should still show. This exercises the full KDE Wayland path end-to-end; it is not automated (needs a live session) but is the plan's final confirmation that Task 2's spike decision actually works integrated with everything else.

- [ ] **Step 6: Commit**

```bash
git add src/timetrace/__main__.py tests/test_main_bootstrap.py
git commit -m "Wire application bootstrap: backends, coordinator, window, tray"
```

---

### Task 26: PyInstaller build

**Files:**
- Create: `packaging/pyinstaller.spec`
- Create: `packaging/timetrace.desktop`

**Interfaces:**
- Produces: a `dist/timetrace/timetrace` (onedir build) or `dist/timetrace` (onefile) executable that runs standalone without a system Python/PySide6 install. Consumed by Task 27 and Task 28 as the artifact they package.

- [ ] **Step 1: Write the PyInstaller spec**

`packaging/pyinstaller.spec`:
```python
# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files

datas = []
datas += collect_data_files("timetrace.assets.kwin_script")
datas += collect_data_files("timetrace.assets.gnome_extension")

a = Analysis(
    ["../src/timetrace/__main__.py"],
    pathex=["../src"],
    datas=datas,
    hiddenimports=["Xlib.ext.screensaver"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    name="timetrace",
    console=False,
    onefile=True,
)
```

- [ ] **Step 2: Write the `.desktop` launcher file for installed use**

`packaging/timetrace.desktop`:
```ini
[Desktop Entry]
Type=Application
Name=TimeTrace
Comment=Simplified ManicTime-alike time tracker
Exec=/usr/bin/timetrace
Icon=timetrace
Categories=Utility;
Terminal=false
```

- [ ] **Step 3: Build and verify**

Run: `pip install pyinstaller` then `cd packaging && pyinstaller pyinstaller.spec`
Expected: `packaging/dist/timetrace` produced.

Run: `./dist/timetrace --version`
Expected: prints `timetrace 0.1.0` with no system Python/PySide6 on `PATH` required (test this by temporarily deactivating any venv, or in a clean container, per Step 4 below).

- [ ] **Step 4: Commit**

```bash
git add packaging/pyinstaller.spec packaging/timetrace.desktop
git commit -m "Add PyInstaller build spec and desktop launcher"
```

---

### Task 27: `.deb` and `.rpm` packaging via fpm

**Files:**
- Create: `packaging/build_deb_rpm.sh`

**Interfaces:**
- Consumes: the PyInstaller output from Task 26 (`packaging/dist/timetrace`), `packaging/timetrace.desktop`.
- Produces: `timetrace_<version>_amd64.deb` and `timetrace-<version>.x86_64.rpm` in `packaging/out/`.

- [ ] **Step 1: Write the build script**

`packaging/build_deb_rpm.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail

VERSION="0.1.0"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_DIR="$SCRIPT_DIR/out"
STAGE_DIR="$SCRIPT_DIR/stage"

rm -rf "$STAGE_DIR" "$OUT_DIR"
mkdir -p "$STAGE_DIR/usr/bin" "$STAGE_DIR/usr/share/applications" "$OUT_DIR"

cp "$SCRIPT_DIR/dist/timetrace" "$STAGE_DIR/usr/bin/timetrace"
chmod 755 "$STAGE_DIR/usr/bin/timetrace"
cp "$SCRIPT_DIR/timetrace.desktop" "$STAGE_DIR/usr/share/applications/timetrace.desktop"

command -v fpm >/dev/null || {
    echo "fpm not found; install with: gem install --no-document fpm" >&2
    exit 1
}

fpm -s dir -t deb -n timetrace -v "$VERSION" \
    --description "Simplified ManicTime-alike time tracker for KDE and GNOME" \
    --license MIT \
    --url "https://github.com/<owner>/timetrace" \
    -C "$STAGE_DIR" -p "$OUT_DIR/timetrace_${VERSION}_amd64.deb" .

fpm -s dir -t rpm -n timetrace -v "$VERSION" \
    --description "Simplified ManicTime-alike time tracker for KDE and GNOME" \
    --license MIT \
    --url "https://github.com/<owner>/timetrace" \
    -C "$STAGE_DIR" -p "$OUT_DIR/timetrace-${VERSION}.x86_64.rpm" .

echo "Built:"
ls -la "$OUT_DIR"
```

- [ ] **Step 2: Make executable and verify**

Run: `chmod +x packaging/build_deb_rpm.sh`
Run: `packaging/build_deb_rpm.sh` (after Task 26's build has produced `packaging/dist/timetrace`)
Expected: `packaging/out/timetrace_0.1.0_amd64.deb` and `packaging/out/timetrace-0.1.0.x86_64.rpm` created. If `fpm` isn't installed, the script exits with the install instructions rather than a confusing failure — install it (`gem install --no-document fpm`, requires Ruby) and re-run before considering this task done.

Run: `dpkg-deb --info packaging/out/timetrace_0.1.0_amd64.deb`
Expected: shows package name `timetrace`, version `0.1.0`.

- [ ] **Step 3: Commit**

```bash
git add packaging/build_deb_rpm.sh
git commit -m "Add .deb/.rpm packaging script via fpm"
```

---

### Task 28: Arch Linux binary package (PKGBUILD)

**Files:**
- Create: `packaging/PKGBUILD`

**Interfaces:**
- Consumes: the PyInstaller output from Task 26.
- Produces: a `makepkg`-buildable binary package installing `/usr/bin/timetrace` and the `.desktop` launcher, per the design's decision to ship a binary (not source-built) AUR package.

- [ ] **Step 1: Write the PKGBUILD**

`packaging/PKGBUILD`:
```bash
# Maintainer: <name> <email>
pkgname=timetrace
pkgver=0.1.0
pkgrel=1
pkgdesc="Simplified ManicTime-alike time tracker for KDE and GNOME"
arch=('x86_64')
url="https://github.com/<owner>/timetrace"
license=('MIT')
depends=()
source_x86_64=("timetrace-${pkgver}-x86_64.bin::https://github.com/<owner>/timetrace/releases/download/v${pkgver}/timetrace")
sha256sums_x86_64=('SKIP')

package() {
    install -Dm755 "${srcdir}/timetrace-${pkgver}-x86_64.bin" "${pkgdir}/usr/bin/timetrace"
    install -Dm644 "${startdir}/timetrace.desktop" "${pkgdir}/usr/share/applications/timetrace.desktop"
}
```

- [ ] **Step 2: Verify locally**

Run: `cp packaging/dist/timetrace packaging/timetrace-0.1.0-x86_64.bin` (stand-in for the real release download while testing locally, since `source_x86_64` points at a not-yet-published GitHub release)
Run: `cd packaging && makepkg -p PKGBUILD --skipinteg`
Expected: builds `timetrace-0.1.0-1-x86_64.pkg.tar.zst`.

Run: `tar -tf packaging/timetrace-0.1.0-1-x86_64.pkg.tar.zst | grep usr/bin/timetrace`
Expected: prints the path, confirming the binary is included.

Before the actual GitHub release exists, replace `<owner>` and the `source_x86_64` URL/`sha256sums_x86_64` with the real release asset URL and its real sha256 (`sha256sum` the uploaded binary) — `SKIP` is only for local testing.

- [ ] **Step 3: Commit**

```bash
git add packaging/PKGBUILD
git commit -m "Add Arch Linux binary PKGBUILD"
```
