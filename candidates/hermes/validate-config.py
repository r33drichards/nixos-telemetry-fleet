#!/usr/bin/env python3
"""Reject broad/unqualified draft gateway settings without printing their values."""
import json
import sys

def validate(config):
    assert set(config) == {'model', 'gateway', 'platform_toolsets', 'max_concurrent_sessions'}
    model = config['model']
    assert set(model) == {'provider', 'default'}
    assert model['provider'] in {'openai-codex'}
    assert isinstance(model['default'], str) and model['default'].strip()
    assert type(config['max_concurrent_sessions']) is int and config['max_concurrent_sessions'] == 1
    # Initial conversational qualification; terminal/browser tools not approved.
    assert config['platform_toolsets'] == {'irc': []}
    assert set(config['gateway']) == {'platforms'}
    platforms = config['gateway']['platforms']
    assert set(platforms) == {'irc'} and platforms['irc']['enabled'] is True
    assert set(platforms['irc']) == {'enabled', 'extra'}
    extra = platforms['irc']['extra']
    assert set(extra) == {'server', 'port', 'nickname', 'channel', 'use_tls', 'allowed_users'}
    assert extra['channel'] == '#hermes' and extra['use_tls'] is True
    assert isinstance(extra['server'], str) and extra['server']
    assert type(extra['port']) is int and 1 <= extra['port'] <= 65535
    assert isinstance(extra['nickname'], str) and extra['nickname']
    assert extra['allowed_users'] == ['yournick']
    assert all(isinstance(n, str) and n and not any(c in n for c in ', *?\r\n') for n in extra['allowed_users'])

if __name__ == '__main__':
    try:
        validate(json.load(open(sys.argv[1])))
    except Exception:
        sys.exit('Hermes configuration rejected; no configuration values disclosed')
