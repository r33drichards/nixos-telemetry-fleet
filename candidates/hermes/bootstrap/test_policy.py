"""Synthetic policies plus real sshd parsing; no listeners or installed keys."""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent
COMMON = 'permitrootlogin no\npasswordauthentication no\nkbdinteractiveauthentication no\nallowusers operator hermes-tunnel\n'
OPERATOR = COMMON + 'authorizedkeysfile /var/lib/fleet-access/authorized_keys\npermittty yes\nmaxsessions 10\n'
TUNNEL = COMMON + '''authenticationmethods publickey
authorizedkeysfile /var/lib/fleet-access/hermes-tunnel-authorized_keys
allowtcpforwarding remote
permitlisten 127.0.0.1:16667
permitopen none
gatewayports no
maxsessions 0
permittty no
allowagentforwarding no
x11forwarding no
allowstreamlocalforwarding no
permittunnel no
disableforwarding no
'''

class PolicyTests(unittest.TestCase):
    def check(self, operator, tunnel, expected):
        with tempfile.TemporaryDirectory() as d:
            a,b=Path(d)/'operator',Path(d)/'tunnel'
            a.write_text(operator); b.write_text(tunnel)
            r=subprocess.run(['sh',str(ROOT/'check-ssh-policy.sh'),str(a),str(b)],capture_output=True)
            self.assertEqual(r.returncode==0,expected, r.stderr.decode())
    def test_approved(self): self.check(OPERATOR,TUNNEL,True)
    def test_directive_name_case(self):
        def capitalized(policy):
            return '\n'.join(line.split(' ',1)[0].upper()+' '+line.split(' ',1)[1] for line in policy.splitlines())+'\n'
        self.check(capitalized(OPERATOR),capitalized(TUNNEL),True)
    def test_order(self): self.check(OPERATOR.replace('operator hermes-tunnel','hermes-tunnel operator'),TUNNEL,True)
    def test_each_tunnel_restriction(self):
        for line in TUNNEL.splitlines():
            with self.subTest(line=line): self.check(OPERATOR,TUNNEL.replace(line+'\n',''),False)
    def test_repeated_allowusers_lines(self):
        self.check(OPERATOR.replace('allowusers operator hermes-tunnel', 'allowusers operator\nallowusers hermes-tunnel'),TUNNEL,True)
        self.check(OPERATOR,TUNNEL + 'allowusers intruder\n',False)
    def test_broadening(self):
        for before,after in [('permitlisten 127.0.0.1:16667','permitlisten *:16667'),('allowtcpforwarding remote','allowtcpforwarding yes'),('gatewayports no','gatewayports yes'),('maxsessions 0','maxsessions 1'),('permittty no','permittty yes'),('disableforwarding no','disableforwarding yes'),('authenticationmethods publickey','authenticationmethods any')]:
            with self.subTest(after=after): self.check(OPERATOR,TUNNEL.replace(before,after),False)
    def test_unexpected_users(self):
        for users in ['operator','operator hermes-tunnel intruder','operator hermes-*','operator hermes-tunnel operator']:
            with self.subTest(users=users): self.check(OPERATOR,TUNNEL.replace('operator hermes-tunnel',users),False)
    def test_operator_preserved(self):
        for before,after in [('passwordauthentication no','passwordauthentication yes'),('permitrootlogin no','permitrootlogin yes'),('permittty yes','permittty no'),('maxsessions 10','maxsessions 0'),('authorizedkeysfile /var/lib/fleet-access/authorized_keys','authorizedkeysfile .ssh/authorized_keys')]:
            with self.subTest(after=after): self.check(OPERATOR.replace(before,after),TUNNEL,False)
    def test_duplicate_or_deny(self):
        for extra in ['permittty yes\n','denyusers operator\n','allowgroups another\n']:
            with self.subTest(extra=extra): self.check(OPERATOR,TUNNEL+extra,False)
    def test_public_key_parameter_shape(self):
        import base64, struct
        text=(ROOT.parent/'tunnel.nix').read_text()
        pattern=re.search(r'builtins.match "([^"]+)" key',text).group(1)
        for byte in [0,1,127,255]:
            blob=struct.pack('>I',11)+b'ssh-ed25519'+struct.pack('>I',32)+bytes([byte])*32
            key='ssh-ed25519 '+base64.b64encode(blob).decode()
            self.assertIsNotNone(re.fullmatch(pattern,key))
            for bad in [key+'\n',key+' comment',key+'\n'+key,'restrict '+key,key.replace('ssh-ed25519','ssh-rsa',1),key[:-1]]:
                self.assertIsNone(re.fullmatch(pattern,bad))
    def test_real_sshd(self):
        sshd=shutil.which('sshd')
        self.assertIsNotNone(sshd, 'real sshd required; do not silently skip')
        with tempfile.TemporaryDirectory() as d:
            key=Path(d)/'fixture-host-key'
            # Disposable local test fixture, never authorized on any host.
            subprocess.run(['ssh-keygen','-q','-t','ed25519','-N','','-f',str(key)],check=True)
            text=(ROOT.parent/'tunnel.nix').read_text()
            match=re.search(r"extraConfig = ''\n(.*?)\n    '';",text,re.S).group(1)
            config=Path(d)/'sshd_config'
            config.write_text(f'HostKey {key}\nUsePAM no\nPermitRootLogin no\nPasswordAuthentication no\nKbdInteractiveAuthentication no\nAllowUsers operator hermes-tunnel\nAuthorizedKeysFile /var/lib/fleet-access/authorized_keys\n'+match+'\n')
            policies=[]
            for user in ['operator','hermes-tunnel']:
                r=subprocess.run([sshd,'-T','-f',str(config),'-C',f'user={user},host=fixture,addr=2001:db8::1,laddr=2001:db8::2,lport=22'],text=True,capture_output=True)
                self.assertEqual(r.returncode,0,r.stderr)
                policies.append(r.stdout)
            self.check(*policies,True)

if __name__=='__main__': unittest.main(verbosity=2)
