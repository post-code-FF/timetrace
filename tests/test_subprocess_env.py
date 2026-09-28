from timetrace.subprocess_env import system_subprocess_env


def test_returns_none_when_not_frozen(monkeypatch):
    import sys

    monkeypatch.setattr(sys, "frozen", False, raising=False)
    assert system_subprocess_env({"LD_LIBRARY_PATH": "/bundle/lib"}) is None


def test_restores_original_ld_library_path_when_frozen(monkeypatch):
    import sys

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    env = {
        "PATH": "/usr/bin",
        "LD_LIBRARY_PATH": "/bundle/lib",
        "LD_LIBRARY_PATH_ORIG": "/usr/lib/x86_64-linux-gnu",
    }
    result = system_subprocess_env(env)
    assert result["LD_LIBRARY_PATH"] == "/usr/lib/x86_64-linux-gnu"
    assert "LD_LIBRARY_PATH_ORIG" not in result
    assert result["PATH"] == "/usr/bin"


def test_strips_ld_library_path_when_frozen_and_no_original(monkeypatch):
    import sys

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    env = {"PATH": "/usr/bin", "LD_LIBRARY_PATH": "/bundle/lib"}
    result = system_subprocess_env(env)
    assert "LD_LIBRARY_PATH" not in result
    assert result["PATH"] == "/usr/bin"


def test_noop_when_frozen_and_ld_library_path_never_set(monkeypatch):
    import sys

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    env = {"PATH": "/usr/bin"}
    result = system_subprocess_env(env)
    assert result == {"PATH": "/usr/bin"}
