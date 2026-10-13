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

# fontconfig и freetype должны быть системными. Упакованные из Ubuntu не
# понимают конфиги новых дистрибутивов (48-guessfamily.conf, xsi:nil и т.п.),
# из-за чего на openSUSE/Fedora сыплются предупреждения "Fontconfig error/warning".
_SYSTEM_LIBS = ("libfontconfig.so", "libfreetype.so")
a.binaries = [b for b in a.binaries if not b[0].startswith(_SYSTEM_LIBS)]

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
