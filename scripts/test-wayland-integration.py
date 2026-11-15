"""Real native Wayland clients on an isolated headless Sway display."""
import os
import subprocess
import threading
import time

from timetrace.backends.window_wayland import WaylandActiveWindowBackend, WaylandToplevelClient
from timetrace.backends.idle_kde_wayland import WaylandExtIdleNotifyBackend


def wait_for(predicate, timeout=8):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return
        time.sleep(0.05)
    raise AssertionError("compositor event did not arrive")


windows, fullscreen = [], []
idled = threading.Event()
# Match application construction order: idle owns the first Wayland registry.
idle = WaylandExtIdleNotifyBackend()
window = WaylandActiveWindowBackend()
clients = []
try:
    window.start_fullscreen_monitor(lambda full, ts: fullscreen.append(full))
    window.start(lambda app, title, ts: windows.append((app, title)))
    idle.start(300, lambda ts: idled.set(), lambda ts: None)
    assert idled.wait(5), "no ext-idle-notify event"
    clients.append(subprocess.Popen(["foot", "--app-id=org.timetrace.First", "--title=Native first", "sleep", "60"]))
    wait_for(lambda: any(app == "org.timetrace.First" for app, title in windows))
    if os.environ.get("SWAYSOCK"):
        subprocess.run(["swaymsg", "fullscreen", "enable"], check=True, capture_output=True)
        wait_for(lambda: fullscreen[-1:] == [True])
        subprocess.run(["swaymsg", "fullscreen", "disable"], check=True, capture_output=True)
        wait_for(lambda: fullscreen[-1:] == [False])
    clients.append(subprocess.Popen(["foot", "--app-id=org.timetrace.Second", "--title=Native second", "sleep", "60"]))
    wait_for(lambda: any(app == "org.timetrace.Second" for app, title in windows))
    control = WaylandToplevelClient()
    try:
        handle = next(h for h, props in control.tracker.windows.items() if props["app_id"] == "org.timetrace.Second")
        # Request after map: labwc 0.7.1 omits initial fullscreen state from
        # foreign-toplevels if the application requested it before mapping.
        handle.set_fullscreen(None)
        control.display.flush()
        wait_for(lambda: fullscreen[-1:] == [True])
    finally:
        control.close()
    clients[-1].terminate()
    clients[-1].wait(timeout=3)
    wait_for(lambda: windows[-1][0] == "org.timetrace.First")
    wait_for(lambda: fullscreen[-1:] == [False])
    clients[0].terminate()
    clients[0].wait(timeout=3)
    wait_for(lambda: windows[-1][0] == "")
    print("PASS: native Wayland focus, fullscreen, close and ext-idle-notify")
finally:
    idle.stop()
    window.stop()
    for client in clients:
        if client.poll() is None:
            client.terminate()
            client.wait(timeout=3)
