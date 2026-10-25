import importlib.util
import pathlib
import unittest
import json
import tempfile
from unittest import mock
spec = importlib.util.spec_from_file_location('sku', pathlib.Path(__file__).resolve().parents[1] / 'scripts/azure-sku-preflight.py')
sku = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sku)

class AzureSku(unittest.TestCase):
    def setUp(self):
        self.node = {'size': 'Example', 'location': 'example-region', 'architecture': 'x86_64'}
        self.record = {'name': 'Example', 'resourceType': 'virtualMachines', 'locations': ['example-region'],
                       'locationInfo': [{'location': 'example-region', 'zones': ['1', '2', '3']}],
                       'capabilities': [{'name': 'TrustedLaunchDisabled', 'value': 'False'},
                                        {'name': 'HyperVGenerations', 'value': 'V1,V2'},
                                        {'name': 'CpuArchitectureType', 'value': 'x64'}], 'restrictions': []}

    def test_supported(self):
        sku.validate(self.node, [self.record])

    def test_location_restricted(self):
        self.record['restrictions'] = [{'type': 'Location', 'values': ['example-region']}]
        with self.assertRaisesRegex(ValueError, 'restricted'):
            sku.validate(self.node, [self.record])

    def test_trusted_launch_disabled(self):
        self.record['capabilities'][0]['value'] = 'True'
        with self.assertRaisesRegex(ValueError, 'Trusted Launch'):
            sku.validate(self.node, [self.record])

    def test_unknown_security_capability(self):
        self.record['capabilities'].pop(0)
        with self.assertRaisesRegex(ValueError, 'unverified'):
            sku.validate(self.node, [self.record])

    def test_zone_restriction_does_not_block_regional_vm(self):
        self.record['restrictions'] = [{'type': 'Zone', 'restrictionInfo': {'locations': ['example-region'], 'zones': ['3']}}]
        sku.validate(self.node, [self.record])
        self.node['zone'] = '3'
        with self.assertRaisesRegex(ValueError, 'restricted'):
            sku.validate(self.node, [self.record])

    def test_architecture_mismatch(self):
        self.node['architecture'] = 'aarch64'
        with self.assertRaisesRegex(ValueError, 'architecture'):
            sku.validate(self.node, [self.record])

    def test_saved_plan_cli_queries_both_nodes(self):
        nodes = {name: dict(self.node, size=name, sku_available=True,
                           trusted_launch_supported=True) for name in ['ExampleA', 'ExampleB']}
        records = [dict(self.record, name=name) for name in nodes]
        plan = {'variables': {'enabled': {'value': True}, 'nodes': {'value': nodes}}}
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / 'plan.json'
            path.write_text(json.dumps(plan))
            with mock.patch.object(sku.sys, 'argv', ['preflight', '--plan-json', str(path)]), \
                 mock.patch.object(sku.subprocess, 'run', return_value=mock.Mock(
                     returncode=0, stdout=json.dumps(records))) as query, \
                 mock.patch('builtins.print'):
                sku.main()
            self.assertEqual(query.call_count, 2)
            for call in query.call_args_list:
                self.assertEqual(call.args[0][:3], ['az', 'vm', 'list-skus'])

    def test_missing_plan_filename_fails_without_azure_query(self):
        with mock.patch.object(sku.sys, 'argv', ['preflight', '--plan-json']), \
             mock.patch.object(sku.subprocess, 'run') as query:
            with self.assertRaisesRegex(ValueError, 'saved plan JSON required'):
                sku.main()
            query.assert_not_called()
