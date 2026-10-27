#!/usr/bin/env python3
"""Bounded resource GETs; never print addresses, credentials or raw ARM output."""
import json
import os
import subprocess

def inspect(env, query):
    if (env.get('GITHUB_REF') != 'refs/heads/main' or
        env.get('GITHUB_REPOSITORY') != 'r33drichards/nixos-telemetry-fleet' or
        env.get('OIDC_CHECK_ENABLED') != 'explicitly-approved'):
        raise ValueError('gate')
    if not env.get('FLEET_RESOURCE_GROUP') or not env.get('AZURE_SUBSCRIPTION_ID'):
        raise ValueError('scope')
    scope = ['--resource-group', env['FLEET_RESOURCE_GROUP'], '--subscription', env['AZURE_SUBSCRIPTION_ID']]
    subnet = query(['network', 'vnet', 'subnet', 'show', *scope,
                    '--vnet-name', 'vnet-nixos-fleet-denmarkeast', '--name', 'bare-hosts'])
    nic = query(['network', 'nic', 'show', *scope, '--name', 'nic-nixos-node2'])
    nsg = query(['network', 'nsg', 'show', *scope, '--name', 'nsg-nixos-node2-ssh6'])
    def tri(value):
        return 'true' if value is True else 'false' if value is False else 'unknown'
    def linked(value): return isinstance(value, dict) and bool(value.get('id'))
    rules = nsg.get('securityRules', [])
    defaults = nsg.get('defaultSecurityRules', [])
    if not isinstance(rules, list) or not isinstance(defaults, list): raise ValueError('schema')
    return {
        'subnet_default_outbound_access': tri(subnet.get('defaultOutboundAccess')),
        'nic_default_outbound_allocated': tri(nic.get('defaultOutboundConnectivityEnabled')),
        'subnet_nat_attached': linked(subnet.get('natGateway')),
        'subnet_route_table_attached': linked(subnet.get('routeTable')),
        'subnet_nsg_attached': linked(subnet.get('networkSecurityGroup')),
        'nic_expected_nsg_attached': (nic.get('networkSecurityGroup') or {}).get('id', '').lower() == nsg.get('id', '!').lower(),
        'custom_outbound_allow_count': sum(r.get('direction') == 'Outbound' and r.get('access') == 'Allow' for r in rules),
        'custom_outbound_deny_count': sum(r.get('direction') == 'Outbound' and r.get('access') == 'Deny' for r in rules),
        'default_internet_allow_present': any(r.get('direction') == 'Outbound' and r.get('access') == 'Allow' and r.get('destinationAddressPrefix') == 'Internet' for r in defaults),
        'qualification': 'resource-settings-only; no guest connectivity or effective-route proof',
    }

def query(args):
    result = subprocess.run(['az', *args, '--output', 'json', '--only-show-errors'],
                            capture_output=True, text=True, timeout=90, check=True)
    return json.loads(result.stdout)

if __name__ == '__main__':
    try:
        print(json.dumps(inspect(os.environ, query), sort_keys=True))
    except subprocess.TimeoutExpired:
        raise SystemExit('Egress read failed: timeout; raw output suppressed.')
    except subprocess.CalledProcessError:
        raise SystemExit('Egress read failed: Azure command failed; raw output suppressed.')
    except Exception:
        raise SystemExit('Egress read failed: gate or response schema; raw output suppressed.')
