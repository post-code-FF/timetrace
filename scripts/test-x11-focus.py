"""Real X11 fallback test on an isolated Xvfb, with no EWMH window manager."""
import os
import subprocess
from Xlib import X, Xatom, display

reader, writer = os.pipe()
server = subprocess.Popen(["Xvfb", "-displayfd", str(writer), "-screen", "0", "800x600x24"], pass_fds=[writer])
os.close(writer)
with os.fdopen(reader) as pipe:
    number = pipe.readline().strip()
assert number, "Xvfb failed"
os.environ["DISPLAY"] = f":{number}"
connection = None
backend = None
try:
    from timetrace.backends.window_x11 import RealX11Client
    connection = display.Display()
    root = connection.screen().root
    window = root.create_window(0, 0, 400, 300, 0, X.CopyFromParent)
    child = window.create_window(0, 0, 200, 100, 0, X.CopyFromParent)
    window.set_wm_class("test", "LegacyTerminal")
    window.set_wm_name("ICCCM child focus")
    state = connection.intern_atom("WM_STATE")
    window.change_property(state, state, 32, [1, 0])
    window.map()
    child.map()
    child.set_input_focus(X.RevertToParent, X.CurrentTime)
    connection.sync()
    backend = RealX11Client()
    assert backend.get_active_window_info() == ("LegacyTerminal", "ICCCM child focus")
    active = connection.intern_atom("_NET_ACTIVE_WINDOW")
    root.change_property(active, Xatom.WINDOW, 32, [0])
    connection.sync()
    assert backend.get_active_window_info() is None, "explicit EWMH no-focus must win"
    root.delete_property(active)
    root.set_input_focus(X.RevertToParent, X.CurrentTime)
    connection.sync()
    assert backend.get_active_window_info() is None, "root is not an application"
    print('PASS: real X11 child focus -> ICCCM client, EWMH no-focus and root rejection')
finally:
    if backend:
        backend.close()
    if connection:
        connection.close()
    server.terminate()
    server.wait(timeout=3)
