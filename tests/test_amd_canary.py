import copy
import importlib.util
import pathlib
import unittest

s=importlib.util.spec_from_file_location('canary',pathlib.Path(__file__).resolve().parents[1]/'scripts/amd-canary-preflight.py')
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)

class CanaryPreflight(unittest.TestCase):
    def setUp(self):
        self.topology={'enabled':True,'location':'denmarkeast','approval':dict.fromkeys(('standard_unsigned_gen2','closed_network','free_compute_and_p6','quota_capacity_checked','state_and_roles','image_region_ready'),True)}
        self.topology['approval'].update(monthly_ancillary_usd=1,evidence='fixture')
        self.skus=[{'name':'Standard_B1s','resourceType':'virtualMachines','locations':['denmarkeast'],'family':'standardBSFamily','restrictions':[],'capabilities':[{'name':'PremiumIO','value':'True'},{'name':'HyperVGenerations','value':'V2'},{'name':'CpuArchitectureType','value':'x64'}]}]
        self.usage=[{'name':{'value':'standardBSFamily'},'limit':1,'currentValue':0},{'name':{'value':'cores'},'limit':1,'currentValue':0}]
    def test_zero_family_quota_fails(self):
        self.usage[0]['limit']=0
        with self.assertRaises(ValueError):m.validate(self.topology,self.skus,self.usage)
    def test_explicit_standard_boot_and_sufficient_quota(self):
        m.validate(self.topology,self.skus,self.usage)
    def test_missing_security_or_replication_approval_fails(self):
        for field in ('standard_unsigned_gen2','image_region_ready'):
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
