import base64
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).parents[1] / 'scripts/setup-hermes-ssh.py'


class SetupHermesSSHTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.ssh_dir = self.root / 'ssh config'
        key = self.root / 'test-key'
        subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(key)], check=True)
        self.private = key.read_bytes()
        self.encoded = base64.b64encode(self.private).decode()

    def run_setup(self, encoded=None):
        return subprocess.run(
            ['python3', str(SCRIPT), '--ssh-dir', str(self.ssh_dir)],
            env={**os.environ, 'HERMES_SSH_KEY_B64': self.encoded if encoded is None else encoded},
            capture_output=True, text=True,
        )

    def test_installs_effective_config_and_is_idempotent(self):
        self.ssh_dir.mkdir()
        original = 'Host *\n    User someone-else\nHost other\n    HostName example.com\n'
        config = self.ssh_dir / 'config'
        config.write_text(original)
        result = self.run_setup()
        self.assertEqual(result.returncode, 0, result.stderr)
        first = config.read_bytes()
        identity = self.ssh_dir / 'id_hermes_azure'
        self.assertEqual(identity.read_bytes(), self.private)
        for path, mode in [(self.ssh_dir, 0o700), (identity, 0o600), (config, 0o600)]:
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), mode)
        effective = subprocess.check_output(['ssh', '-G', '-F', str(config), 'hermes-azure'], text=True)
        self.assertIn('hostname 2603:1020:1601:8::136\n', effective)
        self.assertIn('user operator\n', effective)
        self.assertIn('addressfamily inet6\n', effective)
        self.assertIn('identitiesonly yes\n', effective)
        self.assertIn(f'identityfile {identity}\n', effective)
        self.assertTrue(config.read_text().endswith(original))
        self.assertEqual(self.run_setup().returncode, 0)
        self.assertEqual(config.read_bytes(), first)
        self.assertEqual(len(list(self.ssh_dir.glob('config.before-hermes-*'))), 1)
        self.assertNotIn(self.encoded, result.stdout + result.stderr)
        self.assertNotIn(self.private.decode(), result.stdout + result.stderr)

    def test_invalid_input_does_not_change_config(self):
        self.ssh_dir.mkdir()
        config = self.ssh_dir / 'config'
        config.write_text('Host other\n    HostName example.com\n')
        original = config.read_bytes()
        for value in ['', 'not base64!', base64.b64encode(b'not a private key').decode()]:
            with self.subTest(value=value):
                result = self.run_setup(value)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(config.read_bytes(), original)
                self.assertFalse((self.ssh_dir / 'id_hermes_azure').exists())

    def test_different_key_is_not_overwritten(self):
        self.assertEqual(self.run_setup().returncode, 0)
        other = self.root / 'other-key'
        subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(other)], check=True)
        result = self.run_setup(base64.b64encode(other.read_bytes()).decode())
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.ssh_dir / 'id_hermes_azure').read_bytes(), self.private)

    def test_symlink_is_not_followed(self):
        self.ssh_dir.mkdir()
        target = self.root / 'keep'
        target.write_text('unchanged')
        (self.ssh_dir / 'id_hermes_azure').symlink_to(target)
        self.assertNotEqual(self.run_setup().returncode, 0)
        self.assertEqual(target.read_text(), 'unchanged')

    def test_unmanaged_alias_is_not_overwritten(self):
        self.ssh_dir.mkdir()
        config = self.ssh_dir / 'config'
        original = 'Host other hermes-azure\n    HostName example.com\n'
        config.write_text(original)
        self.assertNotEqual(self.run_setup().returncode, 0)
        self.assertEqual(config.read_text(), original)


if __name__ == '__main__':
    unittest.main()
