import importlib.util
import json
from pathlib import Path
import unittest
spec = importlib.util.spec_from_file_location('review_diagnostics', Path(__file__).parents[1] / 'scripts/review-canary-plan.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
class DiagnosticsTests(unittest.TestCase):
    def test_flags_and_noops(self):
        p = {'variables': {'shared_default_outbound_ipv4': {'value': False}, 'approval': {'value': {'shared_default_outbound_ipv4': False}}}, 'resource_changes': [{'address': 'terraform_data.approval[0]', 'change': {'actions': ['no-op'], 'before': {}, 'after': {}}}]}
        d = m.safe_diagnostics(p, ValueError('secret'))
        self.assertIs(d['trial_enabled'], False)
        self.assertIs(d['trial_approved'], False)
        self.assertEqual(d['actions']['no-op'], 1)
    def test_values_and_unknown_paths_never_leak(self):
        secret = 'SENSITIVE_TOKEN_KEY_CUSTOMDATA'
        p = {'variables': {'shared_default_outbound_ipv4': {'value': secret}, 'approval': {'value': {'shared_default_outbound_ipv4': secret}}}, 'resource_changes': [{'address': secret, 'change': {'actions': [secret]}}, {'address': 'azurerm_subnet.fleet[0]', 'change': {'actions': ['update'], 'before': {'custom_data': secret, secret: secret}, 'after': {'custom_data': 'different'}}}]}
        text = json.dumps(m.safe_diagnostics(p, KeyError(secret)))
        self.assertNotIn(secret, text)
        self.assertIn('custom_data', text)
        self.assertIn('missing-or-invalid', text)
    def test_malformed_inputs(self):
        for p in (None, [], {'variables': []}, {'resource_changes': [None, {'change': None}]}):
            m.safe_diagnostics(p, TypeError('private'))
