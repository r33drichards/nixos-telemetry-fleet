"""Import/configuration qualification only. Never construct a cloud sandbox."""
import importlib.metadata
import os
import sys


def forbid_network(event, args):
    if event in {'socket.connect', 'socket.getaddrinfo', 'socket.sendto'}:
        raise RuntimeError('Network is forbidden in the Modal SDK qualification')


sys.addaudithook(forbid_network)
assert not any(name in os.environ for name in ('MODAL_TOKEN_ID', 'MODAL_TOKEN_SECRET'))
import modal
from tools.environments.modal import ModalEnvironment
from tools.tool_backend_helpers import resolve_modal_backend_state

assert importlib.metadata.version('modal') == '1.6.2'
assert callable(modal.Sandbox.create) and callable(modal.App.lookup)
assert callable(ModalEnvironment)
# Pure backend selection; explicit flags prevent account/entitlement lookup.
for has_direct, expected in ((False, None), (True, 'direct')):
    result = resolve_modal_backend_state(
        'direct', has_direct=has_direct, managed_ready=True, managed_enabled=True)
    assert result['selected_backend'] == expected
print('Pinned Modal SDK imports and direct-mode selection passed; no compute requested')
