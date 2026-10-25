#!/usr/bin/env python3
"""Gated private block-blob transport; no account keys, disk or VM creation."""
import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys

SOURCE_REVISION = 'ba51125b3d367b8326b357023a5ad5812239b7a9'


def validate_plan(raw, expected_hash, now):
    if not re.fullmatch(r'[0-9a-f]{64}', expected_hash) or hashlib.sha256(raw).hexdigest() != expected_hash:
        raise ValueError('Private transport plan checksum mismatch')
    p = json.loads(raw)
    if p.get('source_revision') != SOURCE_REVISION:
        raise ValueError('Only the CI-qualified source revision may be rebuilt')
    for key, pattern in [('storage_account', r'[a-z0-9]{3,24}'), ('container', r'[a-z0-9][a-z0-9-]{1,61}[a-z0-9]'), ('prefix', r'[A-Za-z0-9/_-]{1,120}')]:
        if not re.fullmatch(pattern, p.get(key, '')) or '..' in p[key]:
            raise ValueError('Explicit safe private blob destination required')
    if p.get('setup_estimate_usd', -1) < 0 or p['setup_estimate_usd'] > 1 or not 0 <= p.get('monthly_ancillary_estimate_usd', -1) <= 3:
        raise ValueError('Cost estimates exceed the approved envelope')
    expires = dt.datetime.fromisoformat(p['expires_at'].replace('Z', '+00:00'))
    if expires.tzinfo is None or not now < expires <= now + dt.timedelta(hours=24):
        raise ValueError('Approval must expire within 24 hours')
    if not p.get('approval_reference') or not p.get('subscription_id') or not p.get('resource_group'):
        raise ValueError('Exact scope and approval reference required')
    if p.get('shared_key_disabled') is not True or p.get('anonymous_blob_disabled') is not True or not p.get('bootstrap_account_evidence'):
        raise ValueError('Pinned bootstrap evidence must attest locked private account settings')
    return p


def azure(args):
    # Never stream CLI errors, SAS URLs, identifiers or private destination details.
    r = subprocess.run(['az', *args, '--only-show-errors', '--output', 'json'], capture_output=True, text=True, timeout=3600)
    if r.returncode:
        raise RuntimeError('Azure operation failed; inspect private diagnostics before any retry')
    return json.loads(r.stdout or '{}')


def upload(p, node, vhd, report):
    expected = {'node2': 'x86_64-linux', 'node3': 'aarch64-linux'}[node]
    if report.get('revision') != SOURCE_REVISION or report.get('hostname') != node or report.get('system') != expected or report.get('deploymentApproved') is not False:
        raise ValueError('Image metadata mismatch')
    if vhd.stat().st_size != 8 * 1024**3 + 512:
        raise ValueError('Expected 8-GiB fixed VHD plus footer')
    account = azure(['account', 'show'])
    if account.get('id', '').lower() != p['subscription_id'].lower():
        raise ValueError('Wrong Azure subscription')
    # Account settings are pinned in the privately approved bootstrap manifest.
    # This identity intentionally has no storage-account ARM read permission.
    common = ['--account-name', p['storage_account'], '--container-name', p['container'], '--auth-mode', 'login']
    container = azure(['storage', 'container', 'show', '--account-name', p['storage_account'], '--name', p['container'], '--auth-mode', 'login'])
    properties = container.get('properties', {})
    if 'publicAccess' not in properties or properties['publicAccess'] not in (None, 'None'):
        raise ValueError('Container must be private')
    with vhd.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    name = f"{p['prefix'].rstrip('/')}/{SOURCE_REVISION}/{node}.vhd"
    if azure(['storage', 'blob', 'exists', *common, '--name', name]).get('exists') is not False:
        raise ValueError('Blob exists or existence uncertain; inspect before retry')
    azure(['storage', 'blob', 'upload', *common, '--name', name, '--file', str(vhd), '--type', 'block', '--overwrite', 'false', '--metadata', f'source_revision={SOURCE_REVISION}', f'sha256={digest}', f'node={node}', 'artifact_inspection=passed'])
    result = azure(['storage', 'blob', 'show', *common, '--name', name])
    if result.get('properties', {}).get('contentLength') != vhd.stat().st_size or result.get('metadata', {}).get('sha256') != digest:
        raise ValueError('Uploaded length/provenance verification failed; do not retry blindly')
    return digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plan')
    parser.add_argument('--node', choices=['node2', 'node3'])
    parser.add_argument('--vhd')
    parser.add_argument('--report')
    parser.add_argument('--upload', action='store_true')
    args = parser.parse_args()
    if os.environ.get('GITHUB_REF') != 'refs/heads/main' or os.environ.get('IMAGE_TRANSPORT_ENABLED') != 'explicitly-approved':
        raise ValueError('Require approved main workflow/environment')
    p = validate_plan(pathlib.Path(args.plan).read_bytes(), os.environ.get('APPROVED_IMAGE_TRANSPORT_PLAN_SHA256', ''), dt.datetime.now(dt.timezone.utc))
    if args.upload:
        digest = upload(p, args.node, pathlib.Path(args.vhd), json.loads(pathlib.Path(args.report).read_text()))
        print('Private image transport verified; SHA256=' + digest)
    else:
        print('Private transport plan validated; no cloud operation performed')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        print('Image transport failed closed. Inspect current private state before retry; no automatic cleanup or overwrite.', file=sys.stderr)
        sys.exit(1)
