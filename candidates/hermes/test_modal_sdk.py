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

# Execute the installed direct constructor with a fake SDK/worker only.
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
import tools.environments.modal as backend

for seconds in (120, 300):
    lookup = AsyncMock(return_value=object())
    create = AsyncMock(return_value=object())
    fake_sdk = SimpleNamespace(App=SimpleNamespace(lookup=SimpleNamespace(aio=lookup)),
                               Sandbox=SimpleNamespace(create=SimpleNamespace(aio=create)))
    worker = Mock()
    worker.run_coroutine.side_effect = lambda coro, timeout: asyncio.run(coro)
    with patch.dict(sys.modules, {"modal": fake_sdk}), \
         patch.dict(os.environ, {"HERMES_MODAL_SANDBOX_TIMEOUT": str(seconds)}), \
         patch.object(backend, "ensure_lazy_dep"), \
         patch.object(backend, "_AsyncWorker", return_value=worker), \
         patch.object(backend, "_resolve_modal_image", return_value="fixture-image"), \
         patch.object(backend, "FileSyncManager"), \
         patch.object(backend.BaseEnvironment, "__init__", return_value=None), \
         patch.object(backend.ModalEnvironment, "init_session"):
        backend.ModalEnvironment(image="fixture", timeout=30,
                                 modal_sandbox_kwargs={"cpu": 1, "memory": 1024},
                                 persistent_filesystem=False)
    assert create.await_count == 1
    assert create.await_args.kwargs["timeout"] == seconds
    assert create.await_args.kwargs["cpu"] == 1
    assert create.await_args.kwargs["memory"] == 1024
with patch.dict(os.environ, {"HERMES_MODAL_SANDBOX_TIMEOUT": "301"}), \
     patch.object(backend, "_AsyncWorker") as worker:
    try:
        backend.ModalEnvironment(image="fixture", persistent_filesystem=False)
    except ValueError:
        pass
    else:
        raise AssertionError("Over-limit sandbox lifetime was accepted")
    worker.assert_not_called()
print("Installed direct constructor passes bounded timeout to fake SDK; no cloud calls")
