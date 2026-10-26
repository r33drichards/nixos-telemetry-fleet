#!/usr/bin/env python3
"""Read-only live availability and quota checks for the explicit closed x64 canary."""
import importlib.util
import json
import pathlib
import re
import subprocess
import sys

spec = importlib.util.spec_from_file_location('sku', pathlib.Path(__file__).with_name('azure-sku-preflight.py'))
sku = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sku)


def quota_integer(value):
    if type(value) is int and value >= 0:
        return value
    if type(value) is str and re.fullmatch(r'[0-9]+', value):
        return int(value)
    raise ValueError('Quota must be a nonnegative integer or decimal digit string')


def validate(topology, skus, usage):
    a = topology.get('approval', {})
    if topology.get('enabled') is not True or not all(a.get(k) is True for k in ('standard_unsigned_gen2', 'public_ipv6_ssh', 'free_compute_and_p6', 'quota_capacity_checked', 'state_and_roles', 'image_region_ready')):
        raise ValueError('Explicit IPv6 SSH canary approvals required')
    if not 0 <= a.get('monthly_ancillary_usd', -1) <= 3 or not a.get('evidence'):
        raise ValueError('Cost evidence required')
    if topology.get('shared_default_outbound_ipv4', False) is not False and (topology.get('shared_default_outbound_ipv4') is not True or a.get('shared_default_outbound_ipv4') is not True):
        raise ValueError('Shared outbound trial requires explicit approval')
    region = topology.get('location', 'denmarkeast')
    if region not in ('denmarkeast', 'westus', 'westus2', 'westus3', 'centralus', 'eastus', 'eastus2', 'northcentralus', 'southcentralus', 'westcentralus'):
        raise ValueError('Unapproved region')
    node = dict(location=region, size='Standard_B1s', architecture='x86_64')
    sku.validate(node, skus, require_trusted_launch=False)
    matches = [s for s in skus if s.get('name') == node['size'] and s.get('resourceType') == 'virtualMachines']
    caps = {c['name']: c['value'] for c in matches[0].get('capabilities', [])}
    if caps.get('PremiumIO', '').lower() != 'true':
        raise ValueError('Premium OS disk support unverified')
    family = matches[0].get('family', '').lower()
    if not family:
        raise ValueError('SKU family not reported')
    for category in (family, 'cores'):
        entries = [u for u in usage if u.get('name', {}).get('value', '').lower() == category]
        if len(entries) != 1 or quota_integer(entries[0]['limit']) - quota_integer(entries[0]['currentValue']) < 1:
            raise ValueError('One available vCPU of family and regional quota required')


class QueryFailure(Exception):
    def __init__(self, category):
        self.category = category


def read(args):
    operation = 'sku-query' if args[:2] == ['vm', 'list-skus'] else 'usage-query'
    # SKU enumeration can paginate even when the CLI filters a single SKU.
    # Bound the read; never relax availability/quota validation on timeout.
    try:
        result = subprocess.run(['az', *args, '--output', 'json', '--only-show-errors'], capture_output=True, text=True, timeout=240 if operation == 'sku-query' else 60)
    except subprocess.TimeoutExpired:
        raise QueryFailure(operation + ':timeout') from None
    except OSError:
        raise QueryFailure(operation + ':execution-unavailable') from None
    if result.returncode:
        denied = any(code in result.stderr for code in ('AuthorizationFailed', 'AuthorizationPermissionMismatch', 'Forbidden', 'Insufficient privileges'))
        raise QueryFailure(operation + (':read-denied' if denied else ':read-failed'))
    try:
        value = json.loads(result.stdout)
        if not isinstance(value, list):
            raise ValueError()
        return value
    except (ValueError, TypeError):
        raise QueryFailure(operation + ':invalid-response') from None



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
    region = topology.get('location', 'denmarkeast')
    validate(topology, read(['vm', 'list-skus', '--resource-type', 'virtualMachines', '--location', region, '--size', 'Standard_B1s', '--all']), read(['vm', 'list-usage', '--location', region]))
    print('B1s availability/Gen2/architecture and family/regional quota checks passed; free entitlement remains separately attested.')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        category = error.category if isinstance(error, QueryFailure) else ('validation' if isinstance(error, (ValueError, KeyError, TypeError)) else 'internal')
        print('B1s preflight failed closed [' + category + ']; no resource or role changes attempted.', file=sys.stderr)
        sys.exit(1)
