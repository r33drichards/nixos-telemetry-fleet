import json, pathlib, unittest
ROOT = pathlib.Path(__file__).resolve().parents[1]
class Structure(unittest.TestCase):
    def test_four_locks_pin_same_external_revisions(self):
        locks=[json.loads(p.read_text()) for p in [ROOT/'flake.lock',*[ROOT/f'nodes/node{i}/flake.lock' for i in range(1,4)]]]
        pins=[{n['locked']['repo']:n['locked']['rev'] for n in lock['nodes'].values() if n.get('locked',{}).get('type')=='github'} for lock in locks]
        self.assertTrue(all(p==pins[0] for p in pins))
        self.assertEqual(pins[0]['comin'],'1399adecc682e557bc3ee914d929f8e20391a148')
    def test_three_leaf_configs_disabled(self):
        for i in range(1,4):
            self.assertIn(f'nixosConfigurations.node{i}',(ROOT/f'nodes/node{i}/flake.nix').read_text())
            self.assertIn('lab.enable = false;', (ROOT/f'nodes/node{i}/deployment.nix').read_text())
    def test_dashboard_metrics(self):
        d=json.loads((ROOT/'common/modules/dashboards/nodes.json').read_text())
        self.assertEqual(d['uid'],'three-nodes')
        self.assertEqual(len(d['panels']),4)
        self.assertTrue(all(p['datasource']['uid']=='prometheus' for p in d['panels']))
    def test_no_secret_or_state_files_tracked(self):
        import subprocess
        paths=subprocess.check_output(['git','ls-files'],cwd=ROOT,text=True).splitlines()
        self.assertFalse(any(p.startswith('.local/') or p.endswith(('.tfstate','.pem','.key','.age')) or '.sops.' in p or p.startswith('secrets/') for p in paths))
