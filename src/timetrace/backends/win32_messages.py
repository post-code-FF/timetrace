import ctypes
from ctypes import wintypes

_user32 = ctypes.windll.user32
_kernel32 = ctypes.windll.kernel32

LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t)
HWND_MESSAGE = wintypes.HWND(-3)


class WNDCLASSW(ctypes.Structure):
    _fields_ = [("style", ctypes.c_uint), ("lpfnWndProc", WNDPROC),
                ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
                ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HANDLE),
                ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HANDLE),
                ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR)]


_user32.DefWindowProcW.restype = LRESULT
_user32.DefWindowProcW.argtypes = [wintypes.HWND, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t]
_user32.CreateWindowExW.restype = wintypes.HWND
_user32.FindWindowExW.restype = wintypes.HWND
_user32.FindWindowExW.argtypes = [wintypes.HWND, wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR]
_user32.PostMessageW.argtypes = [wintypes.HWND, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t]

_handlers: dict[int, object] = {}


def _wndproc(hwnd, msg, wparam, lparam):
    handler = _handlers.get(hwnd)
    if handler is not None:
        try:
            handler(msg, wparam, lparam)
        except Exception:
            pass
    return _user32.DefWindowProcW(hwnd, msg, wparam, lparam)


_proc = WNDPROC(_wndproc)
_registered = False


class MessageWindow:
    """Message-only window whose WNDPROC is dispatched by Qt's Win32 event loop."""

    def __init__(self, class_name: str, handler) -> None:
        global _registered
        hinstance = _kernel32.GetModuleHandleW(None)
        if not _registered:
            wc = WNDCLASSW()
            wc.lpfnWndProc = _proc
            wc.hInstance = hinstance
            wc.lpszClassName = "TimeTraceMsg"
            if not _user32.RegisterClassW(ctypes.byref(wc)):
                raise OSError("RegisterClassW failed")
            _registered = True
        self._hwnd = _user32.CreateWindowExW(0, "TimeTraceMsg", class_name, 0, 0, 0, 0, 0,
                                             HWND_MESSAGE, None, hinstance, None)
        if not self._hwnd:
            raise OSError("CreateWindowExW failed")
        _handlers[self._hwnd] = handler

    @property
    def hwnd(self):
        return self._hwnd

    def close(self) -> None:
        if self._hwnd:
            _handlers.pop(self._hwnd, None)
            _user32.DestroyWindow(self._hwnd)
            self._hwnd = None


def find_message_window(title: str):
    return _user32.FindWindowExW(HWND_MESSAGE, None, "TimeTraceMsg", title)


def post_message(hwnd, msg: int) -> None:
    _user32.PostMessageW(hwnd, msg, 0, 0)