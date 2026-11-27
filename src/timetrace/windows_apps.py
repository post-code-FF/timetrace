import ctypes
from pathlib import Path


def executable_display_name(path: str) -> str:
    name = Path(path).name
    if not name.lower().endswith(".exe"):
        return name
    version = ctypes.windll.version
    size = version.GetFileVersionInfoSizeW(path, None)
    if size:
        data = ctypes.create_string_buffer(size)
        if version.GetFileVersionInfoW(path, 0, size, data):
            class LANGANDCODEPAGE(ctypes.Structure):
                _fields_ = [("wLanguage", ctypes.c_uint16), ("wCodePage", ctypes.c_uint16)]
            translations = ctypes.POINTER(LANGANDCODEPAGE)()
            length = ctypes.c_uint()
            if version.VerQueryValueW(data, "\\VarFileInfo\\Translation", ctypes.byref(translations), ctypes.byref(length)) and length.value >= ctypes.sizeof(LANGANDCODEPAGE):
                lang = translations[0]
                key = f"\\StringFileInfo\\{lang.wLanguage:04x}{lang.wCodePage:04x}\\FileDescription"
                value = ctypes.c_wchar_p()
                value_length = ctypes.c_uint()
                if version.VerQueryValueW(data, key, ctypes.byref(value), ctypes.byref(value_length)) and value.value:
                    return value.value
    return name[:-4]