import json, pathlib, unittest
ROOT = pathlib.Path(__file__).resolve().parents[1]
class Structure(unittest.TestCase):
    def test_four_locks_pin_same_external_revisions(self):
        locks=[json.loads(p.read_text()) for p in [ROOT/'flake.lock',*[ROOT/f'nodes/node{i}/flake.lock' for i in range(1,4)]]]
        # Compare full records by graph node, so distinct nixpkgs pins cannot
        # overwrite each other through a dictionary keyed only by repo name.
        github=lambda lock: {name:node['locked'] for name,node in lock['nodes'].items() if node.get('locked',{}).get('type')=='github'}
        root, *leaves = map(github, locks)
        self.assertTrue(all(p==leaves[0] for p in leaves))
        candidate=github(json.loads((ROOT/'candidates/hermes/flake.lock').read_text()))
        hermes={('hermes' if name=='hermes' else 'hermes-'+name):locked for name,locked in candidate.items()}
        self.assertFalse(set(leaves[0]) & set(hermes))
        self.assertEqual(root, {**leaves[0], **hermes})
        self.assertEqual(root['comin']['rev'],'1399adecc682e557bc3ee914d929f8e20391a148')
        self.assertEqual(root['hermes']['rev'],'05d7b5af1c42d524762c7ffce991c1fe1aa2adb1')
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
