import copy
import importlib.util
from pathlib import Path
import unittest
spec = importlib.util.spec_from_file_location("cachix_spec", Path(__file__).parents[1] / "scripts/check-cachix-spec.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
class SpecTests(unittest.TestCase):
    def fixture(self):
        return {"agents": {"node2": "/nix/store/" + "a" * 32 + "-nixos-system-node2"}, "rollbackScript": {"x86_64-linux": "/nix/store/" + "b" * 32 + "-node2-health/bin/node2-health"}}
    def test_valid(self):
        m.validate(self.fixture())
    def test_extra_agent(self):
        x = self.fixture(); x["agents"]["node3"] = x["agents"]["node2"]
        with self.assertRaises(ValueError): m.validate(x)
    def test_missing_health(self):
        x = self.fixture(); del x["rollbackScript"]
        with self.assertRaises(ValueError): m.validate(x)
    def test_non_store_target(self):
        x = self.fixture(); x["agents"]["node2"] = "/tmp/system"
        with self.assertRaises(ValueError): m.validate(x)
