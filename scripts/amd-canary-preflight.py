#!/usr/bin/env python3
"""Read-only live availability and quota checks for the explicit closed AMD canary."""
import importlib.util
import json
import pathlib
import subprocess
import sys

spec = importlib.util.spec_from_file_location('sku', pathlib.Path(__file__).with_name('azure-sku-preflight.py'))
sku = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sku)


def validate(topology, skus, usage):
    a = topology.get('approval', {})
    if topology.get('enabled') is not True or not all(a.get(k) is True for k in ('standard_unsigned_gen2', 'closed_network', 'free_compute_and_p6', 'quota_capacity_checked', 'state_and_roles', 'image_region_ready')):
        raise ValueError('Explicit closed canary approvals required')
    if not 0 <= a.get('monthly_ancillary_usd', -1) <= 3 or not a.get('evidence'):
        raise ValueError('Cost evidence required')
    region = topology.get('location', 'westus3')
    if region not in ('westus', 'westus2', 'westus3', 'centralus', 'eastus', 'eastus2', 'northcentralus', 'southcentralus', 'westcentralus'):
        raise ValueError('Unapproved region')
    node = dict(location=region, size='Standard_B2ats_v2', architecture='x86_64')
    sku.validate(node, skus, require_trusted_launch=False)
    matches = [s for s in skus if s.get('name') == node['size'] and s.get('resourceType') == 'virtualMachines']
    family = matches[0].get('family', '').lower()
    if not family:
        raise ValueError('SKU family not reported')
    for category in (family, 'cores'):
        entries = [u for u in usage if u.get('name', {}).get('value', '').lower() == category]
        if len(entries) != 1 or entries[0]['limit'] - entries[0]['currentValue'] < 2:
            raise ValueError('Two free vCPUs of family and regional quota required')


def read(args):
    result = subprocess.run(['az', *args, '--output', 'json', '--only-show-errors'], capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise ValueError('Read-only query failed')
    return json.loads(result.stdout)


def validate_plan_actions(plan):
    for change in plan.get('resource_changes', []):
        if 'delete' in change.get('change', {}).get('actions', []):
            raise ValueError('Canary create/update scope forbids deletion or replacement')


def main():
    if len(sys.argv) == 3 and sys.argv[1] in ('--plan-json', '--check-plan-json'):
        plan = json.loads(pathlib.Path(sys.argv[2]).read_text())
        validate_plan_actions(plan)
        if sys.argv[1] == '--check-plan-json':
            print('Canary plan contains no delete or replacement actions')
            return
        topology = {k: v['value'] for k, v in plan['variables'].items()}
    elif len(sys.argv) == 2:
        topology = json.loads(pathlib.Path(sys.argv[1]).read_text())
    else:
        raise ValueError('Private topology or saved plan required')
    region = topology.get('location', 'westus3')
    validate(topology, read(['vm', 'list-skus', '--resource-type', 'virtualMachines', '--location', region, '--size', 'Standard_B2ats_v2', '--all']), read(['vm', 'list-usage', '--location', region]))
    print('AMD availability/Gen2/architecture and family/regional quota checks passed; free entitlement remains separately attested.')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        print('AMD preflight failed closed; inspect approvals/quota privately. No resource or role changes attempted.', file=sys.stderr)
        sys.exit(1)
