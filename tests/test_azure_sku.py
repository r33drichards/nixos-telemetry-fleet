import importlib.util
import pathlib
import unittest
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
