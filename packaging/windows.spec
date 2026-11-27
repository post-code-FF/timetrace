# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files

datas = collect_data_files("timetrace.assets", includes=["icon.png", "application.svg"])

a = Analysis(
    ["windows_entry_point.py"],
    pathex=["../src"],
    datas=datas,
    hiddenimports=["timetrace.backends.window_windows", "timetrace.backends.idle_windows", "timetrace.backends.sleep_windows", "timetrace.single_instance_windows", "timetrace.windows_apps"],
    excludes=["PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick", "PySide6.QtPdf", "PySide6.QtDBus", "Xlib", "pywayland", "pytest"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    name="TimeTrace",
    console=False,
    onefile=True,
    icon="../src/timetrace/assets/icon.png",
)