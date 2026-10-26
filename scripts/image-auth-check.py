#!/usr/bin/env python3
"""Read-only audience probe for the existing main-only fleet OIDC identity."""
import datetime as dt
import json
import os
import subprocess
import sys

AUDIENCES = {'storage': 'https://storage.azure.com/', 'disk': 'https://disk.azure.com/'}


def check(name, tenant, now):
    # Match AzureCLICredential's resource/tenant request. Query excludes token material.
    result = subprocess.run(['az', 'account', 'get-access-token', '--resource', AUDIENCES[name],
        '--tenant', tenant, '--query', '{expires_on:expires_on}', '--output', 'json', '--only-show-errors'],
        capture_output=True, text=True, timeout=120)
    if result.returncode:
        raise RuntimeError('TokenAcquisitionFailed')
    try:
        expires = int(json.loads(result.stdout)['expires_on'])
    except (ValueError, TypeError, KeyError):
        raise RuntimeError('ExpiryMetadataMissing') from None
    if expires <= now.timestamp() + 300:
        raise RuntimeError('TokenExpiryTooSoon')


def main():
    if os.environ.get('GITHUB_REF') != 'refs/heads/main' or os.environ.get('OIDC_CHECK_ENABLED') != 'explicitly-approved':
        raise RuntimeError('Require approved main OIDC environment')
    tenant = os.environ.get('AZURE_TENANT_ID', '')
    if not tenant:
        raise RuntimeError('TenantMissing')
    failed = False
    for name in AUDIENCES:
        try:
            check(name, tenant, dt.datetime.now(dt.timezone.utc))
            print(name + ': token acquisition succeeded; expiry exceeds five minutes')
        except Exception as error:
            code = str(error) if type(error) is RuntimeError and str(error) in ('TokenAcquisitionFailed', 'ExpiryMetadataMissing', 'TokenExpiryTooSoon') else 'ProbeExecutionFailed'
            print(name + ': ' + code, file=sys.stderr)
            failed = True
    return 1 if failed else 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception:
        print('Audience probe rejected; no cloud resource writes attempted', file=sys.stderr)
        sys.exit(1)
