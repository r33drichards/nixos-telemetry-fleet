import os
from pathlib import Path
import subprocess
import unittest
SCRIPT = Path(__file__).parents[1] / 'deploy/node2-health.sh'
class HealthTests(unittest.TestCase):
    def run_health(self, running='sshd', root='no'):
        fixture = r'''
        systemctl() { [[ " $RUNNING " == *" ${@: -1} "* ]]; }
        sshd() { printf '%s\n' "permitrootlogin $ROOT_POLICY" 'passwordauthentication no' 'kbdinteractiveauthentication no' 'allowusers operator' 'authorizedkeysfile /var/lib/fleet-access/authorized_keys'; }
        ip() { echo 'inet6 2001:db8::1/64 scope global'; }
        test() { if [[ "$*" == '-s /var/lib/fleet-access/authorized_keys' ]]; then return 0; else builtin test "$@"; fi; }
        source "$HEALTH_SCRIPT"
        '''
        return subprocess.run(['bash', '-c', fixture], env={**os.environ, 'RUNNING': running, 'ROOT_POLICY': root, 'HEALTH_SCRIPT': str(SCRIPT)}, capture_output=True).returncode
    def test_healthy(self): self.assertEqual(self.run_health(), 0)
    def test_comin_rejected(self): self.assertNotEqual(self.run_health('sshd comin'), 0)
    def test_unwanted_stack_rejected(self): self.assertNotEqual(self.run_health('sshd grafana'), 0)
    def test_root_login_rejected(self): self.assertNotEqual(self.run_health(root='yes'), 0)
    def test_ssh_down_rejected(self): self.assertNotEqual(self.run_health(''), 0)
