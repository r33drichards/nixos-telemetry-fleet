import datetime as dt
import importlib.util
import pathlib
import unittest
from unittest import mock

spec=importlib.util.spec_from_file_location('auth',pathlib.Path(__file__).resolve().parents[1]/'scripts/image-auth-check.py')
auth=importlib.util.module_from_spec(spec);spec.loader.exec_module(auth)

class AudienceProbe(unittest.TestCase):
    def test_both_audiences_use_metadata_only_query(self):
        for name in ('storage','disk'):
            with mock.patch.object(auth.subprocess,'run',return_value=mock.Mock(returncode=0,stdout='{"expires_on":2000000000}')) as run:
                auth.check(name,'fixture-tenant',dt.datetime.fromtimestamp(1900000000,dt.timezone.utc))
            args=run.call_args.args[0]
            self.assertEqual(args[:3],['az','account','get-access-token'])
            self.assertEqual(args[args.index('--resource')+1],auth.AUDIENCES[name])
            self.assertEqual(args[args.index('--query')+1],'{expires_on:expires_on}')

    def test_failed_acquisition_never_echoes_raw_error(self):
        with mock.patch.object(auth.subprocess,'run',return_value=mock.Mock(returncode=1,stderr='SECRET')):
            with self.assertRaisesRegex(RuntimeError,'^TokenAcquisitionFailed$'):
                auth.check('disk','fixture',dt.datetime.now(dt.timezone.utc))

    def test_expired_metadata_fails(self):
        with mock.patch.object(auth.subprocess,'run',return_value=mock.Mock(returncode=0,stdout='{"expires_on":1}')):
            with self.assertRaisesRegex(RuntimeError,'TokenExpiryTooSoon'):
                auth.check('disk','fixture',dt.datetime.now(dt.timezone.utc))
