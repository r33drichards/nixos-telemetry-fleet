#!/usr/bin/env python3
"""Read live subscription SKU capabilities; fail closed without printing inventory.

Accept a private tfvars JSON file, or --plan-json with terraform show -json output.
No credentials are generated, no resource mutation occurs, and no metadata is
written to the repository. Run immediately before both cloud plan and apply.
"""
import json
import pathlib
import subprocess
import sys


def validate(node, skus):
    region = node['location'].lower()
    matches = [s for s in skus if s.get('resourceType') == 'virtualMachines'
               and s.get('name', '').lower() == node['size'].lower()
               and region in [v.lower() for v in s.get('locations', [])]]
    if len(matches) != 1:
        raise ValueError('SKU unavailable or ambiguous in selected region')
    sku = matches[0]
    zone = node.get('zone')
    for restriction in sku.get('restrictions', []):
        info = restriction.get('restrictionInfo', {})
        regions = info.get('locations', [])
        if restriction.get('type') == 'Location':
            regions = regions or restriction.get('values', [])
            if not regions or region in [v.lower() for v in regions]:
                raise ValueError('SKU restricted for this subscription/region')
        elif restriction.get('type') == 'Zone':
            if zone and (not regions or region in [v.lower() for v in regions]):
                zones = info.get('zones', []) or restriction.get('values', [])
                if not zones or zone in zones:
                    raise ValueError('SKU restricted in selected zone')
        else:
            raise ValueError('Unrecognized SKU restriction')
    if zone:
        zones = [z for loc in sku.get('locationInfo', [])
                 if loc.get('location', '').lower() == region for z in loc.get('zones', [])]
        if zone not in zones:
            raise ValueError('Selected zone lacks availability evidence')
    caps = {c['name']: c['value'] for c in sku.get('capabilities', [])}
    if caps.get('TrustedLaunchDisabled', '').lower() != 'false':
        raise ValueError('Trusted Launch disabled or support unverified')
    if 'V2' not in [v.strip().upper() for v in caps.get('HyperVGenerations', '').split(',')]:
        raise ValueError('Gen2 support unverified')
    expected = {'x86_64': 'x64', 'aarch64': 'arm64'}[node['architecture']]
    if caps.get('CpuArchitectureType', '').lower() != expected:
        raise ValueError('SKU architecture mismatch or unverified')


def main():
    if len(sys.argv) == 3 and sys.argv[1] == '--plan-json':
        plan = json.loads(pathlib.Path(sys.argv[2]).read_text())
        topology = {k: v['value'] for k, v in plan['variables'].items()}
    elif len(sys.argv) == 2 and not sys.argv[1].startswith('--'):
        topology = json.loads(pathlib.Path(sys.argv[1]).read_text())
    else:
        raise ValueError('Private topology or saved plan JSON required')
    if topology.get('enabled') is not True or len(topology.get('nodes', {})) != 2:
        raise ValueError('Live preflight requires the approved two-host topology')
    if len({n['size'].lower() for n in topology['nodes'].values()}) != 2:
        raise ValueError('Continuous free fleet requires distinct SKU meters')
    for node in topology['nodes'].values():
        if node.get('sku_available') is not True or node.get('trusted_launch_supported') is not True:
            raise ValueError('Missing explicit SKU/security qualification')
        result = subprocess.run(['az', 'vm', 'list-skus', '--resource-type', 'virtualMachines',
            '--location', node['location'], '--size', node['size'], '--all', '--output', 'json',
            '--only-show-errors'], capture_output=True, text=True, timeout=60)
        if result.returncode:
            raise ValueError('Read-only SKU query failed; do not broaden roles automatically')
        validate(node, json.loads(result.stdout))
    print('PASS: current SKU availability, architecture and Trusted Launch capability')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        # Avoid exposing account inventory in public workflow logs.
        print('Azure SKU/security preflight failed; inspect through approved private diagnostics.', file=sys.stderr)
        sys.exit(1)
