#!/usr/bin/env python3
"""Actual host checks; missing inventory/access/behavior fails, never skips.

Inventory is host-local JSON: {"nodes": [{"ssh": "operator@host",
"name": "node2"}, ...]}.
The runner receives /run/fleet/ssh_key and known_hosts outside Git.
"""
import ipaddress, json, os, pathlib, re, subprocess, sys
inventory = json.loads(pathlib.Path(sys.argv[1]).read_text())
expected_revision = os.environ['GITHUB_SHA']
assert re.fullmatch(r'[a-f0-9]{40}', expected_revision), 'Expected source revision required'
nodes = inventory['nodes']
assert len(nodes) == 2, 'Exactly two actual hosts required'
assert len({n['ssh'] for n in nodes}) == 2, 'Hosts must be distinct'
for node in nodes:
    assert re.fullmatch(r'operator@[A-Za-z0-9.:\[\]-]+', node['ssh']), 'Invalid SSH destination'

def run(node, command):
    result = subprocess.run(['ssh', '-i', '/run/fleet/ssh_key', '-o', 'BatchMode=yes',
        '-o', 'StrictHostKeyChecking=yes', '-o', 'UserKnownHostsFile=/run/fleet/known_hosts',
        '-o', 'ConnectTimeout=15', node['ssh'], command], capture_output=True, timeout=60)
    if result.returncode:
        raise RuntimeError('Cloud E2E command failed; inspect through approved private diagnostics')
    return result.stdout

machine_ids = set()
for node in nodes:
    machine_id = run(node, "cat /etc/machine-id").strip()
    assert re.fullmatch(rb"[0-9a-f]{32}", machine_id), "Invalid machine identity"
    assert machine_id not in machine_ids, "Duplicate host identity"
    machine_ids.add(machine_id)
    version = json.loads(run(node, "nixos-version --json"))
    assert version["configurationRevision"] == expected_revision, "Host configuration revision does not match approved workflow head"
    run(node, "grep -q '^ID=nixos' /etc/os-release && systemctl is-active comin sshd")
    run(node, "for unit in wasm-http grafana prometheus prometheus-node-exporter k3s wg-quick-wg0; do if systemctl is-active --quiet $unit; then exit 1; fi; done")
print('PASS: two distinct NixOS hosts at approved revision, authenticated SSH, active Comin and no unwanted services')
