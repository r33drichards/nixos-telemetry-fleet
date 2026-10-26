import copy
import importlib.util
import pathlib
import unittest
from unittest.mock import patch
import subprocess

s=importlib.util.spec_from_file_location('canary',pathlib.Path(__file__).resolve().parents[1]/'scripts/amd-canary-preflight.py')
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)

class CanaryPreflight(unittest.TestCase):
    def setUp(self):
        self.topology={'enabled':True,'location':'denmarkeast','approval':dict.fromkeys(('standard_unsigned_gen2','public_ipv6_ssh','free_compute_and_p6','quota_capacity_checked','state_and_roles','image_region_ready'),True)}
        self.topology['approval'].update(monthly_ancillary_usd=1,evidence='fixture')
        self.skus=[{'name':'Standard_B1s','resourceType':'virtualMachines','locations':['denmarkeast'],'family':'standardBSFamily','restrictions':[],'capabilities':[{'name':'PremiumIO','value':'True'},{'name':'HyperVGenerations','value':'V2'},{'name':'CpuArchitectureType','value':'x64'}]}]
        self.usage=[{'name':{'value':'standardBSFamily'},'limit':1,'currentValue':0},{'name':{'value':'cores'},'limit':1,'currentValue':0}]
    def test_zero_family_quota_fails(self):
        self.usage[0]['limit']=0
        with self.assertRaises(ValueError):m.validate(self.topology,self.skus,self.usage)
    def test_explicit_standard_boot_and_sufficient_quota(self):
        m.validate(self.topology,self.skus,self.usage)
    def test_missing_security_or_replication_approval_fails(self):
        for field in ('standard_unsigned_gen2','image_region_ready','public_ipv6_ssh'):
            p=copy.deepcopy(self.topology);p['approval'][field]=False
            with self.assertRaises(ValueError):m.validate(p,self.skus,self.usage)
    def test_region_move_rechecks_sku(self):
        self.topology['location']='eastus'
        with self.assertRaises(ValueError):m.validate(self.topology,self.skus,self.usage)

    def test_plan_replacement_is_rejected(self):
        with self.assertRaises(ValueError):
            m.validate_plan_actions({'resource_changes':[{'change':{'actions':['delete','create']}}]})
        m.validate_plan_actions({'resource_changes':[{'change':{'actions':['create']}}]})

    def test_premium_disk_support_must_be_verified(self):
        self.skus[0]["capabilities"][0]["value"]="False"
        with self.assertRaises(ValueError):m.validate(self.topology,self.skus,self.usage)

    def test_query_timeout_has_safe_category(self):
        with patch.object(m.subprocess, 'run', side_effect=subprocess.TimeoutExpired('private-command', 240, output='private inventory')):
            with self.assertRaises(m.QueryFailure) as caught: m.read(['vm','list-skus'])
        self.assertEqual(caught.exception.category, 'sku-query:timeout')
        self.assertNotIn('private', str(caught.exception))
    def test_query_denial_and_invalid_json_are_redacted(self):
        for result,expected in [(subprocess.CompletedProcess([],1,'','AuthorizationFailed private-value'),'usage-query:read-denied'),(subprocess.CompletedProcess([],0,'private invalid JSON',''),'usage-query:invalid-response')]:
            with patch.object(m.subprocess,'run',return_value=result):
                with self.assertRaises(m.QueryFailure) as caught: m.read(['vm','list-usage'])
            self.assertEqual(caught.exception.category,expected)
            self.assertNotIn('private',str(caught.exception))

    def test_actual_cli_string_quota_shape(self):
        self.usage = [
            {'name': {'value': 'standardBSFamily'}, 'limit': '10', 'currentValue': '0'},
            {'name': {'value': 'cores'}, 'limit': '10', 'currentValue': '0'},
        ]
        m.validate(self.topology, self.skus, self.usage)
    def test_quota_normalization_rejects_invalid_types(self):
        for value in (True, False, -1, '-1', 1.0, '1.0', '1e2', ' 10', '+10', '', None, [], '١٠'):
            with self.subTest(value=value):
                with self.assertRaises(ValueError): m.quota_integer(value)
        self.assertEqual(m.quota_integer(10),10)
        self.assertEqual(m.quota_integer('10'),10)
    def test_invalid_quota_fails_entire_validation(self):
        for field in ('limit','currentValue'):
            original=self.usage[0][field]
            self.usage[0][field]=True
            with self.assertRaises(ValueError):m.validate(self.topology,self.skus,self.usage)
            self.usage[0][field]=original
    def test_query_timeout_bounds(self):
        with patch.object(m.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'[]','')) as run:
            m.read(['vm','list-skus'])
            self.assertEqual(run.call_args.kwargs['timeout'],240)
            m.read(['vm','list-usage'])
            self.assertEqual(run.call_args.kwargs['timeout'],60)
