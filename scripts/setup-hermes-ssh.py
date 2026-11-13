#!/usr/bin/env python3
"""Install the node2 SSH identity from HERMES_SSH_KEY_B64; no network calls."""

import argparse
import base64
import binascii
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


BEGIN = '# BEGIN managed hermes-azure SSH'
END = '# END managed hermes-azure SSH'


def refuse_unsafe_path(path):
    if path.is_symlink():
        raise ValueError(f'Refusing symlink: {path}')
    if path.exists() and path.stat().st_uid != os.getuid():
        raise ValueError(f'Refusing a path owned by another user: {path}')


def atomic_write(path, content, mode):
    fd, name = tempfile.mkstemp(prefix='.' + path.name + '-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as out:
            out.write(content)
        os.chmod(name, mode)
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def setup(ssh_dir, encoded):
    try:
        private = base64.b64decode(''.join(encoded.split()), validate=True)
    except (binascii.Error, ValueError):
        raise ValueError('HERMES_SSH_KEY_B64 is not valid base64') from None
    if not private:
        raise ValueError('HERMES_SSH_KEY_B64 decodes to an empty key')
    if not shutil.which('ssh-keygen'):
        raise ValueError('ssh-keygen is required (install OpenSSH)')

    # Validate before touching the user's SSH configuration. -P prevents prompts.
    with tempfile.TemporaryDirectory(prefix='hermes-ssh-') as staging:
        candidate = Path(staging) / 'identity'
        candidate.write_bytes(private)
        candidate.chmod(0o600)
        result = subprocess.run(
            ['ssh-keygen', '-y', '-P', '', '-f', str(candidate)],
            capture_output=True, stdin=subprocess.DEVNULL,
        )
        if result.returncode:
            raise ValueError('Key is invalid or encrypted; an unencrypted SSH private key is required')
        public = result.stdout.strip() + b'\n'

    ssh_dir = ssh_dir.expanduser().absolute()
    if any(c in str(ssh_dir) for c in '\r\n'):
        raise ValueError('SSH directory must not contain newline characters')
    refuse_unsafe_path(ssh_dir)
    identity = ssh_dir / 'id_hermes_azure'
    public_path = ssh_dir / 'id_hermes_azure.pub'
    config = ssh_dir / 'config'
    for path in (identity, public_path, config):
        refuse_unsafe_path(path)
        if path.exists() and not path.is_file():
            raise ValueError(f'Refusing non-file path: {path}')
    if identity.exists() and identity.read_bytes() != private:
        raise ValueError('id_hermes_azure already contains a different key; it was not overwritten')
    if public_path.exists() and public_path.read_bytes().split()[:2] != public.split()[:2]:
        raise ValueError('id_hermes_azure.pub contains a different public key; it was not overwritten')

    existing = config.read_text() if config.exists() else ''
    if existing.count(BEGIN) != existing.count(END) or existing.count(BEGIN) > 1:
        raise ValueError('Malformed or duplicate managed SSH block; config was not changed')
    remainder = re.sub(
        rf'^{re.escape(BEGIN)}\n.*?^{re.escape(END)}\n(?:\n)?',
        '', existing, flags=re.MULTILINE | re.DOTALL,
    )
    if BEGIN in remainder or END in remainder:
        raise ValueError('Malformed managed SSH block; config was not changed')
    for line in remainder.splitlines():
        parts = line.split('#', 1)[0].split()
        if parts and parts[0].lower() == 'host' and 'hermes-azure' in parts[1:]:
            raise ValueError('An unmanaged Host hermes-azure already exists; config was not changed')

    quoted_identity = str(identity).replace('\\', '\\\\').replace('"', '\\"')
    block = (
        f'{BEGIN}\n'
        'Host hermes-azure\n'
        '    HostName 2603:1020:1601:8::136\n'
        '    User operator\n'
        '    Port 22\n'
        '    AddressFamily inet6\n'
        f'    IdentityFile "{quoted_identity}"\n'
        '    IdentitiesOnly yes\n'
        '\nHost *\n'
        f'{END}\n\n'
    )
    ssh_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    ssh_dir.chmod(0o700)
    if config.exists() and existing != block + remainder:
        backup_fd, backup_name = tempfile.mkstemp(prefix='config.before-hermes-', dir=ssh_dir)
        with os.fdopen(backup_fd, 'wb') as backup:
            backup.write(existing.encode())
        os.chmod(backup_name, 0o600)
    atomic_write(identity, private, 0o600)
    atomic_write(public_path, public, 0o644)
    atomic_write(config, (block + remainder).encode(), 0o600)
    print(f'Installed SSH identity: {identity}')
    print('Connect with: ssh hermes-azure')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ssh-dir', type=Path, default=Path.home() / '.ssh',
                        help='SSH directory (default: ~/.ssh)')
    args = parser.parse_args()
    encoded = os.environ.pop('HERMES_SSH_KEY_B64', '')
    if not encoded.strip():
        parser.exit(1, 'Set HERMES_SSH_KEY_B64 to the base64-encoded private key.\n')
    try:
        setup(args.ssh_dir, encoded)
    except (ValueError, OSError) as error:
        parser.exit(1, f'SSH setup failed: {error}\n')


if __name__ == '__main__':
    main()
