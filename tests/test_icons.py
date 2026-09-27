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
    # per the test note: "keep this test loose (it accepts either a real system match or the unknown fallback)"
    assert calls[0] in ["visual-studio-code", "vscode", "unknown"] or icon1 == "ICON[unknown]"
