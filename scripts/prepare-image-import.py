#!/usr/bin/env python3
"""Prepare a private, reviewable Azure import recipe. Never invokes Azure or AzCopy."""
import argparse
import hashlib
import json
import os
import pathlib
import re
import sys

SOURCE_REVISION = 'ba51125b3d367b8326b357023a5ad5812239b7a9'
ARCHITECTURES = {'node2': ('x86_64-linux', 'x64'), 'node3': ('aarch64-linux', 'Arm64')}


def prepare(config, reports):
    if config.get('source_revision') != SOURCE_REVISION or config.get('location') != 'westus3':
        raise ValueError('Expected the verified revision and West US 3')
    if set(reports) != set(ARCHITECTURES):
        raise ValueError('Exactly one AMD and one ARM artifact report required')
    for key in ['resource_group', 'gallery_name', 'version']:
        if not re.fullmatch(r'[A-Za-z0-9_.-]+', config.get(key, '')):
            raise ValueError('Explicit safe resource names required')
    if not re.fullmatch(r'\d+\.\d+\.\d+', config['version']):
        raise ValueError('Explicit immutable gallery version required')
    if not re.fullmatch(r'[0-9a-fA-F-]{36}', config.get('subscription_id', '')):
        raise ValueError('Explicit subscription identifier required')
    if not 0 <= config.get('setup_estimate_usd', -1) <= 1:
        raise ValueError('Setup estimate must fit the approved $1 ceiling')
    if not 0 <= config.get('monthly_ancillary_estimate_usd', -1) <= 3:
        raise ValueError('Ancillary estimate must fit the approved $3 monthly ceiling')
    for key in ['cost_evidence', 'phase_b_scope_approval']:
        if not isinstance(config.get(key), str) or not config[key].strip():
            raise ValueError('Exact import cost and temporary permission evidence is required')
    nodes = []
    prefix = f"/subscriptions/{config['subscription_id']}/resourceGroups/{config['resource_group']}"
    for name, (system, arch) in ARCHITECTURES.items():
        report = reports[name]
        if report.get('source_revision') != SOURCE_REVISION or report.get('system') != system:
            raise ValueError('Artifact source/architecture mismatch')
        if report.get('virtual_bytes') != 8 * 1024**3 or report.get('file_bytes') != 8 * 1024**3 + 512:
            raise ValueError('Expected actual 8-GiB fixed VHD plus 512-byte footer')
        if not re.fullmatch(r'[0-9a-f]{64}', report.get('sha256', '')):
            raise ValueError('Actual rebuilt artifact checksum required')
        if report.get('artifact_inspection_passed') is not True:
            raise ValueError('Actual EFI/metadata/private-key inspection required')
        definition = config.get('image_definitions', {}).get(name, '')
        disk = config.get('staging_disks', {}).get(name, '')
        if not all(re.fullmatch(r'[A-Za-z0-9_.-]+', value) for value in [definition, disk]):
            raise ValueError('Explicit definition and staging disk names required')
        disk_id = f'{prefix}/providers/Microsoft.Compute/disks/{disk}'
        version_id = f'{prefix}/providers/Microsoft.Compute/galleries/{config["gallery_name"]}/images/{definition}/versions/{config["version"]}'
        nodes.append({
            'name': name, 'system': system, 'sha256': report['sha256'],
            'file_bytes': report['file_bytes'], 'disk_id': disk_id, 'image_version_id': version_id,
            'steps': [
                {'stage': 'preflight', 'requirements': ['OIDC account/RG match', 'existing private Gen2 gallery/definition matches architecture; this import does not authorize VM boot security changes', 'disk and version names absent; uncertain outcomes require inspection', 'recheck artifact checksum immediately before transfer']},
                {'stage': 'create-upload-disk', 'argv': ['az', 'disk', 'create', '--resource-group', config['resource_group'], '--name', disk, '--location', 'westus3', '--upload-type', 'Upload', '--upload-size-bytes', str(report['file_bytes']), '--data-access-auth-mode', 'AzureActiveDirectory', '--sku', 'Standard_LRS', '--os-type', 'Linux', '--architecture', arch, '--hyper-v-generation', 'V2']},
                {'stage': 'upload', 'requirements': ['grant short-lived Write upload access under approved scope', 'capture URL privately, never print it', 'AzCopy uses existing Azure CLI/Entra session, not account keys', 'record checksum/source tags', 'revoke access on success or failure']},
                {'stage': 'import-gallery', 'argv': ['az', 'sig', 'image-version', 'create', '--resource-group', config['resource_group'], '--gallery-name', config['gallery_name'], '--gallery-image-definition', definition, '--gallery-image-version', config['version'], '--location', 'westus3', '--os-snapshot', disk_id, '--target-regions', 'westus3', '--replica-count', '1', '--storage-account-type', 'Standard_LRS', '--replication-mode', 'Full']},
                {'stage': 'verify-and-clean', 'requirements': ['wait for successful provisioning AND completed West US 3 replication', 'persist private provenance manifest and verify image version ID', 'delete only this staging disk under approved cleanup scope', 'on failure retain recorded outstanding IDs for reviewed cleanup; never report cleanup success without verification']},
            ],
        })
    if len({n['disk_id'].lower() for n in nodes}) != 2 or len({n['image_version_id'].lower() for n in nodes}) != 2:
        raise ValueError('Architecture staging disks and image definitions must be distinct')
    return {'source_revision': SOURCE_REVISION, 'execute': False, 'status': 'private recipe requiring action-time approval; no Azure operations performed', 'setup_ceiling_usd': 1, 'monthly_ancillary_ceiling_usd': 3, 'retain': 'one gallery version per architecture; no retained source VHD', 'nodes': nodes, 'terraform_handoff': 'Use exact immutable version IDs with approved existing NIC IDs; private saved-plan hash approval remains required. Current Trusted Launch guard is unchanged.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('private_config')
    parser.add_argument('private_artifact_reports')
    parser.add_argument('private_output')
    args = parser.parse_args()
    result = prepare(json.loads(pathlib.Path(args.private_config).read_text()), json.loads(pathlib.Path(args.private_artifact_reports).read_text()))
    data = (json.dumps(result, indent=2) + '\n').encode()
    # Exclusive creation avoids overwriting a previously reviewed payload.
    with os.fdopen(os.open(args.private_output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as output:
        output.write(data)
    print('Prepared private import recipe SHA256=' + hashlib.sha256(data).hexdigest())


if __name__ == '__main__':
    try:
        main()
    except Exception:
        print('Image import preparation failed; inspect inputs privately. No cloud operation was attempted.', file=sys.stderr)
        sys.exit(1)
