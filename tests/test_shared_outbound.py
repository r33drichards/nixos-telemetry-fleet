import copy
import unittest
import test_canary_review as base


class SharedOutbound(unittest.TestCase):
    def setUp(self):
        fixture = base.Review()
        fixture.setUp()
        fixture.test_known_ids_match_the_same_planned_graph()
        self.plan, self.bootstrap = fixture.plan, fixture.bootstrap
        self.plan['variables']['shared_default_outbound_ipv4'] = {'value': True}
        self.plan['variables']['approval']['value']['shared_default_outbound_ipv4'] = True
        for item in self.plan['resource_changes']:
            change = item['change']
            change['before'] = copy.deepcopy(change['after'])
            change['actions'] = ['no-op']
            if item['address'] == 'azurerm_subnet.fleet[0]':
                change['actions'] = ['update']
                change['after']['default_outbound_access_enabled'] = True
    def review(self):
        return base.m.review(self.plan,b'fixture','a'*40,'123',self.bootstrap)
    def change(self,address):
        return next(x['change'] for x in self.plan['resource_changes'] if x['address']==address)
    def test_exact_subnet_toggle_passes(self):
        summary=self.review()
        self.assertEqual(summary['actions'],{'create':0,'update':1,'delete':0,'no-op':7})
        self.assertEqual(summary['plan_intent'],'enable-shared-default-outbound')
    def test_extra_subnet_change_fails(self):
        self.change('azurerm_subnet.fleet[0]')['after']['address_prefixes']=['10.0.0.0/24']
        with self.assertRaises(ValueError): self.review()
    def test_second_resource_change_fails(self):
        c=self.change('azurerm_network_security_group.closed[0]')
        c['actions']=['update'];c['after']['security_rule'][0]['destination_port_range']='*'
        with self.assertRaises(ValueError):self.review()
    def test_create_replace_and_noop_fail(self):
        for actions in [['create'],['delete','create'],['no-op']]:
            self.change('azurerm_subnet.fleet[0]')['actions']=actions
            with self.assertRaises(ValueError):self.review()
    def test_unapproved_or_ambiguous_trial_fails(self):
        self.plan['variables']['approval']['value']['shared_default_outbound_ipv4']=False
        with self.assertRaises(ValueError):self.review()
        self.setUp();self.change('azurerm_subnet.fleet[0]')['after_unknown']['id']=True
        with self.assertRaises(ValueError):self.review()
    def test_no_trial_flag_does_not_bypass_create_contract(self):
        self.plan['variables']['shared_default_outbound_ipv4']['value']=False
        with self.assertRaises(ValueError):self.review()
    def test_custom_data_change_fails(self):
        self.change('azurerm_linux_virtual_machine.node2[0]')['after']['custom_data']='different'
        with self.assertRaises(ValueError):self.review()
