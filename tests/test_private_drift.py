import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).parents[1]
s = importlib.util.spec_from_file_location('private_drift', ROOT/'scripts/private-drift-diagnostic.py')
m = importlib.util.module_from_spec(s); s.loader.exec_module(m)

class PrivateDrift(unittest.TestCase):
    def setUp(self):
        self.env = dict(GITHUB_REF='refs/heads/main', GITHUB_REPOSITORY='r33drichards/nixos-telemetry-fleet', TF_ROOT='terraform/amd-canary', OPERATION='plan', RETAIN_DRIFT_DIAGNOSTIC='true', DRIFT_PRIVATE_REVIEW_READY='explicitly-confirmed', GITHUB_SHA='a'*40, GITHUB_RUN_ID='123', GITHUB_RUN_ATTEMPT='1')
        self.schema = {'provider_schemas': {m.PROVIDER: {'resource_schemas': {'azurerm_network_interface': {'block': {'attributes': {'tags': {'optional':True}, 'virtual_machine_id': {'computed':True}, 'dns_servers':{'optional':True}, 'private_ip_addresses':{'computed':True}}}}}}}}
        self.entry = {'address':'azurerm_network_interface.node2[0]', 'type':'azurerm_network_interface', 'provider_name':m.PROVIDER, 'change': {'actions':['update'], 'before': {'tags':None,'dns_servers':None,'virtual_machine_id':None,'private_ip_addresses':[]}, 'after': {'tags':{},'dns_servers':[],'virtual_machine_id':'PRIVATE-SENTINEL','private_ip_addresses':['PRIVATE-SENTINEL']}}}
        self.plan = {'terraform_version':'1.14.0', 'variables':{'secret':'NEVER-COPY'}, 'resource_drift':[self.entry]}
    def test_complete_schema_names_and_exact_private_values(self):
        private, public = m.compare(self.plan,self.schema,self.env)
        self.assertEqual(private['resource_drift'],self.plan['resource_drift'])
        self.assertNotIn('variables',private)
        self.assertNotIn('PRIVATE-SENTINEL',json.dumps(public))
        fields = {f['field']: f for f in public['resources'][0]['fields']}
        self.assertEqual(set(fields),set(self.entry['change']['after']))
        self.assertEqual(fields['tags']['structure'],'null-to-empty')
        self.assertTrue(fields['tags']['configurable']); self.assertFalse(fields['tags']['computed'])
        self.assertTrue(fields['virtual_machine_id']['computed'])
    def test_gates_and_bindings(self):
        for key in self.env:
            with self.subTest(key=key), self.assertRaises(ValueError):
                m.compare(self.plan,self.schema,{**self.env,key:''})
    def test_unknown_plan_field_is_never_printed(self):
        self.entry['change']['after']['PRIVATE-SENTINEL'] = 'value'
        with self.assertRaises(ValueError): m.compare(self.plan,self.schema,self.env)
    def test_nested_map_keys_are_not_field_names(self):
        self.entry['change']['after']['tags'] = {'PRIVATE-SENTINEL':'secret'}
        _, public = m.compare(self.plan,self.schema,self.env)
        self.assertNotIn('PRIVATE-SENTINEL',json.dumps(public))
    def test_unknown_resource_duplicate_and_wrong_action_fail(self):
        for mutation in ('resource','duplicate','action','provider'):
            p=copy.deepcopy(self.plan)
            if mutation=='resource': p['resource_drift'][0]['address']='unknown'
            if mutation=='duplicate': p['resource_drift']*=2
            if mutation=='action': p['resource_drift'][0]['change']['actions']=['delete','create']
            if mutation=='provider': p['resource_drift'][0]['provider_name']='unknown'
            with self.subTest(mutation=mutation), self.assertRaises(ValueError): m.compare(p,self.schema,self.env)
    def test_presence_not_collapsed_into_null(self):
        del self.entry['change']['before']['tags']
        _,public=m.compare(self.plan,self.schema,self.env)
        self.assertEqual(next(f for f in public['resources'][0]['fields'] if f['field']=='tags')['structure'],'presence-change')
    def test_no_apply_compatible_upload_and_guard_still_follows(self):
        script=(ROOT/'scripts/cloud-terraform.sh').read_text()
        start=script.index('    if [ "${RETAIN_DRIFT_DIAGNOSTIC')
        end=script.index('    python3 "$preflight" --check-plan-json',start)
        added=script[start:end]
        self.assertIn('diagnostics/drift/$GITHUB_RUN_ID/$GITHUB_RUN_ATTEMPT',added)
        self.assertIn('for item in comparison.json manifest.json',added)
        self.assertNotIn('terraform apply',added)
        self.assertIn('python3 scripts/review-canary-plan.py',script[end:])

if __name__ == '__main__': unittest.main()
