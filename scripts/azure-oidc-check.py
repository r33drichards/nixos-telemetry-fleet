#!/usr/bin/env python3
"""Verify the selected account and read the approved fleet RG; never print inventory."""
import json
import os
import subprocess


def check(env, query):
    if env.get('GITHUB_REF') != 'refs/heads/main' or env.get('GITHUB_REPOSITORY') != 'r33drichards/nixos-telemetry-fleet':
        raise ValueError('Only the approved repository main branch may check federation')
    if env.get('OIDC_CHECK_ENABLED') != 'explicitly-approved':
        raise ValueError('OIDC check setup is not approved')
    required = ['AZURE_SUBSCRIPTION_ID', 'AZURE_TENANT_ID', 'FLEET_RESOURCE_GROUP']
    if not all(env.get(key) for key in required):
        raise ValueError('Expected account and fleet scope are required')
    account = query(['account', 'show'])
    if account.get('id', '').lower() != env['AZURE_SUBSCRIPTION_ID'].lower() or account.get('tenantId', '').lower() != env['AZURE_TENANT_ID'].lower():
        raise ValueError('Unexpected Azure account')
    group = query(['group', 'show', '--name', env['FLEET_RESOURCE_GROUP'], '--subscription', env['AZURE_SUBSCRIPTION_ID']])
    expected = '/subscriptions/' + env['AZURE_SUBSCRIPTION_ID'] + '/resourceGroups/' + env['FLEET_RESOURCE_GROUP']
    if group.get('id', '').lower() != expected.lower():
        raise ValueError('Unexpected fleet resource group')


def query(args):
    result = subprocess.run(['az', *args, '--output', 'json', '--only-show-errors'], capture_output=True, text=True, timeout=60, check=True)
    return json.loads(result.stdout)


if __name__ == '__main__':
    try:
        check(os.environ, query)
    except Exception:
        raise SystemExit('OIDC read-only check failed; inspect through approved private diagnostics.')
    print('PASS: expected Azure account and approved fleet RG are readable; no resources changed.')
