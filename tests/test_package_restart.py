"""Upgrade tests exercise procfs and real child lifecycles, not GUI processes."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import pytest

from timetrace.package_restart import (
    Process, discover_instances, read_process, session_environment,
    restart_instance, worker_command,
)


@pytest.fixture
def runtime(tmp_path):
    root = tmp_path / 'usr'
    executable = root / 'lib/timetrace/glibc-2.39/timetrace'
    executable.parent.mkdir(parents=True)
    shutil.copy2(sys.executable, executable)
    launcher = root / 'bin/timetrace'
    launcher.parent.mkdir()
    return root, executable, launcher


def start_old(executable, tmp_path, ignore=False):
    ready, saved = tmp_path/'ready', tmp_path/'saved'
    script = (
        'import signal,time,pathlib,sys\n'
        f'saved=pathlib.Path({str(saved)!r})\n'
        + ('signal.signal(signal.SIGTERM, signal.SIG_IGN)\n' if ignore else
           'def stop(*args):\n saved.write_text("history flushed"); sys.exit(0)\n'
           'signal.signal(signal.SIGTERM,stop)\n')
        + f'pathlib.Path({str(ready)!r}).write_text("ready")\n'
        'while True: time.sleep(.05)\n'
    )
    child = subprocess.Popen([str(executable), '-c', script, '--minimized'],
        env={**os.environ, 'PYTHONHOME': sys.base_prefix})
    deadline = time.monotonic()+5
    while not ready.exists() and child.poll() is None and time.monotonic()<deadline:
        time.sleep(.01)
    assert ready.exists()
    return child, saved


def test_procfs_rejects_unrelated_executable_even_if_named_timetrace(runtime, tmp_path):
    root, executable, launcher = runtime
    child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(10)', 'timetrace'])
    try:
        assert read_process(child.pid, root) is None
    finally:
        child.terminate(); child.wait()


def test_procfs_reads_packaged_executable_identity_and_minimized(runtime, tmp_path):
    root, executable, launcher = runtime
    child, saved = start_old(executable, tmp_path)
    try:
        process = read_process(child.pid, root)
        assert process.pid == child.pid
        assert process.uid == os.getuid()
        assert process.start_time > 0
        assert '--minimized' in process.args
        assert process.executable == executable
    finally:
        child.terminate(); child.wait()


def test_discovery_restarts_only_leaf_of_pyinstaller_pair():
    processes = [Process(10, 1, 1000, 100, Path('/runtime'), (), {}, None),
                 Process(11, 10, 1000, 101, Path('/runtime'), (), {}, None),
                 Process(12, 1, 1001, 102, Path('/runtime'), (), {}, None)]
    assert [p.pid for p in discover_instances(processes)] == [11, 12]


def test_no_running_instances_stays_closed():
    assert discover_instances([]) == []


def test_environment_preserves_session_but_drops_frozen_and_injection_values():
    env = session_environment({'DISPLAY': ':3', 'WAYLAND_DISPLAY': 'wayland-2',
        'XDG_DATA_HOME': '/tmp/my data', 'DBUS_SESSION_BUS_ADDRESS': 'unix:path=/tmp/bus',
        'LD_LIBRARY_PATH': '/tmp/root-extraction', 'PYTHONPATH': '/tmp/inject',
        '_PYI_APPLICATION_HOME_DIR': '/tmp/root-extraction', 'HOME': '/wrong',
        'NIRI_SOCKET': '/run/user/1000/niri.sock', 'HYPRLAND_INSTANCE_SIGNATURE': 'session-id'}, os.getuid())
    assert env['DISPLAY'] == ':3'
    assert env['XDG_DATA_HOME'] == '/tmp/my data'
    assert env['DBUS_SESSION_BUS_ADDRESS'] == 'unix:path=/tmp/bus'
    assert env['HOME'] == '/wrong'
    assert env['NIRI_SOCKET'] == '/run/user/1000/niri.sock'
    assert env['HYPRLAND_INSTANCE_SIGNATURE'] == 'session-id'
    assert env['PYINSTALLER_RESET_ENVIRONMENT'] == '1'
    assert not {'LD_LIBRARY_PATH', 'PYTHONPATH', '_PYI_APPLICATION_HOME_DIR'} & env.keys()


def test_worker_command_never_passes_original_arbitrary_arguments():
    process = Process(45, 1, 1000, 123, Path('/runtime'), ('timetrace','--evil'), {}, None)
    assert worker_command(process, Path('/usr/bin/timetrace')) == [
        '/usr/bin/timetrace', '--restart-after-upgrade', '45', '123']


def test_manual_restart_flushes_before_launch_and_keeps_minimized(runtime, tmp_path):
    root, executable, launcher = runtime
    child, saved = start_old(executable, tmp_path)
    launched = tmp_path/'launched'
    launcher.write_text(f'#!/bin/sh\ntest -f "{saved}" || exit 9\nprintf "%s" "$*" > "{launched}"\n')
    launcher.chmod(0o755)
    try:
        process = read_process(child.pid, root)
        assert restart_instance(process, root, timeout=2) == 0
        child.wait(timeout=3)
        deadline=time.monotonic()+3
        while not launched.exists() and time.monotonic()<deadline:
            time.sleep(.01)
        assert saved.read_text() == 'history flushed'
        assert launched.read_text() == '--minimized'
    finally:
        if child.poll() is None: child.kill(); child.wait()


def test_pid_identity_mismatch_never_signals_old_process(runtime, tmp_path):
    from dataclasses import replace
    root, executable, launcher = runtime
    child, saved = start_old(executable, tmp_path)
    try:
        process = read_process(child.pid, root)
        assert restart_instance(replace(process, start_time=process.start_time+1), root, timeout=.1) != 0
        assert child.poll() is None
        assert not saved.exists()
    finally:
        child.terminate(); child.wait()


def test_unresponsive_old_process_is_not_killed_or_duplicated(runtime, tmp_path):
    root, executable, launcher = runtime
    child, saved = start_old(executable, tmp_path, ignore=True)
    launched = tmp_path/'launched'
    launcher.write_text(f'#!/bin/sh\ntouch "{launched}"\n')
    launcher.chmod(0o755)
    try:
        process=read_process(child.pid, root)
        assert restart_instance(process, root, timeout=.1) != 0
        assert child.poll() is None
        assert not launched.exists()
    finally:
        child.kill(); child.wait()


def test_managed_instance_restarts_through_user_service_manager(runtime, tmp_path, monkeypatch):
    from dataclasses import replace
    root, executable, launcher = runtime
    child, saved = start_old(executable, tmp_path)
    calls=[]
    def systemctl(command, **options):
        calls.append((command, options))
        return subprocess.CompletedProcess(command, 0,
            'ActiveState=inactive\nMainPID=0\n' if saved.exists() else f'ActiveState=active\nMainPID={child.pid}\n')
    monkeypatch.setattr(subprocess, 'run', systemctl)
    try:
        process=replace(read_process(child.pid, root), unit='app-timetrace@autostart.service')
        assert restart_instance(process, root) == 0
        assert calls[-1][0] == ['/usr/bin/systemctl', '--user', 'start', 'app-timetrace@autostart.service']
        assert not any('restart' in call[0] or 'stop' in call[0] for call in calls)
        assert 'LD_LIBRARY_PATH' not in calls[0][1]['env']
        child.wait(timeout=2)
        assert saved.read_text() == 'history flushed'
    finally:
        child.terminate(); child.wait()


def test_maintenance_arguments_do_not_import_qt():
    command = ('import sys; sys.modules["PySide6"]=None; '
               'from timetrace.__main__ import main; '
               'raise SystemExit(main(["--restart-after-upgrade", "invalid"]))')
    result=subprocess.run([sys.executable, '-c', command], capture_output=True, text=True)
    assert result.returncode == 2
    assert 'PySide6' not in result.stderr


@pytest.mark.parametrize('kind,args,should_restart', [
    ('arch', ['upgrade'], True),
    ('deb', ['configure', '0.1.7'], True),
    ('deb', ['configure'], False),
    ('deb', ['abort-upgrade', '0.1.7'], False),
    ('rpm', ['2'], True),
    ('rpm', ['1'], False),
    ('rpm', ['0'], False),
])
@pytest.mark.parametrize('exit_code', [0, 1])
def test_installer_lifecycle_only_restarts_after_upgrade(tmp_path, kind, args, should_restart, exit_code):
    packaging=Path(__file__).resolve().parents[1]/'packaging'
    scripts={'arch':'timetrace.install','deb':'deb-postinst.sh','rpm':'rpm-post.sh'}
    log=tmp_path/'invocations'
    driver = ('function /usr/bin/timetrace() { printf "%s\\n" "$*" >> "$INVOCATIONS"; return "$RESULT"; }; '
              'script=$1; shift; source "$script" "$@" || exit $?; '
              + ('post_upgrade 0.1.8 0.1.7' if kind=='arch' else ':'))
    result=subprocess.run(['bash','-c',driver,'test',str(packaging/scripts[kind]),*args],
        env={**os.environ,'INVOCATIONS':str(log),'RESULT':str(exit_code)},capture_output=True,text=True)
    assert result.returncode == 0, result.stderr
    assert log.exists() is should_restart
    if should_restart:
        assert log.read_text() == '--restart-running\n'


def test_manual_app_inside_unrelated_user_service_does_not_restart_that_service(runtime, tmp_path, monkeypatch):
    from dataclasses import replace
    root, executable, launcher = runtime
    child, saved = start_old(executable, tmp_path)
    launched=tmp_path/'launched'
    launcher.write_text(f'#!/bin/sh\ntouch "{launched}"\n')
    launcher.chmod(0o755)
    calls=[]
    def systemctl(command, **options):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, f'ActiveState=active\nMainPID={os.getpid()}\n')
    monkeypatch.setattr(subprocess, 'run', systemctl)
    try:
        process=replace(read_process(child.pid, root),unit='tmux.service')
        assert restart_instance(process,root,timeout=.5) == 0
        child.wait(timeout=2)
        deadline=time.monotonic()+2
        while not launched.exists() and time.monotonic()<deadline: time.sleep(.01)
        assert launched.exists()
        assert saved.read_text() == 'history flushed'
        assert all(command[2] == 'show' for command in calls)
    finally:
        if child.poll() is None: child.kill(); child.wait()


def test_custom_home_keeps_the_existing_history_location():
    from timetrace.paths import db_file_path
    original={'HOME':'/srv/custom-home'}
    assert db_file_path(session_environment(original, os.getuid())) == Path('/srv/custom-home/.local/share/timetrace/data.db')


def test_collected_transient_service_falls_back_to_manual_launch(runtime, tmp_path, monkeypatch):
    from dataclasses import replace
    root,executable,launcher=runtime
    child,saved=start_old(executable,tmp_path)
    launched=tmp_path/'launched'
    launcher.write_text(f'#!/bin/sh\ntouch "{launched}"\n')
    launcher.chmod(0o755)
    def systemctl(command,**options):
        if saved.exists():
            return subprocess.CompletedProcess(command,1,'LoadState=not-found\nMainPID=0\n', 'Unit was collected')
        return subprocess.CompletedProcess(command,0,f'MainPID={child.pid}\n')
    monkeypatch.setattr(subprocess,'run',systemctl)
    try:
        process=replace(read_process(child.pid,root),unit='app-transient.service')
        assert restart_instance(process,root,timeout=2)==0
        child.wait(timeout=2)
        deadline=time.monotonic()+2
        while not launched.exists() and time.monotonic()<deadline: time.sleep(.01)
        assert launched.exists()
        assert saved.read_text()=='history flushed'
    finally:
        if child.poll() is None: child.kill();child.wait()
