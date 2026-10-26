import base64
import copy
import importlib.util
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('review', ROOT/'scripts/review-canary-plan.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def fixture():
    key = 'ssh-ed25519 '+base64.b64encode(b'\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20'+bytes(32)).decode()
    image = '/subscriptions/fixture/resourceGroups/fixture/providers/Microsoft.Compute/galleries/gal_nixos_fleet/images/nixos-node2-x64/versions/0.1.0'
    bootstrap = (ROOT/'terraform/amd-canary/bootstrap/ssh6-per-boot.sh').read_text()
    data = {'disable_root': True, 'ssh_pwauth': False, 'write_files': [
        dict(path='/var/lib/fleet-access/authorized_keys', owner='root:root', permissions='0644', content=key+'\n'),
        dict(path='/var/lib/cloud/scripts/per-boot/fleet-ssh6', owner='root:root', permissions='0700', content=bootstrap)]}
    r = {a:{} for a in m.ADDRESSES}
    r['azurerm_linux_virtual_machine.node2[0]'] = dict(name='nixos-node2', location='denmarkeast', size='Standard_B1s', source_image_id=image, admin_username='operator', disable_password_authentication=True, secure_boot_enabled=False, vtpm_enabled=False, provision_vm_agent=True, allow_extension_operations=False, admin_ssh_key=[dict(username='operator',public_key=key)], os_disk=[dict(name='os-nixos-node2',caching='ReadWrite',storage_account_type='Premium_LRS',disk_size_gb=64)], boot_diagnostics=[{}],custom_data=base64.b64encode(('#cloud-config\n'+json.dumps(data)).encode()).decode())
    r['azurerm_network_security_group.closed[0]'] = dict(name='nsg-nixos-node2-ssh6', security_rule=[dict(name='AllowIPv6KeyOnlySSH' if allow else 'DenyAllInbound', priority=1000 if allow else 4096, direction='Inbound',access='Allow' if allow else 'Deny',protocol='Tcp' if allow else '*',source_port_range='*',destination_port_range='22' if allow else '*',source_address_prefix='::/0' if allow else '*',destination_address_prefix='*') for allow in [True,False]])
    r['azurerm_public_ip.node2[0]'] = dict(name='pip6-nixos-node2',allocation_method='Static',sku='Standard',ip_version='IPv6')
    r['azurerm_virtual_network.fleet[0]'] = dict(name='vnet-nixos-fleet-denmarkeast',address_space=['10.78.0.0/16','fd42:6e69:7800::/48'])
    r['azurerm_subnet.fleet[0]'] = dict(name='bare-hosts',address_prefixes=['10.78.1.0/24','fd42:6e69:7800:1::/64'],default_outbound_access_enabled=False)
    r['azurerm_network_interface.node2[0]'] = dict(name='nic-nixos-node2',ip_configuration=[dict(name='private-ipv4' if v4 else 'public-ipv6',private_ip_address_version='IPv4' if v4 else 'IPv6',private_ip_address_allocation='Dynamic',primary=v4) for v4 in [True,False]])
    variables=dict(enabled=True,location='denmarkeast',ssh_public_key=key,image_version_id=image,subscription_id='fixture',resource_group_name='fixture')
    variables['approval'] = dict.fromkeys(('standard_unsigned_gen2','public_ipv6_ssh','free_compute_and_p6','quota_capacity_checked','state_and_roles','image_region_ready'), True)
    variables['approval'].update(monthly_ancillary_usd=3,evidence='private fixture evidence')
    plan=dict(applyable=True,complete=True,terraform_version='1.14.0',variables={k:{'value':v} for k,v in variables.items()},resource_changes=[dict(address=a,mode='managed',change=dict(actions=['create'],before=None,after=v)) for a,v in r.items()])
    def ref(target, attribute='id'):
        return {'references':[target+'[0].'+attribute,target+'[0]',target]}
    configs={a.removesuffix('[0]'):{'address':a.removesuffix('[0]'),'expressions':{}} for a in m.ADDRESSES}
    vm=configs['azurerm_linux_virtual_machine.node2']
    vm['expressions']['network_interface_ids']=ref('azurerm_network_interface.node2')
    vm['depends_on']=['terraform_data.approval','azurerm_network_interface_security_group_association.closed']
    association=configs['azurerm_network_interface_security_group_association.closed']['expressions']
    association['network_interface_id']=ref('azurerm_network_interface.node2')
    association['network_security_group_id']=ref('azurerm_network_security_group.closed')
    configs['azurerm_subnet.fleet']['expressions']['virtual_network_name']=ref('azurerm_virtual_network.fleet','name')
    r['azurerm_subnet.fleet[0]']['virtual_network_name']='vnet-nixos-fleet-denmarkeast'
    blocks=[]
    for name in ['private-ipv4','public-ipv6']:
        block={'name':{'constant_value':name},'subnet_id':ref('azurerm_subnet.fleet')}
        if name=='public-ipv6':block['public_ip_address_id']=ref('azurerm_public_ip.node2')
        blocks.append(block)
    configs['azurerm_network_interface.node2']['expressions']['ip_configuration']=blocks
    plan['configuration']={'root_module':{'resources':list(configs.values())}}
    for change in plan['resource_changes']:
        change['change']['after_unknown']={'id':True}
        if change['address']=='azurerm_linux_virtual_machine.node2[0]':
            change['change']['after']['network_interface_ids']=[None]
            change['change']['after_unknown']['network_interface_ids']=[True]
        if change['address']=='azurerm_network_interface_security_group_association.closed[0]':
            change['change']['after_unknown'].update(network_interface_id=True,network_security_group_id=True)
        if change['address']=='azurerm_network_interface.node2[0]':
            change['change']['after_unknown']['ip_configuration']=[{'subnet_id':True},{'subnet_id':True,'public_ip_address_id':True}]
    return plan, bootstrap


class Review(unittest.TestCase):
    def setUp(self): self.plan,self.bootstrap=fixture()
    def run_review(self): return m.review(self.plan,b'binary fixture','a'*40,'123',self.bootstrap)
    def resource(self, name): return next(x['change']['after'] for x in self.plan['resource_changes'] if x['address']==name)
    def test_summary_contains_no_key_payload_or_inventory(self):
        output=json.dumps(self.run_review())
        for forbidden in [self.plan['variables']['ssh_public_key']['value'],self.bootstrap,'/subscriptions/', 'fixture']:
            self.assertNotIn(forbidden,output)
        self.assertEqual(self.run_review()['actions'],dict(create=8,update=0,delete=0))
    def test_extra_missing_and_duplicate_resources_rejected(self):
        original=copy.deepcopy(self.plan)
        for change in ['extra','missing','duplicate']:
            self.plan=copy.deepcopy(original)
            if change=='missing': self.plan['resource_changes'].pop()
            else:
                self.plan['resource_changes'].append(copy.deepcopy(self.plan['resource_changes'][0]))
                if change=='extra': self.plan['resource_changes'][-1]['address']='azurerm_role_assignment.unapproved'
            with self.assertRaises(ValueError): self.run_review()
    def test_actions_and_unknown_critical_values_rejected(self):
        for actions in [['update'],['delete','create'],['no-op']]:
            self.plan['resource_changes'][0]['change']['actions']=actions
            with self.assertRaises(ValueError): self.run_review()
    def test_changed_vm_contract_rejected(self):
        original=copy.deepcopy(self.plan)
        for field,value in [('size','Standard_D2s_v5'),('location','westus3'),('allow_extension_operations',True),('admin_password','secret-canary'),('user_data','secret-canary'),('source_image_id',None),('disable_password_authentication',False)]:
            self.plan=copy.deepcopy(original);self.resource('azurerm_linux_virtual_machine.node2[0]')[field]=value
            with self.assertRaises(ValueError): self.run_review()
    def test_wrong_disk_or_public_ipv4_rejected(self):
        self.resource('azurerm_linux_virtual_machine.node2[0]')['os_disk'][0]['disk_size_gb']=128
        with self.assertRaises(ValueError): self.run_review()
        self.setUp();self.resource('azurerm_public_ip.node2[0]')['ip_version']='IPv4'
        with self.assertRaises(ValueError): self.run_review()
    def test_ingress_change_rejected(self):
        self.resource('azurerm_network_security_group.closed[0]')['security_rule'][0]['destination_port_range']='*'
        with self.assertRaises(ValueError): self.run_review()
    def test_custom_data_or_comin_change_rejected(self):
        vm=self.resource('azurerm_linux_virtual_machine.node2[0]')
        payload=base64.b64decode(vm['custom_data']).decode().replace('"ssh_pwauth": false','"ssh_pwauth": true')
        vm['custom_data']=base64.b64encode(payload.encode()).decode()
        with self.assertRaises(ValueError): self.run_review()
        self.setUp()
        with self.assertRaises(ValueError): m.review(self.plan,b'x','a'*40,'123',self.bootstrap+'\ntouch /var/lib/fleet-access/bootstrap-approved\n')
    def test_binding_rejects_untrusted_run_or_revision(self):
        for revision,run in [('secret','123'),('a'*40,'secret')]:
            with self.assertRaises(ValueError):m.review(self.plan,b'x',revision,run,self.bootstrap)

    def test_incomplete_plan_and_provisioners_rejected(self):
        self.plan['complete']=False
        with self.assertRaises(ValueError): self.run_review()
        self.setUp();self.plan['configuration']={'root_module':{'resources':[{'provisioners':[{'type':'local-exec'}]}]}}
        with self.assertRaises(ValueError): self.run_review()
    def test_missing_free_approval_rejected(self):
        self.plan['variables']['approval']['value']['free_compute_and_p6']=False
        with self.assertRaises(ValueError): self.run_review()

    def test_multiline_two_distinct_keys_rejected(self):
        first=self.plan['variables']['ssh_public_key']['value']
        second='ssh-ed25519 '+base64.b64encode(b'\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20'+bytes([1])*32).decode()
        for separator in ('\n','\r\n','\r'):
            combined=first+separator+second
            self.plan['variables']['ssh_public_key']['value']=combined
            vm=self.resource('azurerm_linux_virtual_machine.node2[0]')
            vm['admin_ssh_key'][0]['public_key']=combined
            data=json.loads(base64.b64decode(vm['custom_data']).decode().split('\n',1)[1])
            data['write_files'][0]['content']=combined+'\n'
            vm['custom_data']=base64.b64encode(('#cloud-config\n'+json.dumps(data)).encode()).decode()
            with self.assertRaises(ValueError):self.run_review()
        self.assertEqual(m.fingerprint(first+' comment with spaces'),m.fingerprint(first))
        with self.assertRaises(ValueError):m.fingerprint(first+'\n')
    def test_foreign_known_links_rejected(self):
        for address,field,value in [
            ('azurerm_linux_virtual_machine.node2[0]','network_interface_ids',['/foreign/nic']),
            ('azurerm_network_interface_security_group_association.closed[0]','network_interface_id','/foreign/nic'),
            ('azurerm_network_interface_security_group_association.closed[0]','network_security_group_id','/foreign/nsg')]:
            self.setUp();self.resource(address)[field]=value
            change=next(c['change'] for c in self.plan['resource_changes'] if c['address']==address)
            change['after_unknown'].pop(field,None)
            with self.assertRaises(ValueError):self.run_review()
    def test_foreign_unknown_expression_rejected(self):
        configs=self.plan['configuration']['root_module']['resources']
        vm=next(c for c in configs if c['address']=='azurerm_linux_virtual_machine.node2')
        vm['expressions']['network_interface_ids']={'references':['azurerm_network_interface.foreign[0].id','azurerm_network_interface.foreign[0]','azurerm_network_interface.foreign']}
        with self.assertRaises(ValueError):self.run_review()
    def test_foreign_subnet_public_ip_and_missing_config_rejected(self):
        for field in ('subnet_id','public_ip_address_id'):
            self.setUp();self.resource('azurerm_network_interface.node2[0]')['ip_configuration'][1][field]='/foreign/id'
            with self.assertRaises(ValueError):self.run_review()
        self.setUp();self.plan.pop('configuration')
        with self.assertRaises(KeyError):self.run_review()
    def test_missing_nsg_dependency_rejected(self):
        configs=self.plan['configuration']['root_module']['resources']
        next(c for c in configs if c['address']=='azurerm_linux_virtual_machine.node2')['depends_on']=[]
        with self.assertRaises(ValueError):self.run_review()

    def test_known_ids_match_the_same_planned_graph(self):
        prefix='/subscriptions/fixture/resourceGroups/fixture/providers/Microsoft.Network/'
        ids={
            'azurerm_virtual_network.fleet[0]':prefix+'virtualNetworks/vnet-nixos-fleet-denmarkeast',
            'azurerm_subnet.fleet[0]':prefix+'virtualNetworks/vnet-nixos-fleet-denmarkeast/subnets/bare-hosts',
            'azurerm_network_interface.node2[0]':prefix+'networkInterfaces/nic-nixos-node2',
            'azurerm_public_ip.node2[0]':prefix+'publicIPAddresses/pip6-nixos-node2',
            'azurerm_network_security_group.closed[0]':prefix+'networkSecurityGroups/nsg-nixos-node2-ssh6',
        }
        for c in self.plan['resource_changes']:
            c['change']['after_unknown']={}
            if c['address'] in ids:c['change']['after']['id']=ids[c['address']]
        self.resource('azurerm_linux_virtual_machine.node2[0]')['network_interface_ids']=[ids['azurerm_network_interface.node2[0]']]
        association=self.resource('azurerm_network_interface_security_group_association.closed[0]')
        association.update(network_interface_id=ids['azurerm_network_interface.node2[0]'],network_security_group_id=ids['azurerm_network_security_group.closed[0]'])
        for ip in self.resource('azurerm_network_interface.node2[0]')['ip_configuration']:
            ip['subnet_id']=ids['azurerm_subnet.fleet[0]']
            if ip['name']=='public-ipv6':ip['public_ip_address_id']=ids['azurerm_public_ip.node2[0]']
        self.run_review()
    def test_key_blob_type_mismatch_rejected(self):
        bad='ssh-ed25519 '+base64.b64encode(b'not an ed25519 key blob').decode()
        with self.assertRaises(ValueError):m.fingerprint(bad)
