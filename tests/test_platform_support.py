import sys


def test_platform_flags_match_runtime():
    from timetrace.platform_support import IS_LINUX, IS_WINDOWS

    assert IS_WINDOWS is (sys.platform == "win32")
    assert IS_LINUX is sys.platform.startswith("linux")


def test_package_restart_imports_on_windows_without_pwd():
    import timetrace.package_restart as maintenance

    assert hasattr(maintenance, "maintenance_main")