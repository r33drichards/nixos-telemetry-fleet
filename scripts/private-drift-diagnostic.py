#!/usr/bin/env python3
"""Separate exact private drift evidence from schema-name-only public output."""
import hashlib
import json
import os
from pathlib import Path
import re
import sys

PROVIDER = 'registry.terraform.io/hashicorp/azurerm'
TYPES = {
    'azurerm_network_interface.node2[0]': 'azurerm_network_interface',
    'azurerm_network_security_group.closed[0]': 'azurerm_network_security_group',
    'azurerm_public_ip.node2[0]': 'azurerm_public_ip',
    'azurerm_subnet.fleet[0]': 'azurerm_subnet',
    'azurerm_virtual_network.fleet[0]': 'azurerm_virtual_network',
    'azurerm_linux_virtual_machine.node2[0]': 'azurerm_linux_virtual_machine',
    'azurerm_network_interface_security_group_association.closed[0]': 'azurerm_network_interface_security_group_association',
}

def binding(env):
    if (env.get('GITHUB_REF') != 'refs/heads/main' or
        env.get('GITHUB_REPOSITORY') != 'r33drichards/nixos-telemetry-fleet' or
        env.get('TF_ROOT') != 'terraform/amd-canary' or env.get('OPERATION') != 'plan' or
        env.get('RETAIN_DRIFT_DIAGNOSTIC') != 'true' or
        env.get('DRIFT_PRIVATE_REVIEW_READY') != 'explicitly-confirmed'):
        raise ValueError('gate')
    for name, pattern in [('GITHUB_SHA', r'[0-9a-f]{40}'), ('GITHUB_RUN_ID', r'[0-9]+'), ('GITHUB_RUN_ATTEMPT', r'[1-9][0-9]*')]:
        if not re.fullmatch(pattern, env.get(name, '')): raise ValueError('binding')
    return {'revision': env['GITHUB_SHA'], 'run': env['GITHUB_RUN_ID'],
            'attempt': env['GITHUB_RUN_ATTEMPT'], 'root': env['TF_ROOT'],
            'terraform_version': '1.14.0', 'provider_version': '4.51.0'}

def structural(before, after, present_before, present_after):
    if not present_before or not present_after: return 'presence-change'
    if before is None and after in ([], {}): return 'null-to-empty'
    if after is None and before in ([], {}): return 'empty-to-null'
    if isinstance(before, (list, dict)) or isinstance(after, (list, dict)): return 'collection-change'
    return 'scalar-change'

def compare(plan, schema, env):
    bound = binding(env)
    if plan.get('terraform_version') != '1.14.0': raise ValueError('version')
    resources = schema['provider_schemas'][PROVIDER]['resource_schemas']
    drift = plan.get('resource_drift', [])
    if not isinstance(drift, list) or len(drift) > len(TYPES): raise ValueError('drift schema')
    summary, seen = [], set()
    for entry in drift:
        address = entry.get('address')
        if address not in TYPES or address in seen or entry.get('type') != TYPES[address] or entry.get('provider_name') != PROVIDER:
            raise ValueError('resource')
        seen.add(address)
        change = entry['change']
        if change.get('actions') != ['update']: raise ValueError('drift action')
        before, after = change['before'], change['after']
        if not isinstance(before, dict) or not isinstance(after, dict): raise ValueError('values schema')
        block = resources[TYPES[address]]['block']
        attributes, blocks = block.get('attributes', {}), block.get('block_types', {})
        if not (before.keys() | after.keys()) <= (attributes.keys() | blocks.keys()):
            raise ValueError('attribute outside pinned schema')
        fields = []
        for name in sorted(before.keys() | after.keys()):
            if name in before and name in after and before[name] == after[name]: continue
            if not re.fullmatch(r'[a-z][a-z0-9_]*', name): raise ValueError('schema name')
            a = attributes.get(name, {})
            fields.append({'field': name, 'computed': bool(a.get('computed', False)),
                           'configurable': name in blocks or bool(a.get('optional') or a.get('required')),
                           'sensitive': bool(a.get('sensitive', False)),
                           'structure': structural(before.get(name), after.get(name), name in before, name in after)})
        summary.append({'address': address, 'action': 'update', 'fields': fields})
    # Exact drift stays private; never include all plan variables or full state.
    private = {'format': 1, 'binding': bound, 'resource_drift': drift}
    public = {'binding': bound, 'drift_count': len(drift), 'resources': summary,
              'qualification': 'classification only; no drift acceptance or state reconciliation'}
    return private, public

def main():
    plan_path, schema_path, output = map(Path, sys.argv[1:])
    private, public = compare(json.loads(plan_path.read_text()), json.loads(schema_path.read_text()), os.environ)
    output.mkdir(mode=0o700)
    data = (json.dumps(private, sort_keys=True) + '\n').encode()
    with (output/'comparison.json').open('xb') as f: f.write(data)
    (output/'comparison.json').chmod(0o600)
    manifest = {'binding': private['binding'], 'comparison_sha256': hashlib.sha256(data).hexdigest(),
                'purpose': 'diagnostic-only; never an apply input'}
    (output/'manifest.json').write_text(json.dumps(manifest, sort_keys=True)+'\n')
    (output/'manifest.json').chmod(0o600)
    (output/'summary.json').write_text(json.dumps(public, sort_keys=True)+'\n')
    (output/'summary.json').chmod(0o600)

if __name__ == '__main__':
    try: main()
    except Exception:
        raise SystemExit('Private drift diagnostic failed closed; no values disclosed.')
