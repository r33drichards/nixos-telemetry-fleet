import importlib.util
import pathlib
import unittest

spec = importlib.util.spec_from_file_location('oidc_check', pathlib.Path(__file__).resolve().parents[1] / 'scripts/azure-oidc-check.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class OidcCheck(unittest.TestCase):
    def env(self):
        return dict(GITHUB_REF='refs/heads/main', GITHUB_REPOSITORY='r33drichards/nixos-telemetry-fleet', OIDC_CHECK_ENABLED='explicitly-approved', AZURE_SUBSCRIPTION_ID='test-subscription', AZURE_TENANT_ID='test-tenant', FLEET_RESOURCE_GROUP='test-fleet')

    def test_reads_only_expected_scope(self):
        calls = []
        def query(args):
            calls.append(args)
            return {'id': 'test-subscription', 'tenantId': 'test-tenant'} if args == ['account', 'show'] else {'id': '/subscriptions/test-subscription/resourceGroups/test-fleet'}
        module.check(self.env(), query)
        self.assertEqual(calls, [['account', 'show'], ['group', 'show', '--name', 'test-fleet', '--subscription', 'test-subscription']])

    def test_branch_and_setup_fail_before_query(self):
        for key, value in [('GITHUB_REF', 'refs/pull/1/merge'), ('OIDC_CHECK_ENABLED', ''), ('GITHUB_REPOSITORY', 'someone/fork')]:
            env = self.env(); env[key] = value
            with self.assertRaises(ValueError):
                module.check(env, lambda args: self.fail('Must not query Azure'))

    def test_wrong_account_stops_before_group_read(self):
        with self.assertRaises(ValueError):
            module.check(self.env(), lambda args: {'id': 'wrong', 'tenantId': 'test-tenant'})

    def test_wrong_resource_group_fails(self):
        with self.assertRaises(ValueError):
            module.check(self.env(), lambda args: {'id': 'test-subscription', 'tenantId': 'test-tenant'} if args == ['account', 'show'] else {'id': '/subscriptions/test-subscription/resourceGroups/unrelated'})
