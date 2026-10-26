"""Offline intake regression against the pinned upstream method, no IRC/model I/O.
Run with the upstream checkout, or --patched PATH for a built plugin.
These method-level tests do not exercise a live IRC connection.
"""
import ast
import asyncio
from pathlib import Path
import re
import subprocess
import sys
import tempfile

patched = sys.argv[1] == '--patched'
source = Path(sys.argv[2]) if patched else Path(sys.argv[1]) / 'plugins/platforms/irc/adapter.py'
with tempfile.TemporaryDirectory() as d:
    root = Path(d); target = root / 'plugins/platforms/irc/adapter.py'
    target.parent.mkdir(parents=True); target.write_text(source.read_text())
    if not patched:
        subprocess.run(['git', 'apply', '--unidiff-zero', str(Path(__file__).with_name('irc-channel-policy.patch').resolve())], cwd=root, check=True)
    tree = ast.parse(target.read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'IRCAdapter')
    method = next(n for n in cls.body if isinstance(n, ast.AsyncFunctionDef) and n.name == '_handle_privmsg')
    scope = {'re': re}
    exec(compile(ast.Module(body=[method], type_ignores=[]), '<pinned-irc-method>', 'exec'), scope)
    class Fixture:
        _current_nick = 'hermes-bot'
        _allowed_users_lower = {'yournick'}
        def __init__(self): self.received = []
        async def _dispatch_message(self, **kwargs): self.received.append(kwargs)
    async def check():
        for nick, channel, text, expected in [
            ('yournick', '#hermes', 'hermes-bot: hello', True),
            ('YourNick', '#HERMES', 'hermes-bot: hello', True),
            ('yournick', 'hermes-bot', 'hello', False),
            ('yournick', '#other', 'hermes-bot: hello', False),
            ('intruder', '#hermes', 'hermes-bot: hello', False),
            ('yournick', '#hermes', 'unaddressed text', False),
        ]:
            fixture = Fixture()
            await scope['_handle_privmsg'](fixture, nick, channel, text)
            assert bool(fixture.received) is expected
    asyncio.run(check())
print('6 patched upstream IRC intake cases passed; no network/model calls')
