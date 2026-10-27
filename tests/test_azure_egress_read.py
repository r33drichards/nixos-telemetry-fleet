import importlib.util
import json
from pathlib import Path
import unittest

s = importlib.util.spec_from_file_location('egress', Path(__file__).parents[1]/'scripts/azure-egress-read.py')
m = importlib.util.module_from_spec(s); s.loader.exec_module(m)

class ReadTests(unittest.TestCase):
    def setUp(self):
        self.env = dict(GITHUB_REF='refs/heads/main', GITHUB_REPOSITORY='r33drichards/nixos-telemetry-fleet', OIDC_CHECK_ENABLED='explicitly-approved', FLEET_RESOURCE_GROUP='fixture', AZURE_SUBSCRIPTION_ID='fixture')
    def test_three_scoped_shows_and_sanitized_summary(self):
        calls = []
        responses = [{'defaultOutboundAccess': False, 'addressPrefixes': ['PRIVATE-SENTINEL']}, {'defaultOutboundConnectivityEnabled': True, 'networkSecurityGroup': {'id':'fixture-nsg'}}, {'id':'fixture-nsg', 'securityRules':[{'direction':'Outbound','access':'Deny','name':'PRIVATE-SENTINEL'}], 'defaultSecurityRules':[{'direction':'Outbound','access':'Allow','destinationAddressPrefix':'Internet'}]}]
        def query(args): calls.append(args); return responses[len(calls)-1]
        result = m.inspect(self.env, query)
        self.assertEqual(len(calls),3)
        for args in calls:
            self.assertIn('show', args); self.assertIn('--resource-group',args); self.assertIn('--subscription',args)
        self.assertEqual(result['subnet_default_outbound_access'],'false')
        self.assertEqual(result['custom_outbound_deny_count'],1)
        self.assertNotIn('PRIVATE-SENTINEL',json.dumps(result))
    def test_missing_properties_unknown_not_false(self):
        result = m.inspect(self.env, lambda _: {})
        self.assertEqual(result['subnet_default_outbound_access'],'unknown')
        self.assertEqual(result['nic_default_outbound_allocated'],'unknown')
        self.assertFalse(result['nic_expected_nsg_attached'])
    def test_rejects_gates_before_reads(self):
        for key in ('GITHUB_REF','GITHUB_REPOSITORY','OIDC_CHECK_ENABLED','FLEET_RESOURCE_GROUP','AZURE_SUBSCRIPTION_ID'):
            with self.subTest(key=key), self.assertRaises(ValueError):
                m.inspect({**self.env,key:''},lambda _: self.fail('Unexpected Azure call'))
    def test_schema_failure(self):
        with self.assertRaises(ValueError): m.inspect(self.env,lambda _: {'securityRules': 'invalid'})

if __name__ == '__main__': unittest.main()
