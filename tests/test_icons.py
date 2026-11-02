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


def test_find_desktop_entry_matches_gnome_style_id_with_desktop_suffix(tmp_path):
    # Shell.WindowTracker.get_window_app(win).get_id() on GNOME returns the
    # desktop file's id including the ".desktop" suffix, unlike X11/KDE's
    # bare WM_CLASS.
    apps_dir = tmp_path / "applications"
    apps_dir.mkdir()
    entry = apps_dir / "org.mozilla.firefox.desktop"
    write_desktop_file(entry, name="Firefox", exec_="firefox %u", icon="firefox")

    found = find_desktop_entry("org.mozilla.firefox.desktop", search_dirs=[apps_dir])
    assert found == entry


def test_find_desktop_entry_returns_none_when_no_match(tmp_path):
    apps_dir = tmp_path / "applications"
    apps_dir.mkdir()
    assert find_desktop_entry("nonexistent", search_dirs=[apps_dir]) is None


def test_icon_name_from_desktop_entry(tmp_path):
    entry = tmp_path / "code.desktop"
    write_desktop_file(entry, name="VS Code", exec_="/usr/bin/code %F", icon="visual-studio-code")
    assert icon_name_from_desktop_entry(entry) == "visual-studio-code"


def test_resolve_icon_uses_injected_loader_and_caches(tmp_path, monkeypatch):
    import timetrace.icons as icons

    apps_dir = tmp_path / "applications"
    apps_dir.mkdir()
    write_desktop_file(apps_dir / "code.desktop", name="VS Code", exec_="/usr/bin/code %F", icon="visual-studio-code")

    monkeypatch.setattr(icons, "find_desktop_entry", lambda _: apps_dir / "code.desktop")
    monkeypatch.setattr(icons, "_icon_cache", {})
    calls = []

    def fake_loader(icon_name):
        calls.append(icon_name)
        return f"ICON[{icon_name}]"

    icon1 = resolve_icon("code", icon_loader=fake_loader)
    icon2 = resolve_icon("code", icon_loader=fake_loader)
    assert icon1 == icon2 == "ICON[visual-studio-code]"
    assert calls == ["visual-studio-code"]


def test_app_icon_is_bundled_and_not_null(qtbot):
    from timetrace.icons import app_icon

    assert not app_icon().isNull()


def test_steam_game_shortcut_is_not_matched_as_steam_app(tmp_path):
    apps_dir = tmp_path / "applications"
    apps_dir.mkdir()
    write_desktop_file(
        apps_dir / "Forza.desktop",
        name="Forza Horizon 6",
        exec_="steam steam://rungameid/2483190",
        icon="steam_icon_2483190",
    )
    steam = apps_dir / "steam.desktop"
    write_desktop_file(steam, name="Steam", exec_="/usr/bin/steam %U", icon="steam")

    assert find_desktop_entry("steam", search_dirs=[apps_dir]) == steam


def test_desktop_id_takes_priority_over_wmclass(tmp_path):
    write_desktop_file(tmp_path / 'aaa.desktop', name='Wrong', exec_='wrong', icon='wrong', startup_wm_class='org.example.App')
    target = tmp_path / 'org.example.App.desktop'
    write_desktop_file(target, name='Right', exec_='right', icon='right')
    assert find_desktop_entry('org.example.App', [tmp_path]) == target


def test_telegram_double_desktop_suffix(tmp_path):
    target = tmp_path / 'org.telegram.desktop.desktop'
    write_desktop_file(target, name='Telegram', exec_='Telegram -- %U', icon='org.telegram.desktop')
    assert find_desktop_entry('org.telegram.desktop', [tmp_path]) == target


def test_nested_desktop_id_and_env_wrapped_exec(tmp_path):
    nested = tmp_path / 'vendor'
    nested.mkdir()
    target = nested / 'App.desktop'
    write_desktop_file(target, name='Example', exec_='env MODE=test "/opt/My App/example" %U', icon='example')
    assert find_desktop_entry('vendor-App', [tmp_path]) == target
    assert find_desktop_entry('example', [tmp_path]) == target


def test_invalid_desktop_file_does_not_break_lookup(tmp_path):
    (tmp_path / 'bad.desktop').write_bytes(b'\xff\xfe')
    assert find_desktop_entry('missing', [tmp_path]) is None


def test_icon_loader_reads_absolute_file(qtbot, tmp_path):
    from PySide6.QtGui import QPixmap
    from timetrace.icons import _real_icon_loader
    path = tmp_path / 'app.png'
    image = QPixmap(16, 16)
    image.fill()
    image.save(str(path))
    assert not _real_icon_loader(str(path)).pixmap(16, 16).isNull()


def test_unknown_application_has_renderable_fallback(qtbot, monkeypatch):
    import timetrace.icons as icons
    monkeypatch.setattr(icons, 'find_desktop_entry', lambda _: None)
    assert not icons.resolve_icon('missing-app-for-test').pixmap(16, 16).isNull()


def test_xdg_and_flatpak_discovery(tmp_path, monkeypatch):
    from timetrace.desktop_entries import application_dirs
    monkeypatch.setenv('XDG_DATA_HOME', str(tmp_path / 'user'))
    monkeypatch.setenv('XDG_DATA_DIRS', str(tmp_path / 'system'))
    apps = tmp_path / 'system/applications'
    apps.mkdir(parents=True)
    target = apps / 'org.example.App.desktop'
    write_desktop_file(target, name='Example', exec_='flatpak run org.example.App', icon='example')
    with target.open('a') as file:
        file.write('X-Flatpak=org.example.App\n')
    assert application_dirs()[:2] == [tmp_path / 'user/applications', apps]
    assert find_desktop_entry('org.example.App') == target
    assert find_desktop_entry('flatpak', [apps]) is None


def test_user_hidden_entry_masks_system_entry(tmp_path):
    user, system = tmp_path / 'user', tmp_path / 'system'
    user.mkdir()
    system.mkdir()
    (user / 'app.desktop').write_text('[Desktop Entry]\nHidden=true\n')
    write_desktop_file(system / 'app.desktop', name='App', exec_='app', icon='app')
    assert find_desktop_entry('app', [user, system]) is None


def test_pixmap_fallback_without_theme(qtbot, tmp_path, monkeypatch):
    from PySide6.QtGui import QIcon, QPixmap
    import timetrace.icons as icons
    root = tmp_path / 'pixmaps'
    root.mkdir()
    image = QPixmap(16, 16)
    image.fill()
    image.save(str(root / 'isolated-test-icon.png'))
    monkeypatch.setattr(icons, 'data_dirs', lambda: [tmp_path])
    monkeypatch.setattr(QIcon, 'fromTheme', lambda _: QIcon())
    assert not icons._real_icon_loader('isolated-test-icon').pixmap(16, 16).isNull()


def test_kde_theme_category_before_size(qtbot, tmp_path, monkeypatch):
    from PySide6.QtGui import QIcon, QPixmap
    import timetrace.icons as icons
    root = tmp_path / 'icons/breeze/devices/48'
    root.mkdir(parents=True)
    image = QPixmap(16, 16)
    image.fill()
    image.save(str(root / 'microphone-test.png'))
    monkeypatch.setattr(icons, 'data_dirs', lambda: [tmp_path])
    monkeypatch.setattr(QIcon, 'fromTheme', lambda _: QIcon())
    assert not icons._real_icon_loader('microphone-test').pixmap(16, 16).isNull()
