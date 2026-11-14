import json
import pytest
from timetrace.backends.session_gnome import EventStream, GnomeSessionBackend


def packet(seq=1, ts=1000, epoch='a', **kwargs):
    event = dict(version=1, epoch=epoch, seq=seq, ts=ts, mono=ts,
                 locked=False, available=True, idle_ms=0,
                 app_id='org.gnome.Terminal.desktop', title='Terminal')
    event.update(kwargs)
    return json.dumps(dict(events=[event], overflow=False))


def test_deduplicates_signal_poll_and_restores_new_epoch():
    stream = EventStream()
    assert len(list(stream.decode(packet()))) == 1
    assert list(stream.decode(packet())) == []
    assert list(stream.decode(packet(seq=2, ts=2000)))[0]['ts'] == 2000
    assert len(list(stream.decode(packet(epoch='b', ts=3000)))) == 1
    assert stream.cursor == 'b:1'


def test_replays_missing_focus_transitions_in_order():
    stream = EventStream()
    first = json.loads(packet())['events'][0]
    second = json.loads(packet(seq=2, ts=2000, app_id='firefox.desktop'))['events'][0]
    assert [e['app_id'] for e in stream.decode(json.dumps(dict(events=[first, second])))] == [
        'org.gnome.Terminal.desktop', 'firefox.desktop']


def test_backward_clock_never_produces_negative_intervals():
    stream = EventStream()
    list(stream.decode(packet(ts=2000)))
    assert list(stream.decode(packet(seq=2, ts=1000)))[0]['ts'] == 2000


@pytest.mark.parametrize('update', [dict(version=2), dict(idle_ms='bad'), dict(locked=1), dict(fullscreen=1)])
def test_rejects_invalid_protocol(update):
    with pytest.raises(ValueError):
        list(EventStream().decode(packet(**update)))


def test_overflow_does_not_invent_missing_history(caplog):
    stream = EventStream()
    event = json.loads(packet())['events'][0]
    assert len(list(stream.decode(json.dumps(dict(events=[event], overflow=True))))) == 1
    assert 'overflow' in caplog.text


def test_idle_lock_missing_api_and_extension_stop_pause_accounting():
    backend = GnomeSessionBackend.__new__(GnomeSessionBackend)
    windows, presence = [], []
    backend._window = lambda *a: windows.append(a)
    backend._presence = lambda *a: presence.append(a)
    backend._threshold = 5000
    backend._last_state = None
    for seq, change in enumerate([{}, dict(idle_ms=6000), dict(locked=True),
                                  dict(available=False), dict(idle_ms=-1), {}], 1):
        backend._accept(json.loads(packet(seq=seq, ts=seq*1000, **change))['events'][0])
    assert presence == [(False, False, 1000), (True, False, 2000),
                        (False, True, 3000), (False, False, 6000)]
    assert [w[0] for w in windows] == ['org.gnome.Terminal.desktop'] * 2 + [''] * 3 + ['org.gnome.Terminal.desktop']


def test_gjs_extension_protocol_lifecycle():
    import shutil
    import subprocess
    from pathlib import Path
    if not shutil.which('gjs'):
        pytest.skip('GJS is not installed')
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(['gjs', '-m', str(root / 'tests/extension-harness.js'),
                             str(root / 'src/timetrace/assets/gnome_extension/extension.js')],
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    assert 'PASS' in result.stdout


def test_restarted_shell_marks_unobserved_gap():
    stream = EventStream()
    list(stream.decode(packet(ts=1000)))
    event = list(stream.decode(packet(ts=9000, epoch='new-shell')))[0]
    assert event['gap_since'] == 1000


def test_start_installs_bundled_extension(qtbot, tmp_path, monkeypatch):
    import subprocess
    from timetrace.backends import gnome_extension
    data_home = tmp_path / 'data'
    monkeypatch.setenv('XDG_DATA_HOME', str(data_home))

    def shell_command(args, **kwargs):
        return subprocess.CompletedProcess(args, 0, 'GNOME Shell 51.1\n', '')

    monkeypatch.setattr(gnome_extension.subprocess, 'run', shell_command)
    backend = GnomeSessionBackend()
    try:
        backend.start(lambda *args: None)
        installed = data_home / 'gnome-shell/extensions/timetrace@timetrace.app/extension.js'
        assert installed.is_file()
        assert 'GetEvents' in installed.read_text()
    finally:
        backend.stop()


def test_fullscreen_exempts_idle_but_never_lock_or_missing_bridge():
    backend = GnomeSessionBackend.__new__(GnomeSessionBackend)
    presence = []
    backend._window = None
    backend._presence = lambda *args: presence.append(args)
    backend._threshold = 5000
    backend._last_state = None
    for seq, change in enumerate([
        dict(fullscreen=True), dict(fullscreen=False),
        dict(fullscreen=True, locked=True), dict(fullscreen=True, available=False),
    ], 1):
        backend._accept(json.loads(packet(seq=seq, ts=seq*1000, idle_ms=7000, **change))['events'][0])
    assert presence == [(False, False, 1000), (True, False, 2000), (False, True, 3000)]


def test_old_loaded_extension_keeps_upgrade_notice_until_fullscreen_is_supported(qtbot):
    from PySide6.QtDBus import QDBusMessage
    backend = GnomeSessionBackend()
    backend._stopped = False
    backend.extension_notice = 'Выйдите из сеанса GNOME и войдите снова.'

    class Reply:
        def __init__(self, payload):
            self.payload = payload
        def reply(self):
            return self
        def type(self):
            return QDBusMessage.MessageType.ReplyMessage
        def arguments(self):
            return [self.payload]
        def deleteLater(self):
            pass

    backend._reply(Reply(packet()))
    assert backend.extension_notice and 'GNOME' in backend.extension_notice
    backend._reply(Reply(packet(seq=2, fullscreen=False)))
    assert backend.extension_notice is None
    backend.stop()
