#!/usr/bin/env python3
"""Actual host checks; missing inventory/access/behavior fails, never skips.

Inventory is host-local JSON: {"nodes": [{"ssh": "operator@host",
"overlay": "fd42:6e69:7800::1", "wasm": true}, ...]}.
The runner receives /run/fleet/ssh_key and known_hosts outside Git.
"""
import ipaddress, json, pathlib, re, subprocess, sys
inventory = json.loads(pathlib.Path(sys.argv[1]).read_text())
nodes = inventory['nodes']
assert len(nodes) == 3, 'Exactly three actual hosts required'
assert len({n['ssh'] for n in nodes}) == 3, 'Hosts must be distinct'
assert any(n.get('wasm') for n in nodes), 'An actual Wasm host is required'
for node in nodes:
    assert re.fullmatch(r'operator@[A-Za-z0-9.:\[\]-]+', node['ssh']), 'Invalid SSH destination'
    assert ipaddress.ip_address(node['overlay']).version == 6
    assert ipaddress.ip_address(node['overlay']).is_private

def run(node, command):
    result = subprocess.run(['ssh', '-i', '/run/fleet/ssh_key', '-o', 'BatchMode=yes',
        '-o', 'StrictHostKeyChecking=yes', '-o', 'UserKnownHostsFile=/run/fleet/known_hosts',
        '-o', 'ConnectTimeout=15', node['ssh'], command], capture_output=True, timeout=60)
    if result.returncode:
        raise RuntimeError('Cloud E2E command failed; inspect through approved private diagnostics')
    return result.stdout

for node in nodes:
    run(node, "grep -q '^ID=nixos' /etc/os-release && systemctl is-active wg-quick-wg0 comin prometheus-node-exporter")
    for peer in nodes:
        run(node, "curl -g --noproxy '*' --max-time 15 -fsS 'http://[%s]:9100/metrics' | grep -q node_uname_info" % peer['overlay'])
        if peer.get('wasm'):
            run(peer, 'systemctl is-active wasm-http')
            body = run(node, "curl -g --noproxy '*' --max-time 15 -fsS 'http://[%s]:8080/'" % peer['overlay'])
            assert body == b'hello from wasm\n', 'Actual Wasm response mismatch'
print('PASS: three NixOS hosts, active Comin/WireGuard, cross-node metrics and actual Wasm HTTP')
