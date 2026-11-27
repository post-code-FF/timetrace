"""Package-manager maintenance, deliberately imported before Qt.

Root only discovers packaged processes and spawns workers after dropping all
privileges. Workers recheck procfs identity before touching their own process.
"""
from dataclasses import dataclass
import os
from pathlib import Path
try:
    import pwd
except ModuleNotFoundError:  # Windows has no POSIX account database.
    pwd = None
import re
import signal
import subprocess
import sys
import time


INSTALL_ROOT = Path('/usr')


@dataclass(frozen=True)
class Process:
    pid: int
    ppid: int
    uid: int
    start_time: int
    executable: Path
    args: tuple[str, ...]
    environment: dict[str, str]
    unit: str | None


def read_process(pid: int, install_root: Path = INSTALL_ROOT) -> Process | None:
    """Reject unrelated binaries; executable identity never comes from argv."""
    directory = Path('/proc') / str(pid)
    try:
        stat = (directory/'stat').read_text().rsplit(')', 1)[1].split()
        if stat[0] == 'Z':
            return None
        executable = Path(os.readlink(directory/'exe').removesuffix(' (deleted)'))
        relative = executable.relative_to(install_root/'lib/timetrace')
        if not re.fullmatch(r'glibc-\d+\.\d+/timetrace', str(relative)):
            return None
        args = tuple(os.fsdecode(arg) for arg in (directory/'cmdline').read_bytes().split(b'\0') if arg)
        environment = dict(os.fsdecode(item).split('=', 1) for item in
                           (directory/'environ').read_bytes().split(b'\0') if b'=' in item)
        unit = None
        for line in (directory/'cgroup').read_text().splitlines():
            hierarchy, controllers, cgroup = line.split(':', 2)
            parts = cgroup.split('/')
            # A system service or user@UID.service is not an app user service.
            if f'user@{directory.stat().st_uid}.service' in parts:
                candidate = parts[-1]
                if candidate.endswith('.service') and not candidate.startswith('user@'):
                    unit = candidate
        return Process(pid, int(stat[1]), directory.stat().st_uid, int(stat[19]),
                       executable, args, environment, unit)
    except (OSError, ValueError, IndexError):
        return None


def discover_instances(processes: list[Process]) -> list[Process]:
    # In a onefile build both bootloader and Python child have the same exe.
    # Only signal/restart the leaf (Python) process. The bootloader then exits.
    parents = {process.ppid for process in processes}
    return [process for process in processes if process.pid not in parents]


def session_environment(original: dict[str, str], uid: int) -> dict[str, str]:
    account = pwd.getpwuid(uid)
    allowed = {'DISPLAY', 'WAYLAND_DISPLAY', 'XAUTHORITY', 'DBUS_SESSION_BUS_ADDRESS',
               'XDG_RUNTIME_DIR', 'XDG_SESSION_TYPE', 'XDG_CURRENT_DESKTOP',
               'XDG_SESSION_DESKTOP', 'DESKTOP_SESSION', 'XDG_CONFIG_HOME',
               'XDG_DATA_HOME', 'XDG_STATE_HOME', 'XDG_CACHE_HOME', 'XDG_DATA_DIRS',
               'XDG_CONFIG_DIRS', 'LANG', 'LANGUAGE', 'TZ', 'QT_QPA_PLATFORM',
               'QT_SCALE_FACTOR', 'QT_SCREEN_SCALE_FACTORS', 'QT_AUTO_SCREEN_SCALE_FACTOR',
               'NIRI_SOCKET', 'HYPRLAND_INSTANCE_SIGNATURE', 'SWAYSOCK', 'I3SOCK'}
    result = {key: value for key, value in original.items()
              if key in allowed or key.startswith('LC_')}
    result.update(HOME=original.get('HOME') or account.pw_dir, USER=account.pw_name, LOGNAME=account.pw_name,
                  PATH='/usr/bin:/bin', PYINSTALLER_RESET_ENVIRONMENT='1')
    return result


def worker_command(process: Process, launcher: Path) -> list[str]:
    return [str(launcher), '--restart-after-upgrade', str(process.pid), str(process.start_time)]


def _same_instance(expected: Process, actual: Process | None) -> bool:
    return actual is not None and (expected.pid, expected.start_time, expected.uid,
                                  expected.executable) == (actual.pid, actual.start_time,
                                                          actual.uid, actual.executable)


def restart_instance(process: Process, install_root: Path = INSTALL_ROOT,
                     timeout: float = 15.0) -> int:
    current = read_process(process.pid, install_root)
    if process.uid != os.getuid() or not _same_instance(process, current):
        print('TimeTrace: upgrade restart skipped: process identity changed.', file=sys.stderr)
        return 1
    environment = session_environment(process.environment, process.uid)
    launcher = install_root/'bin/timetrace'
    try:
        ancestors = [process]
        parent = read_process(process.ppid, install_root)
        while parent is not None and parent.uid == process.uid:
            ancestors.append(parent)
            parent = read_process(parent.ppid, install_root)
        old_pids = {old.pid for old in ancestors}
        managed = False
        if process.unit:
            state = subprocess.run(['/usr/bin/systemctl', '--user', 'show', process.unit,
                '--property=MainPID'], env=environment, timeout=timeout,
                capture_output=True, text=True)
            if state.returncode:
                print(state.stderr, file=sys.stderr)
                return 1
            properties = dict(line.split('=', 1) for line in state.stdout.splitlines() if '=' in line)
            # Manual launches from tmux.service or another host service inherit
            # its cgroup. Never stop/start a service whose main isn't our app.
            managed = int(properties.get('MainPID', '0')) in old_pids
        # pidfd pins the process across the final identity check and SIGTERM.
        descriptor = os.pidfd_open(process.pid)
        try:
            if not _same_instance(process, read_process(process.pid, install_root)):
                return 1
            signal.pidfd_send_signal(descriptor, signal.SIGTERM)
        finally:
            os.close(descriptor)
        deadline = time.monotonic()+timeout
        while any(_same_instance(old, read_process(old.pid, install_root)) for old in ancestors):
            if time.monotonic() >= deadline:
                print('TimeTrace: old instance did not exit; leaving it running.', file=sys.stderr)
                return 1
            time.sleep(.05)
        if managed:
            # Do not ask systemd to stop/restart: its stop timeout could apply
            # SIGKILL to an unresponsive app. We already stopped it gracefully.
            # Wait for the manager to reap the old bootloader before start().
            while time.monotonic() < deadline:
                state = subprocess.run(['/usr/bin/systemctl', '--user', 'show', process.unit,
                    '--property=ActiveState', '--property=MainPID', '--property=LoadState'], env=environment,
                    timeout=max(.1, deadline-time.monotonic()), capture_output=True, text=True)
                properties = dict(line.split('=', 1) for line in state.stdout.splitlines() if '=' in line)
                if properties.get('LoadState') == 'not-found':
                    break  # A collected transient unit cannot be started again.
                if state.returncode:
                    print(state.stderr, file=sys.stderr)
                    return 1
                if properties.get('ActiveState') in ('inactive', 'failed'):
                    return subprocess.run(['/usr/bin/systemctl', '--user', 'start', process.unit],
                        env=environment, timeout=max(.1, deadline-time.monotonic()), check=False).returncode
                if properties.get('ActiveState') in ('active', 'activating') and int(properties.get('MainPID', '0')) not in old_pids | {0}:
                    return 0  # Restart=always/on-success already launched a new process.
                time.sleep(.05)
            else:
                print('TimeTrace: user service did not finish graceful shutdown.', file=sys.stderr)
                return 1
        args = [str(launcher)]
        if '--minimized' in process.args:
            args.append('--minimized')
        subprocess.Popen(args, env=environment, stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
        return 0
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print(f'TimeTrace: upgrade restart failed: {exc}', file=sys.stderr)
        return 1


def restart_running(install_root: Path = INSTALL_ROOT) -> int:
    if os.geteuid() != 0:
        print('TimeTrace: package upgrade maintenance requires root.', file=sys.stderr)
        return 1
    processes = [process for entry in Path('/proc').iterdir() if entry.name.isdecimal()
                 if (process := read_process(int(entry.name), install_root)) is not None
                 and process.uid != 0 and '--restart-after-upgrade' not in process.args]
    result = 0
    for process in discover_instances(processes):
        try:
            account = pwd.getpwuid(process.uid)
            environment = session_environment(process.environment, process.uid)
            def demote():
                os.initgroups(account.pw_name, account.pw_gid)
                os.setgid(account.pw_gid)
                os.setuid(account.pw_uid)
            # Popen is called before Qt/threads exist. preexec_fn never executes
            # user content; the installed launcher is exec'd only after setuid.
            worker = subprocess.Popen(worker_command(process, install_root/'bin/timetrace'),
                env=environment, preexec_fn=demote, cwd='/', start_new_session=True,
                stdin=subprocess.DEVNULL)
            try:
                result |= int(worker.wait(timeout=25) != 0)
            except subprocess.TimeoutExpired:
                print(f'TimeTrace: restart worker for UID {process.uid} timed out.', file=sys.stderr)
                result = 1
        except (KeyError, OSError, subprocess.SubprocessError) as exc:
            print(f'TimeTrace: could not restart UID {process.uid}: {exc}', file=sys.stderr)
            result = 1
    return result


def maintenance_main(argv: list[str]) -> int | None:
    if pwd is None:
        return None
    if argv == ['--restart-running']:
        return restart_running()
    if argv[:1] == ['--restart-after-upgrade']:
        if len(argv) != 3:
            return 2
        try:
            pid, start_time = map(int, argv[1:])
        except ValueError:
            return 2
        process = read_process(pid)
        if process is None or process.uid == 0 or process.start_time != start_time:
            return 1
        return restart_instance(process)
    return None
