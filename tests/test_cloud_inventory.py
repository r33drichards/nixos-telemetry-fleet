"""Reject malformed cloud inventories before any SSH execution."""
import json
import os
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

class CloudInventory(unittest.TestCase):
    def run_invalid(self, nodes, expected):
        with tempfile.TemporaryDirectory() as tmp:
            inventory = pathlib.Path(tmp) / 'inventory.json'
            inventory.write_text(json.dumps({'nodes': nodes}))
            result = subprocess.run(
                ['python3', str(ROOT / 'scripts/cloud-e2e.py'), str(inventory)],
                env={**os.environ, 'GITHUB_SHA': '0' * 40},
                capture_output=True, text=True, timeout=5,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(expected, result.stderr)

    def nodes(self):
        return [{'ssh': f'operator@node{i}', 'overlay': f'fd42::{i}', 'wasm': i == 1} for i in range(1, 3)]

    def test_requires_two_hosts(self):
        self.run_invalid(self.nodes()[:1], 'Exactly two actual hosts required')

    def test_rejects_old_three_host_inventory(self):
        self.run_invalid(self.nodes() + [{'ssh': 'operator@node3', 'overlay': 'fd42::3'}], 'Exactly two actual hosts required')

    def test_rejects_scoped_address(self):
        nodes = self.nodes()
        nodes[0]['overlay'] += '%untrusted-scope'
        self.run_invalid(nodes, 'Unscoped IPv6 address required')

    def test_rejects_duplicate_overlay(self):
        nodes = self.nodes()
        nodes[1]['overlay'] = nodes[0]['overlay']
        self.run_invalid(nodes, 'Overlay addresses must be distinct')

    def test_rejects_shell_metacharacters(self):
        nodes = self.nodes()
        nodes[0]['ssh'] = 'operator@host;exit'
        self.run_invalid(nodes, 'Invalid SSH destination')
