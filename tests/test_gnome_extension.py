import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from timetrace.backends.gnome_extension import install_and_enable


class GnomeExtensionInstallationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.extensions = Path(self.temp.name) / 'extensions'
        self.target = self.extensions / 'timetrace@timetrace.app'

    def commands(self, major=51, enable_code=0):
        return patch('timetrace.backends.gnome_extension.subprocess.run', side_effect=[
            subprocess.CompletedProcess(['gnome-shell', '--version'], 0, f'GNOME Shell {major}.1\n', ''),
            subprocess.CompletedProcess(['gnome-extensions', 'enable'], enable_code, '', ''),
        ])

    def test_first_launch_installs_bundled_extension_in_original_uuid(self):
        with self.commands():
            self.assertIsNone(install_and_enable(self.extensions))
        metadata = json.loads((self.target / 'metadata.json').read_text())
        self.assertEqual(metadata['uuid'], 'timetrace@timetrace.app')
        self.assertEqual(metadata['shell-version'], ['51'])
        self.assertIn('GetEvents', (self.target / 'extension.js').read_text())

    def test_update_replaces_old_code_and_requests_relogin(self):
        self.target.mkdir(parents=True)
        (self.target / 'extension.js').write_text('old extension')
        with self.commands():
            notice = install_and_enable(self.extensions)
        self.assertIn('войдите', notice)
        self.assertIn('GetEvents', (self.target / 'extension.js').read_text())

    def test_unchanged_extension_is_not_rewritten_or_reported_as_an_update(self):
        with self.commands():
            install_and_enable(self.extensions)
        before = (self.target / 'extension.js').stat().st_mtime_ns
        with self.commands():
            self.assertIsNone(install_and_enable(self.extensions))
        self.assertEqual((self.target / 'extension.js').stat().st_mtime_ns, before)

    def test_shell_must_discover_first_install_before_enabling(self):
        with self.commands(enable_code=2):
            notice = install_and_enable(self.extensions)
        self.assertTrue((self.target / 'extension.js').is_file())
        self.assertIn('войдите', notice)

    def test_other_gnome_versions_do_not_get_an_incompatible_extension(self):
        for major in (50, 52):
            with self.commands(major=major):
                self.assertIsNotNone(install_and_enable(self.extensions))
            self.assertFalse(self.extensions.exists())

    def test_missing_cli_and_timeouts_do_not_crash_or_write_files(self):
        for error in (FileNotFoundError(), subprocess.TimeoutExpired('gnome-shell', 5)):
            with patch('timetrace.backends.gnome_extension.subprocess.run', side_effect=error):
                self.assertIsNotNone(install_and_enable(self.extensions))
            self.assertFalse(self.extensions.exists())

    def test_unwritable_destination_does_not_crash_startup(self):
        self.extensions.write_text('not a directory')
        with self.commands():
            self.assertIsNotNone(install_and_enable(self.extensions))
        self.assertEqual(self.extensions.read_text(), 'not a directory')

    def test_xdg_data_home_is_used(self):
        with patch.dict('os.environ', {'XDG_DATA_HOME': self.temp.name}), self.commands():
            install_and_enable()
        self.assertTrue((Path(self.temp.name) / 'gnome-shell/extensions/timetrace@timetrace.app/extension.js').is_file())
