#!/usr/bin/env python3
"""Emit only allowlisted canary facts. Raw plan/key/custom-data never printed."""
import base64
import hashlib
import json
import os
import pathlib
import re
import sys

ROOT = 'terraform/amd-canary'
ADDRESSES = {
    'terraform_data.approval[0]',
    'azurerm_virtual_network.fleet[0]',
    'azurerm_subnet.fleet[0]',
    'azurerm_network_security_group.closed[0]',
    'azurerm_public_ip.node2[0]',
    'azurerm_network_interface.node2[0]',
    'azurerm_network_interface_security_group_association.closed[0]',
    'azurerm_linux_virtual_machine.node2[0]',
}


def require(ok):
    if not ok:
        raise ValueError('Canary plan is outside reviewed contract')


def equal_fields(value, expected):
    require(all(k in value and value[k] == v for k, v in expected.items()))


def fingerprint(key):
    require(isinstance(key, str) and '\r' not in key and '\n' not in key)
    record = re.fullmatch(r'ssh-ed25519[ \t]+([A-Za-z0-9+/]+={0,2})(?:[ \t]+[^\x00-\x1f\x7f]*)?', key.strip(' \t'))
    require(record is not None)
    raw = base64.b64decode(record.group(1), validate=True)
    require(raw[:19] == b'\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20' and len(raw) == 51)
    return 'SHA256:' + base64.b64encode(hashlib.sha256(raw).digest()).decode().rstrip('=')


def validate_links(plan, resources, variables):
    root = plan['configuration']['root_module']
    require(not root.get('module_calls'))
    configs = root['resources']
    expected_addresses = {a.removesuffix('[0]') for a in ADDRESSES}
    require(len(configs) == len(expected_addresses) and {c['address'] for c in configs} == expected_addresses)
    expressions = {c['address']: c.get('expressions', {}) for c in configs}
    changes = {c['address']: c['change'] for c in plan['resource_changes']}
    prefix = '/subscriptions/' + variables['subscription_id'] + '/resourceGroups/' + variables['resource_group_name'] + '/providers/Microsoft.Network/'
    ids = {
        'azurerm_virtual_network.fleet': prefix + 'virtualNetworks/vnet-nixos-fleet-denmarkeast',
        'azurerm_subnet.fleet': prefix + 'virtualNetworks/vnet-nixos-fleet-denmarkeast/subnets/bare-hosts',
        'azurerm_network_interface.node2': prefix + 'networkInterfaces/nic-nixos-node2',
        'azurerm_public_ip.node2': prefix + 'publicIPAddresses/pip6-nixos-node2',
        'azurerm_network_security_group.closed': prefix + 'networkSecurityGroups/nsg-nixos-node2-ssh6',
    }
    def refs(expression, target, attribute='id'):
        require(set(expression) == {'references'})
        require(set(expression['references']) == {target+'[0].'+attribute, target+'[0]', target})
    def scalar(value, unknown, expected):
        if unknown is True:
            require(value is None)
        else:
            require((unknown is None or unknown is False) and value == expected)
    for target, expected in ids.items():
        change = changes[target+'[0]']
        scalar(change['after'].get('id'), change.get('after_unknown', {}).get('id'), expected)
    def link(address, field, target, sequence=False):
        change = changes[address+'[0]']
        refs(expressions[address][field], target)
        value = change['after'].get(field)
        unknown = change.get('after_unknown', {}).get(field)
        if sequence:
            if unknown is True:
                require(value is None)
            else:
                require(isinstance(value, list) and len(value) == 1)
                if unknown is None: unknown = [False]
                require(isinstance(unknown, list) and len(unknown) == 1)
                scalar(value[0], unknown[0], ids[target])
        else:
            scalar(value, unknown, ids[target])
    link('azurerm_linux_virtual_machine.node2', 'network_interface_ids', 'azurerm_network_interface.node2', True)
    link('azurerm_network_interface_security_group_association.closed', 'network_interface_id', 'azurerm_network_interface.node2')
    link('azurerm_network_interface_security_group_association.closed', 'network_security_group_id', 'azurerm_network_security_group.closed')
    vm_config = next(c for c in configs if c['address'] == 'azurerm_linux_virtual_machine.node2')
    require(set(vm_config.get('depends_on', [])) == {'terraform_data.approval', 'azurerm_network_interface_security_group_association.closed'})
    subnet = resources['azurerm_subnet.fleet[0]']
    require(subnet['virtual_network_name'] == 'vnet-nixos-fleet-denmarkeast')
    refs(expressions['azurerm_subnet.fleet']['virtual_network_name'], 'azurerm_virtual_network.fleet', 'name')
    change = changes['azurerm_network_interface.node2[0]']
    blocks = expressions['azurerm_network_interface.node2']['ip_configuration']
    require(isinstance(blocks, list) and len(blocks) == 2)
    block_map = {b['name']['constant_value']: b for b in blocks}
    require(set(block_map) == {'private-ipv4', 'public-ipv6'})
    ips = change['after']['ip_configuration']
    require(len(ips) == 2 and {ip['name'] for ip in ips} == set(block_map))
    unknowns = change.get('after_unknown', {}).get('ip_configuration', [{}, {}])
    require(isinstance(unknowns, list) and len(unknowns) == 2)
    for ip, unknown in zip(ips, unknowns):
        block = block_map[ip['name']]
        refs(block['subnet_id'], 'azurerm_subnet.fleet')
        scalar(ip.get('subnet_id'), unknown.get('subnet_id'), ids['azurerm_subnet.fleet'])
        if ip['name'] == 'public-ipv6':
            refs(block['public_ip_address_id'], 'azurerm_public_ip.node2')
            scalar(ip.get('public_ip_address_id'), unknown.get('public_ip_address_id'), ids['azurerm_public_ip.node2'])
        else:
            require('public_ip_address_id' not in block and not ip.get('public_ip_address_id') and not unknown.get('public_ip_address_id'))


def review(plan, binary, revision, run, bootstrap):
    require(re.fullmatch('[0-9a-f]{40}', revision) and re.fullmatch('[0-9]+', run))
    require(plan.get('errored', False) is False and plan.get('applyable') is True and plan.get('complete') is True)
    require(plan.get('terraform_version') == '1.14.0')
    def no_provisioners(value):
        if isinstance(value, dict):
            require(not value.get('provisioners'))
            for child in value.values(): no_provisioners(child)
        elif isinstance(value, list):
            for child in value: no_provisioners(child)
    no_provisioners(plan.get('configuration', {}))
    changes = plan.get('resource_changes', [])
    require(len(changes) == len(ADDRESSES) and {x['address'] for x in changes} == ADDRESSES)
    require(not plan.get('resource_drift') and not plan.get('deferred_changes'))
    resources = {}
    for x in changes:
        require(x.get('mode') == 'managed' and x['change']['actions'] == ['create'])
        require(x['change'].get('before') is None and not x.get('deposed'))
        resources[x['address']] = x['change']['after']
    variables = {k: v['value'] for k, v in plan['variables'].items()}
    require(variables['enabled'] is True and variables['location'] == 'denmarkeast')
    approval = variables['approval']
    require(all(approval.get(k) is True for k in ('standard_unsigned_gen2', 'public_ipv6_ssh', 'free_compute_and_p6', 'quota_capacity_checked', 'state_and_roles', 'image_region_ready')))
    require(0 <= approval['monthly_ancillary_usd'] <= 3 and bool(approval['evidence']))
    key_fingerprint = fingerprint(variables['ssh_public_key'])
    key = variables['ssh_public_key'].strip(' \t')
    image = variables['image_version_id']
    expected_image = '/subscriptions/' + variables['subscription_id'] + '/resourceGroups/' + variables['resource_group_name'] + '/providers/Microsoft.Compute/galleries/gal_nixos_fleet/images/nixos-node2-x64/versions/0.1.0'
    require(image == expected_image)
    for address, value in resources.items():
        if address.startswith('azurerm_') and 'resource_group_name' in value:
            require(value['resource_group_name'] == variables['resource_group_name'])
        if 'location' in value:
            require(value['location'] == 'denmarkeast')
    vm = resources['azurerm_linux_virtual_machine.node2[0]']
    equal_fields(vm, dict(name='nixos-node2', location='denmarkeast', size='Standard_B1s', source_image_id=image, admin_username='operator', disable_password_authentication=True, secure_boot_enabled=False, vtpm_enabled=False, provision_vm_agent=True, allow_extension_operations=False))
    require(vm.get('admin_password') is None and not vm.get('user_data') and not vm.get('identity') and not vm.get('source_image_reference'))
    require(vm.get('priority', 'Regular') == 'Regular')
    require(not vm.get('additional_capabilities') and not vm.get('secret'))
    require(len(vm['admin_ssh_key']) == 1)
    equal_fields(vm['admin_ssh_key'][0], dict(username='operator', public_key=variables['ssh_public_key']))
    require(len(vm['os_disk']) == 1)
    equal_fields(vm['os_disk'][0], dict(name='os-nixos-node2', caching='ReadWrite', storage_account_type='Premium_LRS', disk_size_gb=64))
    require(not vm['os_disk'][0].get('diff_disk_settings') and not vm['os_disk'][0].get('disk_encryption_set_id'))
    require(len(vm['boot_diagnostics']) == 1 and vm['boot_diagnostics'][0].get('storage_account_uri') is None)
    data = base64.b64decode(vm['custom_data'], validate=True).decode()
    require(data.startswith('#cloud-config\n'))
    require(json.loads(data.split('\n', 1)[1]) == {
        'disable_root': True, 'ssh_pwauth': False, 'write_files': [
            dict(path='/var/lib/fleet-access/authorized_keys', owner='root:root', permissions='0644', content=key+'\n'),
            dict(path='/var/lib/cloud/scripts/per-boot/fleet-ssh6', owner='root:root', permissions='0700', content=bootstrap),
        ]})
    nsg = resources['azurerm_network_security_group.closed[0]']
    require(nsg['name'] == 'nsg-nixos-node2-ssh6' and len(nsg['security_rule']) == 2)
    for rule in nsg['security_rule']:
        allow = rule['name'] == 'AllowIPv6KeyOnlySSH'
        require(allow or rule['name'] == 'DenyAllInbound')
        equal_fields(rule, dict(priority=1000 if allow else 4096, direction='Inbound', access='Allow' if allow else 'Deny', protocol='Tcp' if allow else '*', source_port_range='*', destination_port_range='22' if allow else '*', source_address_prefix='::/0' if allow else '*', destination_address_prefix='*'))
        for field in ('source_port_ranges', 'destination_port_ranges', 'source_address_prefixes', 'destination_address_prefixes', 'source_application_security_group_ids', 'destination_application_security_group_ids'):
            require(not rule.get(field))
    require({r['name'] for r in nsg['security_rule']} == {'AllowIPv6KeyOnlySSH', 'DenyAllInbound'})
    equal_fields(resources['azurerm_public_ip.node2[0]'], dict(name='pip6-nixos-node2', allocation_method='Static', sku='Standard', ip_version='IPv6'))
    equal_fields(resources['azurerm_virtual_network.fleet[0]'], dict(name='vnet-nixos-fleet-denmarkeast', address_space=['10.78.0.0/16', 'fd42:6e69:7800::/48']))
    equal_fields(resources['azurerm_subnet.fleet[0]'], dict(name='bare-hosts', address_prefixes=['10.78.1.0/24', 'fd42:6e69:7800:1::/64'], default_outbound_access_enabled=False))
    require(not resources['azurerm_virtual_network.fleet[0]'].get('dns_servers'))
    subnet = resources['azurerm_subnet.fleet[0]']
    require(not subnet.get('delegation') and not subnet.get('service_endpoints') and not subnet.get('service_endpoint_policy_ids'))
    nic = resources['azurerm_network_interface.node2[0]']
    require(not nic.get('dns_servers'))
    require(nic['name'] == 'nic-nixos-node2' and len(nic['ip_configuration']) == 2)
    require(not nic.get('ip_forwarding_enabled') and not nic.get('accelerated_networking_enabled'))
    for ip in nic['ip_configuration']:
        v4 = ip['name'] == 'private-ipv4'
        require(v4 or ip['name'] == 'public-ipv6')
        equal_fields(ip, dict(private_ip_address_version='IPv4' if v4 else 'IPv6', private_ip_address_allocation='Dynamic', primary=v4))
        if v4:
            require(not ip.get('public_ip_address_id'))
    validate_links(plan, resources, variables)
    # Values below are fixed labels or validated digests, never raw plan fields.
    return dict(schema=1, run_id=run, revision=revision, terraform_root=ROOT,
                backend_key='fleet/amd-canary/terraform.tfstate', plan_sha256=hashlib.sha256(binary).hexdigest(),
                resource_counts={t: sum(a.startswith(t+'.') for a in ADDRESSES) for t in sorted({a.split('.')[0] for a in ADDRESSES})},
                actions={'create': 8, 'update': 0, 'delete': 0}, region='denmarkeast', vm='Standard_B1s', os_disk='Premium_LRS/P6/64GiB',
                image='existing node2-x64 gallery version 0.1.0', ssh_key_fingerprint=key_fingerprint,
                ingress='IPv6 TCP22 from ::/0 only; all other inbound denied',
                planned_authentication='operator public key only; password/root disabled', planned_comin='inactive; no approval marker',
                cloud_init='exact reviewed public-key/per-boot payload')


def main():
    plan_path, binary_path, bootstrap_path = map(pathlib.Path, sys.argv[1:])
    result = review(json.loads(plan_path.read_text()), binary_path.read_bytes(), os.environ['GITHUB_SHA'], os.environ['GITHUB_RUN_ID'], bootstrap_path.read_text())
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        print('Canary summary rejected: plan outside reviewed contract; no plan values disclosed.', file=sys.stderr)
        sys.exit(1)
