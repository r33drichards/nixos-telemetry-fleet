import ast
import importlib.util
import json
from pathlib import Path
import hashlib
import unittest

path = Path(__file__).parents[1]/'scripts/review-canary-plan.py'
spec = importlib.util.spec_from_file_location('review', path)
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

class DriftTests(unittest.TestCase):
    def test_only_allowlisted_names(self):
        marker = 'PRIVATE-SENTINEL'
        entry = {'address':'azurerm_linux_virtual_machine.node2[0]', 'change': {'actions':['update'], 'before': {'tags':{},marker:0}, 'after': {'tags': {marker:marker}, marker:marker}}}
        result = m.safe_drift({'resource_drift':[entry]})
        self.assertEqual(result['known'][0]['changed_fields'],['tags'])
        self.assertTrue(result['known'][0]['unrecognized_fields_changed'])
        self.assertNotIn(marker,json.dumps(result))
    def test_unknown_address_and_bounded_output(self):
        result = m.safe_drift({'resource_drift':[{'address':'PRIVATE-SENTINEL'}]*40})
        self.assertTrue(result['truncated']); self.assertEqual(result['count'],40)
        self.assertNotIn('PRIVATE-SENTINEL',json.dumps(result))
    def test_malformed_or_missing(self):
        for v in (None,{},'private'):
            self.assertEqual(m.safe_drift({'resource_drift':v}), {'schema':'invalid'})
        self.assertEqual(m.safe_drift({})['count'],0)
    def test_review_guard_unchanged(self):
        # Reviewed main a2544d3: preserve the complete decision function.
        tree = ast.parse(path.read_text())
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'review')
        digest = hashlib.sha256(ast.dump(node).encode()).hexdigest()
        self.assertEqual(digest, '9b1008cd8cc148afa7391d41b087a96f82f266a6af254b665c93cb974ee22db5')


if __name__ == '__main__': unittest.main()
