import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
ROOT = Path(__file__).parents[1]
class UploadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); (self.root/'scripts').mkdir(); (self.root/'bin').mkdir()
        for file in ('cachix-upload.sh', 'check-cachix-spec.py'):
            shutil.copyfile(ROOT/'scripts'/file, self.root/'scripts'/file)
        self.spec = {'agents': {'node2': '/nix/store/'+'a'*32+'-nixos-system-node2'}, 'rollbackScript': {'x86_64-linux': '/nix/store/'+'b'*32+'-node2-health/bin/node2-health'}}
        (self.root/'deploy-result').write_text(json.dumps(self.spec))
        self.env = {**os.environ, 'PATH': str(self.root/'bin')+':'+os.environ['PATH'], 'GITHUB_REF':'refs/heads/main', 'GITHUB_SHA':'c'*40, 'EXPECTED_REVISION':'c'*40, 'UPLOAD_APPROVED':'explicitly-approved', 'CACHIX_AUTH_TOKEN':'synthetic-secret', 'EXPECTED_SPEC_SHA256':hashlib.sha256((self.root/'deploy-result').read_bytes()).hexdigest(), 'CALLS':str(self.root/'calls')}
        self.mock('nix', 'printf "%s\\n" "$*" >> "$CALLS"')
        self.mock('readlink', 'printf "%s\\n" /nix/store/cccccccccccccccccccccccccccccccc-deploy.json')
    def mock(self, name, text):
        p=self.root/'bin'/name; p.write_text('#!/bin/bash\nset -eu\n'+text+'\n'); p.chmod(0o755)
    def run_phase(self, phase, **changes):
        result=subprocess.run(['bash','scripts/cachix-upload.sh',phase],cwd=self.root,env={**self.env,**changes},capture_output=True,text=True)
        self.assertNotIn('synthetic-secret', result.stdout+result.stderr)
        return result.returncode
    def calls(self): return (self.root/'calls').read_text() if (self.root/'calls').exists() else ''
    def test_prepare_builds_without_token(self):
        self.assertEqual(self.run_phase('prepare', CACHIX_AUTH_TOKEN=''),0)
        self.assertEqual(self.calls().count('build -L'),2); self.assertNotIn('push',self.calls())
    def test_upload_only(self):
        self.assertEqual(self.run_phase('upload'),0)
        self.assertIn('-c cachix push r33drichards-nixos-fleet /nix/store/',self.calls())
        self.assertNotIn('activate',self.calls()); self.assertNotIn('build',self.calls())
    def test_missing_token(self):
        self.assertNotEqual(self.run_phase('upload',CACHIX_AUTH_TOKEN=''),0); self.assertEqual(self.calls(),'')
    def test_wrong_revision(self):
        self.assertNotEqual(self.run_phase('upload',EXPECTED_REVISION='d'*40),0); self.assertEqual(self.calls(),'')
    def test_wrong_spec(self):
        self.assertNotEqual(self.run_phase('upload',EXPECTED_SPEC_SHA256='0'*64),0); self.assertEqual(self.calls(),'')
    def test_gate_cannot_be_replaced_by_activation_gate(self):
        self.assertNotEqual(self.run_phase('upload',UPLOAD_APPROVED='',ACTIVATION_APPROVED='explicitly-approved'),0); self.assertEqual(self.calls(),'')
    def test_activation_is_not_an_operation(self):
        self.assertNotEqual(self.run_phase('activate'),0); self.assertEqual(self.calls(),'')
    def test_nonmain_rejected(self):
        self.assertNotEqual(self.run_phase('upload',GITHUB_REF='refs/heads/feature'),0); self.assertEqual(self.calls(),'')
    def test_broadened_agent_rejected_even_with_matching_digest(self):
        self.spec['agents']['node3']=self.spec['agents']['node2']; (self.root/'deploy-result').write_text(json.dumps(self.spec))
        digest=hashlib.sha256((self.root/'deploy-result').read_bytes()).hexdigest()
        self.assertNotEqual(self.run_phase('upload',EXPECTED_SPEC_SHA256=digest),0); self.assertEqual(self.calls(),'')
    def test_failed_push_fails_job(self):
        self.mock('nix','exit 23'); self.assertEqual(self.run_phase('upload'),23)
