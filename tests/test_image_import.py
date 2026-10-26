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
importer = module('import-image')

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
            approval_reference='private-review', shared_key_disabled=True, anonymous_blob_disabled=True, bootstrap_account_evidence='private-bootstrap-review', subscription_id=self.config['subscription_id'], resource_group='example-fleet')

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
        responses=[{'id':plan['subscription_id']}, {'properties':{'publicAccess':None}}, {'exists':True}]
        with mock.patch.object(transport, 'azure', side_effect=responses) as az:
            with self.assertRaisesRegex(ValueError, 'exists'):
                transport.upload(plan, 'node2', image, report)
            self.assertFalse(any(call.args[0][:3]==['storage','blob','upload'] for call in az.call_args_list))
            self.assertFalse(any(call.args[0][:2]==['storage','account'] for call in az.call_args_list))

    def test_transport_rejects_unverified_account_manifest(self):
        plan=self.transport_plan(); plan['shared_key_disabled']=False
        with self.assertRaisesRegex(ValueError, 'bootstrap evidence'):
            self.validate(plan)

    def import_case(self, failure=None):
        plan={**self.config, **self.transport_plan(), 'artifact_reports':copy.deepcopy(self.reports)}
        node='node2'; calls=[]
        version_id=recipe.prepare(plan, self.reports)['nodes'][0]['image_version_id']
        def az(args):
            calls.append(args)
            cmd=tuple(args[:3])
            if args[:2]==['account','show']: return {'id':plan['subscription_id'], 'tenantId':'example-tenant'}
            if cmd==('sig','image-definition','show'): return dict(architecture='x64',hyperVGeneration='V2',osType='Linux',osState='Generalized')
            if args[:2]==['disk','list'] or cmd==('sig','image-version','list'): return []
            if cmd==('storage','container','show'): return {'properties':{'publicAccess':None}}
            if cmd==('storage','blob','show'): return {'metadata':{}}
            if args[:2]==['disk','grant-access']: return {'accessSas':'https://example.blob.core.windows.net/upload'}
            if args[:2]==['disk','show']: return dict(provisioningState='Succeeded',diskState='Unattached')
            if cmd==('sig','image-version','show'): return {'id':version_id,'tags':{'sha256':'a'*64},'provisioningState':'Succeeded','replicationStatus':{'aggregatedState':'Failed' if failure=='replication' else 'Completed'}}
            if cmd==('storage','blob','exists'): return {'exists':False}
            return {}
        with mock.patch.object(importer,'azure',side_effect=az), mock.patch.object(importer,'verify_download',return_value=self.reports[node]), mock.patch.object(importer,'copy_to_disk',side_effect=RuntimeError('transfer failed') if failure=='transfer' else None), mock.patch('builtins.print'):
            import tempfile
            with tempfile.TemporaryDirectory() as directory:
                if failure:
                    with self.assertRaises((ValueError,RuntimeError)): importer.execute(plan,node,pathlib.Path(directory))
                else:
                    importer.execute(plan,node,pathlib.Path(directory))
        return calls

    def test_import_revokes_upload_then_cleans_only_after_replication(self):
        calls=self.import_case()
        cmds=[tuple(a[:3]) for a in calls]
        revoke=next(i for i,a in enumerate(calls) if a[:2]==['disk','revoke-access'])
        replicate=cmds.index(('sig','image-version','show'))
        delete=next(i for i,a in enumerate(calls) if a[:2]==['disk','delete'])
        self.assertLess(revoke,replicate); self.assertLess(replicate,delete)
        self.assertFalse(any('role' in a or 'listKeys' in a or 'vm' in a for a in calls))
        self.assertIn(('storage','blob','delete'),cmds)

    def test_transfer_failure_revokes_url_without_deleting_evidence(self):
        calls=self.import_case('transfer')
        self.assertTrue(any(a[:2]==['disk','revoke-access'] for a in calls))
        self.assertFalse(any('delete' in a or a[:3]==['sig','image-version','create'] for a in calls))

    def test_replication_failure_preserves_staging_and_blob(self):
        calls=self.import_case('replication')
        self.assertFalse(any('delete' in a for a in calls))

    def test_api_failure_reports_only_allowlisted_operation_and_code(self):
        result=mock.Mock(returncode=1, stdout='', stderr='ERROR: (AuthorizationFailed) https://private/?sig=SECRET token=SECRET')
        with mock.patch.object(importer.subprocess, 'run', return_value=result), mock.patch('sys.stderr', new_callable=io.StringIO) as output:
            with self.assertRaises(importer.SafeImportError) as raised:
                importer.azure(['disk','create','--name','private-name'])
        self.assertEqual(str(raised.exception), 'disk.create: AuthorizationFailed')
        self.assertNotIn('SECRET', output.getvalue())
        self.assertNotIn('private-name', output.getvalue())

    def test_unknown_api_error_is_not_echoed(self):
        result=mock.Mock(returncode=1, stdout='', stderr='sensitive raw output')
        with mock.patch.object(importer.subprocess, 'run', return_value=result):
            with self.assertRaisesRegex(importer.SafeImportError, '^disk.create: UnclassifiedCliError$'):
                importer.azure(['disk','create'])

    def test_transfer_and_revoke_failures_are_both_reported_without_secrets(self):
        def az(args):
            if args[1]=='grant-access': return {'accessSas':'https://example.blob.core.windows.net/?sig=SECRET'}
            raise importer.SafeImportError('disk.revoke-access: AuthorizationFailed')
        with mock.patch.object(importer,'azure',side_effect=az), mock.patch.object(importer,'copy_to_disk',side_effect=RuntimeError('SECRET')), mock.patch('sys.stderr',new_callable=io.StringIO) as output:
            import tempfile
            with tempfile.TemporaryDirectory() as directory:
                with self.assertRaises(importer.SafeImportError):
                    importer.upload_and_revoke(pathlib.Path('fixture'),pathlib.Path(directory),'tenant',[],'disk')
        self.assertIn('Upload phase failed: UnclassifiedExecutionError',output.getvalue())
        self.assertIn('Upload access cleanup UNVERIFIED: disk.revoke-access: AuthorizationFailed',output.getvalue())
        self.assertNotIn('SECRET',output.getvalue())

    def test_successful_revoke_command_requires_inactive_disk_readback(self):
        def az(args):
            if args[1]=='grant-access': return {'accessSas':'https://example.blob.core.windows.net/upload'}
            if args[1]=='show': return {'diskState':'ActiveUpload'}
            return {}
        with mock.patch.object(importer,'azure',side_effect=az), mock.patch.object(importer,'copy_to_disk'), mock.patch('sys.stderr',new_callable=io.StringIO):
            import tempfile
            with tempfile.TemporaryDirectory() as directory:
                with self.assertRaisesRegex(importer.SafeImportError,'UploadAccessStillActiveOrUnknown'):
                    importer.upload_and_revoke(pathlib.Path('fixture'),pathlib.Path(directory),'tenant',[],'disk')

    def test_missing_azcopy_is_reported_without_upload_url(self):
        with mock.patch.object(importer.subprocess,'run',side_effect=FileNotFoundError('SECRET')):
            with self.assertRaisesRegex(importer.SafeImportError,'^azcopy.transfer: ExecutableMissing$'):
                importer.copy_to_disk(pathlib.Path('fixture'),'https://example.blob.core.windows.net/?sig=SECRET',pathlib.Path('/tmp'),'tenant')

    def test_partial_transfer_failure_is_not_treated_as_success(self):
        result=mock.Mock(returncode=1,stdout='SECRET',stderr='SECRET')
        with mock.patch.object(importer.subprocess,'run',return_value=result):
            with self.assertRaisesRegex(importer.SafeImportError,'^azcopy.transfer: TransferFailed$'):
                importer.copy_to_disk(pathlib.Path('fixture'),'https://example.blob.core.windows.net/?sig=SECRET',pathlib.Path('/tmp'),'tenant')
