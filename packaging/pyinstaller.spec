# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files

datas = []
datas += collect_data_files("timetrace.assets.kwin_script")
datas += collect_data_files("timetrace.assets.gnome_extension")

a = Analysis(
    ["entry_point.py"],
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
