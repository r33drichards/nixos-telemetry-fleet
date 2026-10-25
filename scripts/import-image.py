#!/usr/bin/env python3
"""Approved AAD disk/gallery import with staging cleanup; never changes IAM or VMs."""
import argparse
import datetime as dt
import importlib.util
import json
import os
import pathlib
import subprocess
import signal
import sys
import tempfile
import time
from urllib.parse import urlparse

HERE = pathlib.Path(__file__).resolve().parent

def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

transport = load('transport-image')
recipe = load('prepare-image-import')
azure = transport.azure


def verify_download(path, metadata, node):
    if metadata.get('source_revision') != recipe.SOURCE_REVISION or metadata.get('node') != node or metadata.get('artifact_inspection') != 'passed':
        raise ValueError('Require trusted rebuild/inspection provenance')
    result = subprocess.run([sys.executable, str(HERE / 'validate-vhd.py'), str(path)], capture_output=True, text=True, check=True)
    report = json.loads(result.stdout)
    if report['sha256'] != metadata.get('sha256'):
        raise ValueError('Downloaded VHD checksum mismatch')
    return dict(source_revision=recipe.SOURCE_REVISION, system=recipe.ARCHITECTURES[node][0],
        virtual_bytes=report['virtual_bytes'], file_bytes=path.stat().st_size,
        sha256=report['sha256'], artifact_inspection_passed=True)


def copy_to_disk(path, url, private_dir, tenant):
    parsed = urlparse(url)
    if parsed.scheme != 'https' or not parsed.hostname or not parsed.hostname.endswith(('.blob.core.windows.net', '.blob.storage.azure.net')):
        raise ValueError('Unexpected managed-disk upload endpoint')
    env = dict(os.environ, AZCOPY_AUTO_LOGIN_TYPE='AZCLI', AZCOPY_TENANT_ID=tenant,
        AZCOPY_LOG_LOCATION=str(private_dir), AZCOPY_JOB_PLAN_LOCATION=str(private_dir))
    result = subprocess.run(['azure-storage-azcopy', 'copy', str(path), url, '--blob-type', 'PageBlob', '--overwrite', 'true'],
        env=env, capture_output=True, text=True, timeout=2700)
    if result.returncode:
        raise RuntimeError('AAD transfer failed; upload URL and logs withheld')


def execute(p, node, directory):
    account = azure(['account', 'show'])
    if account.get('id', '').lower() != p['subscription_id'].lower():
        raise ValueError('Wrong subscription')
    base = ['--resource-group', p['resource_group']]
    gallery = base + ['--gallery-name', p['gallery_name'], '--gallery-image-definition', p['image_definitions'][node]]
    definition = azure(['sig', 'image-definition', 'show', *gallery])
    if definition.get('architecture', '').lower() != recipe.ARCHITECTURES[node][1].lower() or definition.get('hyperVGeneration') != 'V2' or definition.get('osType') != 'Linux' or definition.get('osState') != 'Generalized':
        raise ValueError('Gallery definition architecture/Gen2/Linux/generalization mismatch')
    if any(f.get('name') == 'SecurityType' and f.get('value') not in ('Standard',) for f in definition.get('features', [])):
        raise ValueError('Candidate image cannot satisfy protected-boot gallery definition')
    disk_name = p['staging_disks'][node]
    if any(d.get('name', '').lower() == disk_name.lower() for d in azure(['disk', 'list', *base])):
        raise ValueError('Staging disk exists; inspect uncertain/prior outcome')
    if any(v.get('name') == p['version'] for v in azure(['sig', 'image-version', 'list', *gallery])):
        raise ValueError('Gallery version already exists; never overwrite or duplicate it')
    common = ['--account-name', p['storage_account'], '--container-name', p['container'], '--auth-mode', 'login']
    container = azure(['storage', 'container', 'show', '--account-name', p['storage_account'], '--name', p['container'], '--auth-mode', 'login'])
    properties = container.get('properties', {})
    if 'publicAccess' not in properties or properties['publicAccess'] not in (None, 'None'):
        raise ValueError('Private transport container is not verified')
    blob = f"{p['prefix'].rstrip('/')}/{recipe.SOURCE_REVISION}/{node}.vhd"
    info = azure(['storage', 'blob', 'show', *common, '--name', blob])
    path = directory / f'{node}.vhd'
    azure(['storage', 'blob', 'download', *common, '--name', blob, '--file', str(path), '--overwrite', 'false'])
    report = verify_download(path, info.get('metadata', {}), node)
    if report != p['artifact_reports'][node]:
        raise ValueError('Actual artifact differs from the privately approved report')
    reports = p['artifact_reports']
    plan = recipe.prepare(p, reports)
    selected = next(n for n in plan['nodes'] if n['name'] == node)
    create = selected['steps'][1]['argv'][1:]
    azure([*create, '--tags', f'source_revision={recipe.SOURCE_REVISION}', f'sha256={report["sha256"]}', 'purpose=fleet-image-staging'])
    # If create returns an uncertain error, do not assume it failed or retry.
    try:
        access = azure(['disk', 'grant-access', *base, '--name', disk_name, '--access-level', 'Write', '--duration-in-seconds', '3600'])
        with tempfile.TemporaryDirectory(prefix='private-azcopy-', dir=directory) as private_logs:
            copy_to_disk(path, access['accessSas'], pathlib.Path(private_logs), account['tenantId'])
    finally:
        # Revoke short-lived upload access only. Persistent role assignments stay.
        azure(['disk', 'revoke-access', *base, '--name', disk_name])
    disk = azure(['disk', 'show', *base, '--name', disk_name])
    if disk.get('provisioningState') != 'Succeeded' or disk.get('diskState') != 'Unattached':
        raise ValueError('Staging disk import is not ready')
    azure([*selected['steps'][3]['argv'][1:], '--tags', f'source_revision={recipe.SOURCE_REVISION}', f'sha256={report["sha256"]}'])
    version_args = gallery + ['--gallery-image-version', p['version']]
    azure(['sig', 'image-version', 'wait', *version_args, '--created', '--timeout', '1800'])
    deadline = time.monotonic() + 1800
    while True:
        version = azure(['sig', 'image-version', 'show', *version_args, '--expand', 'ReplicationStatus'])
        state = version.get('replicationStatus', {}).get('aggregatedState')
        if version.get('provisioningState') == 'Succeeded' and state == 'Completed':
            break
        if state == 'Failed' or version.get('provisioningState') == 'Failed' or time.monotonic() >= deadline:
            raise ValueError('Gallery replication incomplete; retain staging for inspection')
        time.sleep(15)
    if version.get('id', '').lower() != selected['image_version_id'].lower() or version.get('tags', {}).get('sha256') != report['sha256']:
        raise ValueError('Gallery provenance mismatch; retain staging')
    azure(['disk', 'delete', *base, '--name', disk_name, '--yes'])
    if any(d.get('name', '').lower() == disk_name.lower() for d in azure(['disk', 'list', *base])):
        raise ValueError('Staging disk cleanup not verified')
    azure(['storage', 'blob', 'delete', *common, '--name', blob])
    if azure(['storage', 'blob', 'exists', *common, '--name', blob]).get('exists') is not False:
        raise ValueError('Transport blob cleanup not verified')
    print('Private gallery import and staging cleanup verified; SHA256=' + report['sha256'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('private_plan')
    parser.add_argument('--node', choices=['node2', 'node3'], required=True)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    def interrupted(signum, frame):
        raise InterruptedError('Import interrupted; inspect state before retry')
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    if os.environ.get('GITHUB_REF') != 'refs/heads/main' or os.environ.get('IMAGE_IMPORT_ENABLED') != 'explicitly-approved':
        raise ValueError('Require approved main workflow and import gate')
    raw = pathlib.Path(args.private_plan).read_bytes()
    p = transport.validate_plan(raw, os.environ.get('APPROVED_IMAGE_IMPORT_PLAN_SHA256', ''), dt.datetime.now(dt.timezone.utc))
    recipe.prepare(p, p['artifact_reports'])
    if args.execute:
        with tempfile.TemporaryDirectory(prefix='private-fleet-import-') as directory:
            execute(p, args.node, pathlib.Path(directory))
    else:
        print('Private import plan validated; no cloud operations performed')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        print('Image import failed closed. Inspect scoped disks/gallery/blobs before retry; persistent IAM is unchanged.', file=sys.stderr)
        sys.exit(1)
