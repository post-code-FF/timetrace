import struct

from timetrace.app_names import AppNameResolver


def _resolver(tmp_path):
    steam = tmp_path / "Steam"
    (steam / "steamapps").mkdir(parents=True)
    (steam / "steamapps" / "appmanifest_2483190.acf").write_text(
        '"AppState"\n{\n\t"appid"\t\t"2483190"\n\t"name"\t\t"Forza Horizon 6"\n}\n'
    )
    apps = tmp_path / "apps"
    apps.mkdir()
    (apps / "Until_Dawn.desktop").write_text(
        "[Desktop Entry]\nName=Until Dawn\nExec=steam steam://rungameid/14040031577061195776\n"
        "Icon=/x/icon.png\n"
    )
    (apps / "Game.desktop").write_text(
        "[Desktop Entry]\nName=Cool Game\nExec=portproton \"/games/coolgame.exe\"\nIcon=cool\n"
    )
    return AppNameResolver(steam_roots=[steam], desktop_dirs=[apps])


def test_steam_app_name_from_manifest(tmp_path):
    assert _resolver(tmp_path).display_name("steam_app_2483190") == "Forza Horizon 6"


def test_non_steam_shortcut_resolved_via_desktop_entry(tmp_path):
    resolver = _resolver(tmp_path)
    assert resolver.display_name("steam_app_3268949589", "Дожить до рассвета") == "Until Dawn"
    assert resolver.icon_name("steam_app_3268949589") == "/x/icon.png"


def test_non_steam_shortcut_resolved_via_shortcuts_vdf(tmp_path):
    steam = tmp_path / "Steam"
    cfg = steam / "userdata" / "1" / "config"
    cfg.mkdir(parents=True)
    (cfg / "shortcuts.vdf").write_bytes(
        b"\x00shortcuts\x00\x000\x00\x02appid\x00" + struct.pack("<I", 3717756991)
        + b"\x01AppName\x00Little Hope\x00\x08\x08"
    )
    resolver = AppNameResolver(steam_roots=[steam], desktop_dirs=[])
    assert resolver.display_name("steam_app_3717756991") == "Little Hope"


def test_unknown_steam_app_falls_back_to_title_then_id(tmp_path):
    resolver = _resolver(tmp_path)
    assert resolver.display_name("steam_app_1", "Some Title") == "Some Title"
    assert resolver.display_name("steam_app_2") == "Steam App 2"


def test_wine_exe_uses_desktop_entry_then_strips_extension(tmp_path):
    resolver = _resolver(tmp_path)
    assert resolver.display_name("CoolGame.exe") == "Cool Game"
    assert resolver.display_name("other.exe") == "other"


def test_regular_class_unchanged(tmp_path):
    assert _resolver(tmp_path).display_name("firefox") == "firefox"
