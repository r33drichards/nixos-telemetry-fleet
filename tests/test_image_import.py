import copy
import datetime as dt
import hashlib
import importlib.util
import json
import pathlib
import unittest
import io
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / f'{name}.py')
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

recipe = module('prepare-image-import')
transport = module('transport-image')

class ImageImport(unittest.TestCase):
    def setUp(self):
        self.config = dict(source_revision=recipe.SOURCE_REVISION, location='westus3',
            resource_group='example-fleet', gallery_name='exampleGallery', version='1.0.0',
            subscription_id='00000000-0000-0000-0000-000000000000', setup_estimate_usd=0.2,
            monthly_ancillary_estimate_usd=0.86, cost_evidence='private-review', phase_b_scope_approval='private-review',
            image_definitions={'node2':'amd','node3':'arm'}, staging_disks={'node2':'stage-amd','node3':'stage-arm'})
        self.reports = {name: dict(source_revision=recipe.SOURCE_REVISION, system=system,
            virtual_bytes=8*1024**3, file_bytes=8*1024**3+512, sha256='a'*64,
            artifact_inspection_passed=True) for name,(system,_) in recipe.ARCHITECTURES.items()}

    def test_import_preparation_does_not_require_vm_access_or_boot_approval(self):
        plan = recipe.prepare(self.config, self.reports)
        self.assertFalse(plan['execute'])
        self.assertEqual(len(plan['nodes']), 2)
        for node in plan['nodes']:
            create = node['steps'][1]['argv']
            self.assertIn('AzureActiveDirectory', create)
            self.assertIn(str(8*1024**3+512), create)
            self.assertEqual(node['steps'][3]['argv'][-2:], ['--replication-mode', 'Full'])
            self.assertNotIn('listKeys', json.dumps(plan))

    def test_duplicate_destinations_rejected(self):
        self.config['staging_disks']['node3'] = 'stage-amd'
        with self.assertRaisesRegex(ValueError, 'distinct'):
            recipe.prepare(self.config, self.reports)

    def test_old_four_gib_report_rejected(self):
        self.reports['node2']['file_bytes'] = 4*1024**3+512
        with self.assertRaisesRegex(ValueError, '8-GiB'):
            recipe.prepare(self.config, self.reports)

    def test_budget_overages_rejected(self):
        for field,value in [('setup_estimate_usd',1.01), ('monthly_ancillary_estimate_usd',3.01)]:
            config = dict(self.config, **{field:value})
            with self.assertRaises(ValueError): recipe.prepare(config, self.reports)

    def transport_plan(self):
        return dict(source_revision=recipe.SOURCE_REVISION, storage_account='exampleprivate',
            container='image-transport', prefix='approved-import', setup_estimate_usd=0.2,
            monthly_ancillary_estimate_usd=0.86, expires_at='2026-10-26T01:00:00Z',
            approval_reference='private-review', subscription_id=self.config['subscription_id'], resource_group='example-fleet')

    def validate(self, plan, digest=None, now=None):
        raw=json.dumps(plan).encode()
        return transport.validate_plan(raw, digest or hashlib.sha256(raw).hexdigest(), now or dt.datetime(2026,10,25,23,tzinfo=dt.timezone.utc))

    def test_transport_requires_exact_payload_hash(self):
        self.validate(self.transport_plan())
        with self.assertRaisesRegex(ValueError, 'checksum'):
            self.validate(self.transport_plan(), '0'*64)

    def test_transport_expired_or_wrong_source_rejected(self):
        with self.assertRaisesRegex(ValueError, 'expire'):
            self.validate(self.transport_plan(), now=dt.datetime(2026,10,27,tzinfo=dt.timezone.utc))
        plan=self.transport_plan(); plan['source_revision']='0'*40
        with self.assertRaisesRegex(ValueError, 'qualified'):
            self.validate(plan)

    def test_destination_injection_rejected(self):
        plan=self.transport_plan(); plan['prefix']='../escape'
        with self.assertRaises(ValueError): self.validate(plan)

    def test_existing_blob_is_never_overwritten(self):
        plan=self.transport_plan()
        image=mock.Mock()
        image.stat.return_value.st_size=8*1024**3+512
        image.open.return_value=io.BytesIO(b'fixture-bytes')
        report=dict(revision=recipe.SOURCE_REVISION, hostname='node2', system='x86_64-linux', deploymentApproved=False)
        responses=[{'id':plan['subscription_id']}, {'allowBlobPublicAccess':False, 'allowSharedKeyAccess':False}, {'properties':{'publicAccess':None}}, {'exists':True}]
        with mock.patch.object(transport, 'azure', side_effect=responses) as az:
            with self.assertRaisesRegex(ValueError, 'exists'):
                transport.upload(plan, 'node2', image, report)
            self.assertFalse(any(call.args[0][:3]==['storage','blob','upload'] for call in az.call_args_list))

    def test_transport_rejects_shared_key_enabled_account(self):
        plan=self.transport_plan()
        image=mock.Mock()
        image.stat.return_value.st_size=8*1024**3+512
        report=dict(revision=recipe.SOURCE_REVISION, hostname='node2', system='x86_64-linux', deploymentApproved=False)
        with mock.patch.object(transport, 'azure', side_effect=[{'id':plan['subscription_id']}, {'allowBlobPublicAccess':False, 'allowSharedKeyAccess':True}]) as az:
            with self.assertRaisesRegex(ValueError, 'shared-key'):
                transport.upload(plan, 'node2', image, report)
            self.assertEqual(az.call_count, 2)
